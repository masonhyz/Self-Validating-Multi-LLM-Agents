import ollama
import re
import os
import json
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

class SelfValidatingPipeline:
    def __init__(self, model="qwen2.5:1.5b", max_iterations=5, temperature=0.1):
        self.model = model
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
    
    def log_iteration(self, iteration, output, result, feedback):
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "output_length": len(output),
            "output_hash": hash(output),
            "is_valid": result[0],
            "message": result[1],
            "score": result[2],
            "details": result[3] if len(result) > 3 else {},
            "feedback_sent": feedback
        }
        
        log_file = f"logs/iteration_{iteration}.json"
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)
    
    def save_iteration(self, iteration, output, result):
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
        
        filename = f"outputs/iterations/iter_{iteration}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    
    def generate_verifier(self, problem_data):
        print("=== Phase 1: Generating Verifier ===")
        
        # Enhanced prompt with parsing information
        enhanced_verifier_prompt = f"""{self.verifier_prompt}

IMPORTANT: The output you need to verify will be extracted using this Python code:
```python
def parse_output_only(response):
    output_match = re.search(r'OUTPUT:\\s*(.*)', response, re.DOTALL)
    if output_match:
        text = output_match.group(1).strip()
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        return text.strip()
    return response.strip()
```

This means the output will be a STRING with any markdown code blocks removed. Design your verifier accordingly."""

        messages = [
            {"role": "system", "content": enhanced_verifier_prompt},
            {"role": "user", "content": problem_data["full_content"]}
        ]
        
        for attempt in range(3):
            print(f"Verifier generation attempt {attempt + 1}...")
            
            response = ollama.chat(
                model=self.model, 
                messages=messages,
                options={"temperature": self.temperature}
            )
            content = response['message']['content']
            
            verifier = self.parse_verifier_only(content)
            
            if verifier:
                # Write verifier to file
                with open("outputs/verifier.py", "w") as f:
                    f.write(verifier)
                
                # Load module from file
                try:
                    spec = importlib.util.spec_from_file_location("verifier", "outputs/verifier.py")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if self.validate_verifier(module):
                        print("✓ Valid verifier generated")
                        self.verifier = module
                        return module
                    
                except Exception as e:
                    print(f"✗ Error loading verifier module: {e}")
            
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
        problem_data = self.load_problem(problem_file)
        
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
        
        self.messages = [
            {"role": "system", "content": enhanced_output_prompt},
            {"role": "user", "content": problem_data["description"]}
        ]
        
        for iteration in range(self.max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            
            response = ollama.chat(
                model=self.model, 
                messages=self.messages,
                options={"temperature": self.temperature}
            )
            content = response['message']['content']
            
            output = self.parse_output_only(content)
            
            result = self.execute_verifier(self.verifier, output)
            is_valid, message, score = result[0], result[1], result[2]
            details = result[3] if len(result) > 3 else {}
            
            print(f"Valid: {is_valid} | Score: {score:.3f}")
            print(f"Message: {message}")
            if details:
                print(f"Details: {details}")
            
            self.save_iteration(iteration + 1, output, result)
            self.messages.append({"role": "assistant", "content": content})
            
            if is_valid:
                print("\n✓ All constraints satisfied!")
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
            
            self.log_iteration(iteration + 1, output, result, feedback)
            self.messages.append({"role": "user", "content": feedback})
        
        print("\n✗ Max iterations reached without satisfying all constraints")
        self.save_final(output, result, success=False)
        return output, result
    
    def save_final(self, output, result, success=True):
        with open("outputs/verifier.py", "r") as f:
            verifier_code = f.read()
        
        data = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "total_iterations": len(self.iterations),
            "constraints": self.constraints,
            "problem_description": self.problem_description,
            "verifier_path": "outputs/verifier.py",
            "verifier_code": verifier_code,
            "final_output": output,
            "final_result": {
                "is_valid": result[0],
                "message": result[1],
                "score": result[2],
                "details": result[3] if len(result) > 3 else {}
            },
            "iteration_history": self.iterations
        }
        
        filename = f"outputs/final/result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        with open("outputs/final/latest_output.txt", "w") as f:
            f.write(output)
        
        print(f"\nResults saved to {filename}")

if __name__ == "__main__":
    pipeline = SelfValidatingPipeline(
        model="gemma2:2b", 
        max_iterations=5,
        temperature=0.7
    )
    output, result = pipeline.run("prompts/story_problem.md")
    
    print("\n" + "="*50)
    print("FINAL OUTPUT")
    print("="*50)
    print(output)
