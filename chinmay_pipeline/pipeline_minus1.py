import ollama
import re
import os
import signal
import importlib.util
from datetime import datetime
from contextlib import contextmanager

@contextmanager
def timeout(duration):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {duration} seconds")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(duration)
    try:
        yield
    finally:
        signal.alarm(0)

# Log file path: same directory as this script
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline_run.log")

class SelfValidatingPipeline:
    def __init__(self, verifier_model="granite4:latest", story_model="gemma3:4b", max_iterations=5, temperature=0.1):
        self.verifier_model = verifier_model
        self.story_model = story_model
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.messages = []
        self.iterations = []
        self.verifier = None
        self.constraints = []
        self.problem_description = ""
        
        os.makedirs("outputs/iterations", exist_ok=True)
        os.makedirs("outputs/final", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        with open("prompts/verifier_prompt.md", "r") as f:
            self.verifier_prompt = f.read()
        
        with open("prompts/output_prompt.md", "r") as f:
            self.output_prompt = f.read()

        self._log_file = None

    def _log_line(self, line=""):
        """Write a line to the run log file if open."""
        if self._log_file is not None:
            self._log_file.write(line + "\n")
            self._log_file.flush()

    def _log_section(self, section_name, content=""):
        """Write a delimited section to the run log file if open."""
        if self._log_file is not None:
            self._log_file.write("\n" + "=" * 60 + "\n")
            self._log_file.write(f" {section_name}\n")
            self._log_file.write("=" * 60 + "\n\n")
            if content:
                self._log_file.write(content if content.endswith("\n") else content + "\n")
            self._log_file.flush()
    
    def load_problem(self, problem_file):
        with open(problem_file, "r") as f:
            content = f.read()
        
        # Parse structured problem format
        problem_data = self.parse_problem_structure(content)
        return problem_data
    
    def parse_problem_structure(self, content):
        """Parse structured problem format to separate description from constraints"""
        # Look for VERIFIABLE CONSTRAINTS section
        constraint_match = re.search(r'## VERIFIABLE CONSTRAINTS\s*\n(.*?)(?:\n##|\Z)', content, re.DOTALL)
        constraints = []
        if constraint_match:
            constraint_text = constraint_match.group(1).strip()
            # Parse individual constraints (assuming bullet format)
            constraint_lines = [line.strip() for line in constraint_text.split('\n') if line.strip().startswith('-')]
            constraints = [line[1:].strip() for line in constraint_lines]
        
        # Get everything before VERIFIABLE CONSTRAINTS as description
        if constraint_match:
            description = content[:constraint_match.start()].strip()
        else:
            description = content.strip()
        
        self.constraints = constraints
        self.problem_description = description
        
        return {
            "description": description,
            "constraints": constraints,
            "full_content": content
        }
    
    def parse_verifier_only(self, response):
        # Look for VERIFIER block first
        verifier_match = re.search(r'VERIFIER:\s*```python\n(.*?)```', response, re.DOTALL)
        if verifier_match:
            return verifier_match.group(1).strip()
        
        # Fallback to any python block
        verifier_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
        if verifier_match:
            return verifier_match.group(1).strip()
        
        return None
    
    def parse_output_only(self, response):
        # Look for OUTPUT: section
        output_match = re.search(r'OUTPUT:\s*(.*)', response, re.DOTALL)
        if output_match:
            text = output_match.group(1).strip()
            # Remove any code blocks from output
            text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
            return text.strip()
        
        # Fallback to full response if no OUTPUT: found
        return response.strip()
    
    def execute_verifier(self, verifier_module, output):
        # Limit output length for safety
        if len(output) > 50000:
            return (False, f"Output too long ({len(output)} chars; limit 50000)", 0.0, {})
        
        try:
            with timeout(10):  # 10 second timeout
                result = verifier_module.verify(output)
                
                # Handle both old format (3-tuple) and new format (4-tuple with details)
                if isinstance(result, tuple) and len(result) == 3:
                    is_valid, message, score = result
                    details = {}
                elif isinstance(result, tuple) and len(result) == 4:
                    is_valid, message, score, details = result
                    if not isinstance(details, dict):
                        details = {}
                else:
                    return (False, f"Verifier returned invalid format: {result}", 0.0, {})
                
                # Validate types
                if not isinstance(is_valid, bool):
                    return (False, f"First element must be bool, got {type(is_valid)}", 0.0, {})
                if not isinstance(message, str):
                    return (False, f"Second element must be str, got {type(message)}", 0.0, {})
                if not isinstance(score, (int, float)):
                    return (False, f"Third element must be number, got {type(score)}", 0.0, {})
                
                return (is_valid, message, float(score), details)
                
        except TimeoutError:
            return (False, "Verifier execution timed out", 0.0, {})
        except Exception as e:
            return (False, f"Verifier error: {str(e)}", 0.0, {})
    
    def validate_verifier(self, verifier_module):
        test_results = []
        test_inputs = ["test", "", "A" * 100]
        
        for test_input in test_inputs:
            result = self.execute_verifier(verifier_module, test_input)
            # Check if result has at least 3 elements with correct types
            if (len(result) >= 3 and 
                result[0] in [True, False] and 
                isinstance(result[1], str) and 
                isinstance(result[2], (int, float))):
                test_results.append(True)
            else:
                test_results.append(False)
        
        return all(test_results)
    
    def save_iteration(self, iteration, output, result):
        """Track iteration in memory (run log has full details)."""
        data = {
            "iteration": iteration,
            "output": output,
            "output_length": len(output),
            "validation_result": {
                "is_valid": result[0],
                "message": result[1],
                "score": result[2],
                "details": result[3] if len(result) > 3 else {}
            }
        }
        self.iterations.append(data)

    def generate_verifier(self, problem_data):
        print("=== Phase 1: Generating Verifier ===")
        
        # Enhanced prompt with parsing information
        enhanced_verifier_prompt = f"""{self.verifier_prompt}

IMPORTANT: The output you need to verify will be a STRING with any markdown code blocks removed. Design your verifier accordingly."""

        messages = [
            {"role": "system", "content": enhanced_verifier_prompt},
            {"role": "user", "content": problem_data["full_content"]}
        ]
        
        for attempt in range(3):
            print(f"Verifier generation attempt {attempt + 1}...")
            self._log_section(f"GENERATE_VERIFIER_ATTEMPT_{attempt + 1}", (
                f"system_prompt (first 15000 chars):\n{messages[0]['content'][:15000]}{'...' if len(messages[0]['content']) > 15000 else ''}\n\n"
                f"user_content (problem full_content):\n{messages[1]['content']}\n"
            ))
            
            response = ollama.chat(
                model=self.verifier_model,
                messages=messages,
                options={"temperature": self.temperature}
            )
            content = response['message']['content']
            self._log_section(f"GENERATE_VERIFIER_ATTEMPT_{attempt + 1}_LLM_RESPONSE", f"length: {len(content)}\n\nfull response:\n{content}")

            verifier = self.parse_verifier_only(content)
            self._log_line(f"--- extracted verifier code (attempt {attempt + 1}) ---")
            if verifier:
                self._log_line(verifier)
                self._log_line("--- end verifier code ---")
            else:
                self._log_line("(none)")
            
            if verifier:
                # Write verifier to file
                with open("outputs/verifier.py", "w") as f:
                    f.write(verifier)
                
                # Load module from file
                try:
                    spec = importlib.util.spec_from_file_location("verifier", "outputs/verifier.py")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    valid = self.validate_verifier(module)
                    self._log_section(f"GENERATE_VERIFIER_ATTEMPT_{attempt + 1}_VALIDATION", f"validate_verifier result: {valid}\nVerifier generated successfully. Path: outputs/verifier.py")
                    
                    if valid:
                        print("✓ Valid verifier generated")
                        self.verifier = module
                        return module
                    
                except Exception as e:
                    print(f"✗ Error loading verifier module: {e}")
                    self._log_section(f"GENERATE_VERIFIER_ATTEMPT_{attempt + 1}_VALIDATION", f"Error loading verifier module: {e}")
            
            print("✗ Invalid verifier, retrying...")
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user", 
                "content": """The verifier is invalid. Please provide a valid Python function with this EXACT signature:

def verify(output):
    # output is a STRING 
    # Check constraints and provide detailed feedback
    # Return (is_valid: bool, message: str, score: float, details: dict)
    # OR return (is_valid: bool, message: str, score: float)
    
    return (is_valid, message, score, details)

Make sure to:
- Handle string input correctly
- Provide granular scores (not just 0 or 1)
- Include specific measurements in your message
- Return concrete, actionable feedback"""
            })
        
        raise Exception("Failed to generate valid verifier after 3 attempts")
    
    def run(self, problem_file):
        # Open run log (overwrite each run), same level as pipeline.py
        self._log_file = open(LOG_PATH, "w", encoding="utf-8")
        final_success = False
        final_output = None
        final_result = None
        final_iteration = 0
        try:
            self._log_section("RUN START", (
                f"timestamp: {datetime.now().isoformat()}\n"
                f"problem_file: {problem_file}\n"
                f"verifier_model: {self.verifier_model}\n"
                f"story_model: {self.story_model}\n"
                f"max_iterations: {self.max_iterations}\n"
            ))

            problem_data = self.load_problem(problem_file)
            self._log_section("LOAD_PROBLEM", f"input: {problem_file}\n\noutput (problem_data):\n  description (length {len(problem_data['description'])}):\n{problem_data['description']}\n\n  full_content length: {len(problem_data['full_content'])}\n  constraints ({len(problem_data['constraints'])}):\n" + "\n".join(f"  - {c}" for c in problem_data["constraints"]))
            self._log_section("PARSE_PROBLEM_STRUCTURE", f"description (first 20000 chars):\n{problem_data['description'][:20000]}{'...' if len(problem_data['description']) > 20000 else ''}\n\nverifiable_constraints:\n" + "\n".join(f"  - {c}" for c in problem_data["constraints"]))

            self.verifier = self.generate_verifier(problem_data)

            print("\n=== Phase 2: Generating Outputs ===")
            print(f"Constraints to verify: {self.constraints}")

            # Load verifier code to share with output generation
            with open("outputs/verifier.py", "r") as f:
                verifier_code = f.read()

            # Enhanced output prompt with verifier information
            enhanced_output_prompt = f"""{self.output_prompt}

CONSTRAINTS TO SATISFY:
{chr(10).join(f"- {constraint}" for constraint in self.constraints)}

THE VERIFIER FUNCTION THAT WILL CHECK YOUR OUTPUT:
```python
{verifier_code}
```

Your output will be processed as a STRING after removing any markdown code blocks. Make sure your format matches what the verifier expects."""

            # User prompt must include both task description and VERIFIABLE CONSTRAINTS (critical for the story LLM)
            user_content = problem_data["description"]
            if self.constraints:
                user_content += "\n\n## VERIFIABLE CONSTRAINTS\n" + "\n".join(f"- {c}" for c in self.constraints)
            self.messages = [
                {"role": "system", "content": enhanced_output_prompt},
                {"role": "user", "content": user_content}
            ]

            for iteration in range(self.max_iterations):
                print(f"\n--- Iteration {iteration + 1} ---")
                n = iteration + 1
                # Prompt to LLM (full messages as sent to ollama.chat)
                msgs_text = "\n\n".join(f"[{m['role']}]\n{m['content'][:80000]}{'...' if len(m.get('content', '')) > 80000 else ''}" for m in self.messages)
                self._log_section(f"ITERATION_{n}_PROMPT_TO_LLM", msgs_text)

                response = ollama.chat(
                    model=self.story_model,
                    messages=self.messages,
                    options={"temperature": self.temperature}
                )
                content = response['message']['content']
                self._log_section(f"ITERATION_{n}_LLM_RESPONSE", content)

                output = self.parse_output_only(content)
                self._log_section(f"ITERATION_{n}_PARSE_OUTPUT_ONLY", output)

                result = self.execute_verifier(self.verifier, output)
                is_valid, message, score = result[0], result[1], result[2]
                details = result[3] if len(result) > 3 else {}
                verifier_input_preview = output[:500] + ("..." if len(output) > 500 else "")
                self._log_section(f"ITERATION_{n}_EXECUTE_VERIFIER", (
                    f"input: output length={len(output)}, first 500 chars:\n{verifier_input_preview}\n\n"
                    f"output: is_valid={is_valid}, message={message}, score={score}, details={details}"
                ))

                print(f"Valid: {is_valid} | Score: {score:.3f}")
                print(f"Message: {message}")
                if details:
                    print(f"Details: {details}")

                self.save_iteration(iteration + 1, output, result)
                self.messages.append({"role": "assistant", "content": content})

                if is_valid:
                    print("\n✓ All constraints satisfied!")
                    final_success = True
                    final_output = output
                    final_result = result
                    final_iteration = n
                    self.save_final(output, result, success=True)
                    return output, result

                # Enhanced feedback with specific metrics
                output_excerpt = output[:300] + ("..." if len(output) > 300 else "")

                feedback_parts = [
                    "VERIFICATION_RESULT:",
                    f"- Valid: {is_valid}",
                    f"- Score: {score:.3f}/1.0",
                    f"- Issues: {message}"
                ]

                if details:
                    feedback_parts.append("- Detailed metrics:")
                    for key, value in details.items():
                        feedback_parts.append(f"  * {key}: {value}")

                feedback_parts.extend([
                    "",
                    f"Your previous output (first 300 chars): '{output_excerpt}'",
                    "",
                    "Fix the issues above and provide an improved solution. Respond with only OUTPUT: followed by your solution."
                ])

                feedback = "\n".join(feedback_parts)
                self._log_section(f"ITERATION_{n}_FEEDBACK_SENT", feedback)
                self.messages.append({"role": "user", "content": feedback})

            print("\n✗ Max iterations reached without satisfying all constraints")
            final_output = output
            final_result = result
            final_iteration = self.max_iterations
            self.save_final(output, result, success=False)
            return output, result
        finally:
            if self._log_file is not None:
                run_end = (
                    f"success: {final_success}\n"
                    f"total_iterations: {final_iteration}\n"
                    f"final_verification: is_valid={final_result[0] if final_result else None}, message={final_result[1] if final_result else None}, score={final_result[2] if final_result else None}\n"
                )
                if final_output is not None:
                    run_end += f"\nfinal_output (see ITERATION_{final_iteration}_PARSE_OUTPUT_ONLY for full text):\n{final_output[:1000]}{'...' if len(final_output) > 1000 else ''}\n"
                run_end += "\nFinal output also written to outputs/final/latest_output.txt"
                self._log_section("RUN END", run_end)
                self._log_file.close()
                self._log_file = None
    
    def save_final(self, output, result, success=True):
        os.makedirs("outputs/final", exist_ok=True)
        with open("outputs/final/latest_output.txt", "w", encoding="utf-8") as f:
            f.write(output)
        print("\nResults saved to outputs/final/latest_output.txt")

if __name__ == "__main__":
    pipeline = SelfValidatingPipeline(
        verifier_model="granite4:latest",
        story_model="gemma3:4b",
        max_iterations=5,
        temperature=0.7
    )
    output, result = pipeline.run("prompts/story_problem_1.md")
    
    print("\n" + "="*50)
    print("FINAL OUTPUT")
    print("="*50)
    print(output)
