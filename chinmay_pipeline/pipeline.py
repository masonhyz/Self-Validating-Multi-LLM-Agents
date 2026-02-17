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
    def __init__(self, model="qwen2.5:1.5b", max_iterations=5):
        self.model = model
        self.max_iterations = max_iterations
        self.messages = []
        self.iterations = []
        self.verifier = None
        self.constraint_summary = ""
        
        os.makedirs("outputs/iterations", exist_ok=True)
        os.makedirs("outputs/final", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        with open("prompts/verifier_prompt.md", "r") as f:
            self.verifier_prompt = f.read()
        
        with open("prompts/output_prompt.md", "r") as f:
            self.output_prompt = f.read()
    
    def load_problem(self, problem_file):
        with open(problem_file, "r") as f:
            return f.read()
    
    def extract_constraint_summary(self, problem):
        critical_match = re.search(r'CRITICAL CHECK[S]?:(.*?)(?:\n\n|\Z)', problem, re.DOTALL | re.IGNORECASE)
        if critical_match:
            return critical_match.group(1).strip()
        return "See problem requirements"
    
    def parse_verifier_only(self, response):
        verifier_match = re.search(r'VERIFIER:\s*```python\n(.*?)```', response, re.DOTALL)
        if verifier_match:
            return verifier_match.group(1).strip()
        
        verifier_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
        if verifier_match:
            return verifier_match.group(1).strip()
        
        return None
    
    def parse_output_only(self, response):
        output_match = re.search(r'OUTPUT:\s*(.*)', response, re.DOTALL)
        if output_match:
            text = output_match.group(1).strip()
            text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
            return text.strip()
        
        return response.strip()
    
    def execute_verifier(self, verifier_module, output):
        # Limit output length for safety
        if len(output) > 50000:
            return (False, f"Output too long ({len(output)} chars; limit 50000)", 0.0)
        
        try:
            with timeout(10):  # 10 second timeout
                result = verifier_module.verify(output)
                
                if not isinstance(result, tuple) or len(result) != 3:
                    return (False, f"Verifier returned invalid format: {result}", 0.0)
                
                is_valid, message, score = result
                if not isinstance(is_valid, bool):
                    return (False, f"First element must be bool, got {type(is_valid)}", 0.0)
                if not isinstance(message, str):
                    return (False, f"Second element must be str, got {type(message)}", 0.0)
                if not isinstance(score, (int, float)):
                    return (False, f"Third element must be number, got {type(score)}", 0.0)
                
                return (is_valid, message, float(score))
                
        except TimeoutError:
            return (False, "Verifier execution timed out", 0.0)
        except Exception as e:
            return (False, f"Verifier error: {str(e)}", 0.0)
    
    def validate_verifier(self, verifier_module):
        test_results = []
        test_inputs = ["test", "", "A" * 1000]
        
        for test_input in test_inputs:
            result = self.execute_verifier(verifier_module, test_input)
            if result[0] in [True, False] and isinstance(result[1], str) and isinstance(result[2], (int, float)):
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
                "score": result[2]
            }
        }
        self.iterations.append(data)
        
        filename = f"outputs/iterations/iter_{iteration}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    
    def generate_verifier(self, problem):
        print("=== Phase 1: Generating Verifier ===")
        
        messages = [
            {"role": "system", "content": self.verifier_prompt},
            {"role": "user", "content": problem}
        ]
        
        for attempt in range(3):
            print(f"Verifier generation attempt {attempt + 1}...")
            
            response = ollama.chat(model=self.model, messages=messages)
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
            messages.append({"role": "user", "content": "The verifier is invalid. Please provide a valid Python function with signature: def verify(output): ... return (bool, str, float). Make sure to return concrete messages and monotonic scores."})
        
        raise Exception("Failed to generate valid verifier after 3 attempts")
    
    def run(self, problem_file):
        problem = self.load_problem(problem_file)
        self.constraint_summary = self.extract_constraint_summary(problem)
        
        self.verifier = self.generate_verifier(problem)
        
        print("\n=== Phase 2: Generating Outputs ===")
        print(f"Will check constraints: {self.constraint_summary}")
        
        # Enhanced output prompt with constraint info
        enhanced_output_prompt = f"{self.output_prompt}\n\nConstraints to satisfy: {self.constraint_summary}"
        
        self.messages = [
            {"role": "system", "content": enhanced_output_prompt},
            {"role": "user", "content": problem}
        ]
        
        for iteration in range(self.max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            
            response = ollama.chat(model=self.model, messages=self.messages)
            content = response['message']['content']
            
            output = self.parse_output_only(content)
            
            result = self.execute_verifier(self.verifier, output)
            is_valid, message, score = result
            
            print(f"Valid: {is_valid} | Score: {score:.3f} | {message}")
            
            self.save_iteration(iteration + 1, output, result)
            self.messages.append({"role": "assistant", "content": content})
            
            if is_valid:
                print("\n✓ Constraints satisfied!")
                self.save_final(output, result, success=True)
                return output, result
            
            # Enhanced feedback with failing output excerpt
            output_excerpt = output[:500] + ("..." if len(output) > 500 else "")
            
            feedback = f"""VERIFICATION_RESULT:
- valid: false
- score: {score:.3f}
- message: "{message}"

Your previous output (first 500 chars):
"{output_excerpt}"

Please fix the issues and respond with only OUTPUT: and your improved solution."""
            
            self.log_iteration(iteration + 1, output, result, feedback)
            self.messages.append({"role": "user", "content": feedback})
        
        print("\n✗ Max iterations reached without satisfying constraints")
        self.save_final(output, result, success=False)
        return output, result
    
    def save_final(self, output, result, success=True):
        with open("outputs/verifier.py", "r") as f:
            verifier_code = f.read()
        
        data = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "total_iterations": len(self.iterations),
            "constraint_summary": self.constraint_summary,
            "verifier_path": "outputs/verifier.py",
            "verifier_code": verifier_code,
            "final_output": output,
            "final_result": {
                "is_valid": result[0],
                "message": result[1],
                "score": result[2]
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
    pipeline = SelfValidatingPipeline(model="qwen2.5:1.5b", max_iterations=5)
    output, result = pipeline.run("prompts/number_problem.txt")
    
    print("\n" + "="*50)
    print("FINAL OUTPUT")
    print("="*50)
    print(output)