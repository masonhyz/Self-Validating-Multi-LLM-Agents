import ollama
import re
import os
import json
import signal
import importlib.util
from datetime import datetime
from contextlib import contextmanager
from typing import Any, Dict, List, Tuple, Optional




from ollama import Client
client = Client()


@contextmanager
def timeout(duration: int):
    """Simple SIGALRM-based timeout (Unix/macOS)."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {duration} seconds")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(duration)
    try:
        yield
    finally:
        signal.alarm(0)


class SelfValidatingPipeline:
    """
    Self-validating generation pipeline adapted for JSON case inputs.

    Expected case schema (single case object):
    {
      "case_number": int,
      "genre": str,
      "prompt": str,
      "constraints": [str, ...],
      "objective": str,
      "output_format": str
    }

    It preserves the original behavior:
      1) Generate a Python verifier from the case
      2) Iteratively generate candidate outputs
      3) Run verifier and feed back concrete errors/metrics
      4) Save iteration logs + final result artifacts
    """

    def __init__(self, model: str = "qwen2.5:1.5b", max_iterations: int = 5, temperature: float = 0.1):
        self.model = model
        self.max_iterations = max_iterations
        self.temperature = temperature

        self.messages: List[Dict[str, str]] = []
        self.iterations: List[Dict[str, Any]] = []
        self.verifier = None

        self.constraints: List[str] = []
        self.problem_description: str = ""
        self.case_metadata: Dict[str, Any] = {}

        os.makedirs("outputs/iterations", exist_ok=True)
        os.makedirs("outputs/final", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    # -------------------------------------------------------------------------
    # Input loading / normalization
    # -------------------------------------------------------------------------
    def load_problem(self, problem_file: str) -> Dict[str, Any]:
        """
        Load exactly one case JSON object with schema:
        {
            "case_number": int,
            "genre": str,
            "prompt": str,
            "constraints": [str, ...],
            "objective": str,
            "output_format": str
        }
        """
        with open(problem_file, "r", encoding="utf-8") as f:
            case = json.load(f)

        if not isinstance(case, dict):
            raise ValueError("Expected a single JSON object (one case), not a list or wrapper.")

        return self.parse_case_json(case)

    def _extract_case(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            # Exact schema
            if self._looks_like_case(payload):
                return payload

            # Common wrappers
            if "case" in payload and isinstance(payload["case"], dict):
                if self._looks_like_case(payload["case"]):
                    return payload["case"]

            if "cases" in payload and isinstance(payload["cases"], list) and payload["cases"]:
                if isinstance(payload["cases"][0], dict) and self._looks_like_case(payload["cases"][0]):
                    return payload["cases"][0]

            raise ValueError(
                "JSON object does not match case schema and no supported wrapper was found "
                "(expected case dict, {'case': {...}}, or {'cases': [...]})."
            )

        if isinstance(payload, list):
            if not payload:
                raise ValueError("JSON list is empty; expected at least one case object.")
            if isinstance(payload[0], dict) and self._looks_like_case(payload[0]):
                return payload[0]
            raise ValueError("JSON list does not contain a valid case object at index 0.")

        raise ValueError("Unsupported JSON root type; expected dict or list.")

    def _looks_like_case(self, obj: Dict[str, Any]) -> bool:
        required = {"case_number", "genre", "prompt", "constraints", "objective", "output_format"}
        return required.issubset(set(obj.keys()))

    def parse_case_json(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """Return only prompt, constraints, objective, and output_format (assumes fields exist)."""
        self.constraints = [c.strip() for c in case["constraints"]]

        return {
            "prompt": case["prompt"].strip(),
            "constraints": self.constraints,
            "objective": case["objective"].strip(),
            "output_format": case["output_format"].strip(),
            "full_content": case["full_content"].strip(),
        }

    # -------------------------------------------------------------------------
    # Parsing helpers for LLM responses
    # -------------------------------------------------------------------------
    def parse_verifier_only(self, response: str) -> Optional[str]:
        # Prefer explicit VERIFIER: fenced block
        verifier_match = re.search(r"VERIFIER:\s*```python\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
        if verifier_match:
            return verifier_match.group(1).strip()

        # Fallback to any python fenced block
        verifier_match = re.search(r"```python\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
        if verifier_match:
            return verifier_match.group(1).strip()

        return None

    def parse_output_only(self, response: str) -> str:
        text = response.strip()

        # If wrapped in triple backticks, remove only the outer fences
        if text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()

        return text

    # -------------------------------------------------------------------------
    # Verifier execution / validation
    # -------------------------------------------------------------------------
    def execute_verifier(self, verifier_module, output: str):
        if len(output) > 50000:
            return (False, 0.0, f"Output too long ({len(output)} chars; limit 50000)")

        try:
            with timeout(10):
                result = verifier_module.verify(output)
                return result

        except TimeoutError:
            return (False, 0.0, "Verifier execution timed out")
        except Exception as e:
            return (False, 0.0, f"Verifier error: {str(e)}")

    # -------------------------------------------------------------------------
    # Persistence / logging
    # -------------------------------------------------------------------------
    def log_iteration(self, iteration: int, output: str, result: Tuple, feedback: str) -> None:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "output_length": len(output),
            "output_hash": hash(output),
            "is_valid": result[0],
            "message": result[1],
            "score": result[2],
            "details": result[3] if len(result) > 3 else {},
            "feedback_sent": feedback,
        }

        log_file = f"logs/iteration_{iteration}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    def save_iteration(self, iteration: int, output: str, result: Tuple) -> None:
        data = {
            "iteration": iteration,
            "output": output,
            "output_length": len(output),
            "validation_result": {
                "is_valid": result[0],
                "message": result[1],
                "score": result[2],
                "details": result[3] if len(result) > 3 else {},
            },
        }
        self.iterations.append(data)

        filename = f"outputs/iterations/iter_{iteration}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # LLM phases
    # -------------------------------------------------------------------------
    def generate_verifier(self, problem_data: Dict[str, Any]):
        prompt = """
        You are a verifier-generator assistant. Your task is to generate a Python function that verifies 
        whether a candidate output satisfies a mathematically verifiable problem specification, and calculates 
        the percentage of constraints it satisfies. You will be given (1) a problem statement, (2) a list of 
        constraints, and (3) an output format description. Assume the candidate output follows the stated 
        output format. Generate exactly one Python function with this signature: def verify(output: str):. 
        The function must (1) check every constraint in the problem carefully and explicitly, (2) determine 
        whether the output is fully valid (all constraints satisfied), (3) compute a score in [0.0, 1.0] 
        representing the fraction of constraints satisfied, and (4) return a tuple of exactly 3 elements in 
        this format: (is_valid: bool, score: float, message: str). Here, is_valid = True iff all constraints 
        are satisfied, [IMPORTANT:] calculate the score at the end of the function: score = (# satisfied 
        constraints) / (total # constraints), and message is a concise diagnostic summary that indicates which 
        constraint(s) failed and why if invalid, or states that all constraints are satisfied if valid. Do 
        not early terminate the function when you see unstatisfied constraints. Problem: \n\n
        """

        messages = [
            {"role": "user", "content": prompt + problem_data["full_content"]},
        ]

        content = client.chat('qwen3-coder-next:cloud', messages=messages)
        verifier_code = self.parse_verifier_only(content["message"]["content"])

        if verifier_code:
            print("✓ Verifier generated")
            verifier_path = os.path.abspath("outputs/verifier.py")
            with open(verifier_path, "w", encoding="utf-8") as f:
                f.write(verifier_code)

            spec = importlib.util.spec_from_file_location("generated_verifier", verifier_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec from {verifier_path}")

            verifier_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verifier_module)
            if not hasattr(verifier_module, "verify"):
                raise AttributeError("Generated verifier module does not define `verify(output: str)`")
            return verifier_module
        raise RuntimeError("Failed to generate valid verifier")


    def run(self, problem_file: str):
        problem_data = self.load_problem(problem_file)

        print("=== Phase 1: Generating Verifier ===")
        self.verifier = self.generate_verifier(problem_data)

        print("\n=== Phase 2: Generating Outputs ===")
        prompt = """
        Your task is to generate an instance of a solution to problems. You will be given a problem 
        statement and a list of constraints. Your task is to generate an instance of a solution to 
        the problem that satisfies all the constraints, and that follows the output format. DO NOT 
        include anything else as the ouput. No explanation, no commentary. The raw solution will be 
        extracted as a string and directly ran through a verifier function. Problem: \n\n
        """
        self.messages = [
            {"role": "user", "content": prompt + problem_data["full_content"]},
            # {"role": "user", "content": problem_data["full_content"]},
        ]


        for iteration in range(self.max_iterations):
            print(f"--- Iteration {iteration + 1} ---")
            print("PROMPT: ", self.messages)

            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                options={"temperature": self.temperature},
            )
            content = response["message"]["content"]
            output = self.parse_output_only(content)
            print("OUTPUT: ", output)

            result = self.execute_verifier(self.verifier, output)
            is_valid, score, message = result[0], result[1], result[2]
            print("valid: ", is_valid, "score: ", score, "message: ", message)

            if is_valid:
                print("\n✓ All constraints satisfied!")
                self.save_final(problem_data, output, result, success=True)
                return output, result

            feedback_parts = [
                f"Remember to not violate the frequently violated constraint: {message}",
            ]
            feedback = "\n".join(feedback_parts)
            self.messages.append({"role": "user", "content": feedback})

        print("\n✗ Max iterations reached without satisfying all constraints")
        self.save_final(problem_data, output, result, success=False)
        return output, result

    def save_final(self, problem_data: Dict[str, Any], output: str, result: Tuple, success: bool = True) -> None:
        with open("outputs/verifier.py", "r", encoding="utf-8") as f:
            verifier_code = f.read()

        data = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "total_iterations": len(self.iterations),
            "case": problem_data.get("case"),
            "constraints": self.constraints,
            "problem_description": self.problem_description,
            "verifier_path": "outputs/verifier.py",
            "verifier_code": verifier_code,
            "final_output": output,
            "final_result": {
                "is_valid": result[0],
                "message": result[1],
                "score": result[2],
                "details": result[3] if len(result) > 3 else {},
            },
            "iteration_history": self.iterations,
        }

        filename = f"outputs/final/result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        with open("outputs/final/latest_output.txt", "w", encoding="utf-8") as f:
            f.write(output)

        print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    # Example usage:
    #   python self_validating_pipeline_json.py
    # Ensure prompts/verifier_prompt.md and prompts/output_prompt.md exist,
    # and point run(...) to a JSON file in the expected case schema.
    pipeline = SelfValidatingPipeline(
        model="gemma3:4b",
        max_iterations=5,
        temperature=0.7,
    )

    # Change this path to your case JSON file
    output, result = pipeline.run("cases/case1.json")

    print("\n" + "=" * 50)
    print("FINAL OUTPUT")
    print("=" * 50)
    print(output)
