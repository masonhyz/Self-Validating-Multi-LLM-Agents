import re
import os
import json
import importlib.util
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import llm
from config import (
    VERIFIER_MODEL, CRITIC_MODEL, OUTPUT_MODEL,
    MAX_OUTPUT_LEN, VERIFIER_PATH, DETAILS_REQUIRED_KEYS,
)
from prompts import VERIFIER_PROMPT, SYSTEM_MSG, CRITIC_PROMPT_TEMPLATE
from utils import timeout, collapse_newlines


# ---------------------------------------------------------------------------
# Verifier helpers
# ---------------------------------------------------------------------------

def _result_details(result: Tuple) -> Dict:
    """Extract the details dict from a verifier result, or return a fallback."""
    if (
        len(result) > 3
        and isinstance(result[3], dict)
        and DETAILS_REQUIRED_KEYS.issubset(result[3])
    ):
        return result[3]
    message = result[2] if len(result) > 2 else "unknown"
    return {
        "passed": [],
        "failed": [
            {
                "constraint_index": -1,
                "constraint": "verifier contract",
                "reason": f"Verifier did not return a valid 4-tuple with details dict: {message}",
                "expected": "4-tuple (bool, float, str, dict) with keys passed/failed/num_passed/num_failed",
                "observed": repr(result),
            }
        ],
        "num_passed": 0,
        "num_failed": 1,
    }


def _load_verifier_module(path: str):
    spec = importlib.util.spec_from_file_location("generated_verifier", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SelfValidatingPipeline:
    """
    Self-validating generation pipeline for JSON case inputs.

    Phase 1: A verifier-generator LLM writes a verify() function from the case spec.
    Phase 2: A solution-generator LLM iteratively produces candidate outputs; a critic
             LLM converts verifier diagnostics into targeted repair instructions that
             are fed back to the generator until all constraints pass.
    """

    def __init__(self, max_iterations: int = 5, reuse_verifier: bool = False):
        self.max_iterations = max_iterations
        self.reuse_verifier = reuse_verifier

        self.messages: List[Dict[str, str]] = []
        self.iterations: List[Dict[str, Any]] = []
        self.verifier = None
        self.constraints: List[str] = []

        os.makedirs("outputs/iterations", exist_ok=True)
        os.makedirs("outputs/final", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    # -------------------------------------------------------------------------
    # Input loading
    # -------------------------------------------------------------------------

    def load_problem(self, problem_file: str) -> Dict[str, Any]:
        with open(problem_file, "r", encoding="utf-8") as f:
            case = json.load(f)
        if not isinstance(case, dict):
            raise ValueError("Expected a single JSON object (one case), not a list or wrapper.")
        return self._parse_case(case)

    def _parse_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        self.constraints = [c.strip() for c in case["constraints"]]
        return {
            "prompt":        case["prompt"].strip(),
            "constraints":   self.constraints,
            "objective":     case["objective"].strip(),
            "output_format": case["output_format"].strip(),
            "full_content":  collapse_newlines(case["full_content"]),
        }

    # -------------------------------------------------------------------------
    # Response parsing
    # -------------------------------------------------------------------------

    def _parse_verifier_code(self, response: str) -> Optional[str]:
        for pattern in (
            r"VERIFIER:\s*```python\s*\n(.*?)```",
            r"```python\s*\n(.*?)```",
        ):
            m = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def _parse_output(self, response: str) -> str:
        # Strip thinking blocks emitted by reasoning models (Qwen, DeepSeek-R1, etc.)
        text = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = text.strip()
        # Strip outer code fence if the model wrapped the answer anyway
        if text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        return text

    # -------------------------------------------------------------------------
    # Verifier execution
    # -------------------------------------------------------------------------

    def _run_verifier(self, output: str) -> Tuple:
        if len(output) > MAX_OUTPUT_LEN:
            return (False, 0.0, f"Output too long ({len(output)} chars; limit {MAX_OUTPUT_LEN})")
        try:
            with timeout(10):
                return self.verifier.verify(output)
        except TimeoutError:
            return (False, 0.0, "Verifier execution timed out")
        except Exception as e:
            return (False, 0.0, f"Verifier error: {e}")

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _log_iteration(self, iteration: int, output: str, result: Tuple, feedback: str) -> None:
        log_data = {
            "timestamp":    datetime.now().isoformat(),
            "iteration":    iteration,
            "output_length": len(output),
            "output_hash":  hash(output),
            "is_valid":     result[0],
            "score":        result[1],
            "message":      result[2],
            "details":      _result_details(result),
            "feedback_sent": feedback,
        }
        with open(f"logs/iteration_{iteration}.json", "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    def _save_iteration(self, iteration: int, output: str, result: Tuple) -> None:
        data = {
            "iteration":    iteration,
            "output":       output,
            "output_length": len(output),
            "validation_result": {
                "is_valid": result[0],
                "score":    result[1],
                "message":  result[2],
                "details":  _result_details(result),
            },
        }
        self.iterations.append(data)
        with open(f"outputs/iterations/iter_{iteration}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_final(
        self,
        problem_data: Dict[str, Any],
        output: str,
        result: Tuple,
        verifier_code: str,
        success: bool,
    ) -> None:
        now = datetime.now()
        data = {
            "success":          success,
            "timestamp":        now.isoformat(),
            "total_iterations": len(self.iterations),
            "constraints":      self.constraints,
            "verifier_path":    "outputs/verifier.py",
            "verifier_code":    verifier_code,
            "final_output":     output,
            "final_result": {
                "is_valid": result[0],
                "score":    result[1],
                "message":  result[2],
                "details":  _result_details(result),
            },
            "iteration_history": self.iterations,
        }
        filename = f"outputs/final/result_{now.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        with open("outputs/final/latest_output.txt", "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nResults saved to {filename}")

    # -------------------------------------------------------------------------
    # LLM phases
    # -------------------------------------------------------------------------

    def _generate_verifier(self, problem_data: Dict[str, Any]) -> str:
        """Ask the verifier model to write a verify() function. Returns source code."""
        messages = [{"role": "user", "content": VERIFIER_PROMPT + problem_data["full_content"]}]
        verifier_code = self._parse_verifier_code(llm.chat(VERIFIER_MODEL, messages))
        if not verifier_code:
            raise RuntimeError("Verifier LLM did not return a parseable Python code block")
        return verifier_code

    def _load_verifier(self, verifier_code: str):
        """Write verifier code to disk, load as module, smoke-test the 4-tuple contract."""
        with open(VERIFIER_PATH, "w", encoding="utf-8") as f:
            f.write(verifier_code)
        module = _load_verifier_module(VERIFIER_PATH)
        if not hasattr(module, "verify"):
            raise AttributeError("Generated verifier does not define `verify(output: str)`")

        try:
            smoke = module.verify("")
        except Exception as e:
            raise RuntimeError(f"Verifier crashed on smoke test verify(''): {e}") from e

        if not (isinstance(smoke, tuple) and len(smoke) == 4 and isinstance(smoke[3], dict)):
            raise RuntimeError(
                f"Verifier smoke test: expected 4-tuple with dict at [3], "
                f"got {type(smoke).__name__} of len {len(smoke) if isinstance(smoke, tuple) else '?'}"
            )
        missing = DETAILS_REQUIRED_KEYS - smoke[3].keys()
        if missing:
            raise RuntimeError(f"Verifier smoke test: details dict missing keys {missing}")

        return module

    def _generate_repair_suggestions(self, output: str, result: Tuple) -> str:
        """
        Call the critic LLM to convert verifier diagnostics into concrete repair
        instructions for the solution generator. Falls back to _format_feedback on error.
        """
        details = _result_details(result)
        passed  = details.get("passed", [])
        failed  = details.get("failed", [])

        diag_lines = []
        if passed:
            diag_lines.append("ALREADY SATISFIED:")
            diag_lines.extend(f"  ✓ {p}" for p in passed)
        if failed:
            diag_lines.append("VIOLATED:")
            for entry in failed:
                diag_lines.append(f"  ✗ [{entry.get('constraint', '?')}]")
                diag_lines.append(f"      reason:   {entry.get('reason', '?')}")
                diag_lines.append(f"      expected: {entry.get('expected', '?')}")
                diag_lines.append(f"      observed: {entry.get('observed', '?')}")

        excerpt      = output[:800] + ("..." if len(output) > 800 else "")
        critic_input = collapse_newlines(CRITIC_PROMPT_TEMPLATE.format(
            excerpt     = excerpt,
            diagnostics = "\n".join(diag_lines),
        ))

        try:
            with timeout(120):
                suggestions = collapse_newlines(
                    llm.chat(CRITIC_MODEL, messages=[{"role": "user", "content": critic_input}])
                )
        except Exception as e:
            print(f"[critic] LLM call failed ({e}), falling back to formatted feedback")
            return self._format_feedback(output, result)

        passed_block = ""
        if passed:
            passed_block = (
                "Constraints already satisfied (DO NOT break these):\n"
                + "\n".join(f"  ✓ {p}" for p in passed)
                + "\n\n"
            )

        return collapse_newlines(
            "Your previous answer failed verification.\n\n"
            + passed_block
            + "A repair advisor has analysed the failures and produced the following instructions.\n"
            "Follow them exactly:\n\n"
            + suggestions
            + "\n\n"
            f"Your previous output (for reference):\n{excerpt}\n\n"
            "Now produce the corrected answer. "
            "Output ONLY the final answer string — no explanation, no code fences."
        )

    def _format_feedback(self, output: str, result: Tuple) -> str:
        """Fallback: build a repair prompt directly from verifier diagnostics."""
        details = _result_details(result)
        lines   = ["Your previous answer failed verification.", ""]

        passed = details.get("passed", [])
        if passed:
            lines.append("Constraints you already satisfy — DO NOT break these:")
            lines.extend(f"  ✓ {p}" for p in passed)
            lines.append("")

        failed = details.get("failed", [])
        if failed:
            lines.append("Constraints you must fix:")
            for entry in failed:
                lines.append(f"  ✗ [{entry.get('constraint', '?')}]")
                lines.append(f"      Reason:   {entry.get('reason', '?')}")
                lines.append(f"      Expected: {entry.get('expected', '?')}")
                lines.append(f"      Observed: {entry.get('observed', '?')}")
            lines.append("")

        lines.append(
            "Repair your previous answer to fix ONLY the failing constraints above. "
            "Preserve everything that already passes. "
            "Output ONLY the corrected final answer string — no explanation, no code fences."
        )
        return collapse_newlines("\n".join(lines))

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    def run(self, problem_file: str) -> Tuple[Optional[str], Optional[Tuple]]:
        problem_data = self.load_problem(problem_file)

        # Phase 1: verifier
        if self.reuse_verifier:
            print("=== Phase 1: Reusing existing verifier ===")
            with open(VERIFIER_PATH, "r", encoding="utf-8") as f:
                verifier_code = f.read()
            self.verifier = _load_verifier_module(VERIFIER_PATH)
        else:
            print("=== Phase 1: Generating Verifier ===")
            verifier_code = self._generate_verifier(problem_data)
            self.verifier = self._load_verifier(verifier_code)
            print("✓ Verifier generated")

        # Phase 2: iterative output generation
        print("\n=== Phase 2: Generating Outputs ===")
        self.messages = [
            SYSTEM_MSG,
            {
                "role": "user",
                "content": (
                    "Generate a solution that satisfies ALL constraints "
                    "and follows the output format.\n\n"
                    + problem_data["full_content"]
                ),
            },
        ]

        last_output: Optional[str] = None
        last_result: Optional[Tuple] = None

        for iteration in range(self.max_iterations):
            print(f"--- Iteration {iteration + 1} ---")

            try:
                with timeout(1000):
                    content = llm.chat(OUTPUT_MODEL, messages=self.messages)
            except TimeoutError:
                return (None, None)

            self.messages.append({"role": "assistant", "content": content})

            output      = self._parse_output(content)
            last_output = output
            result      = self._run_verifier(output)
            last_result = result
            is_valid, score, message = result[0], result[1], result[2]

            print(f"OUTPUT: {output}")
            print(f"valid={is_valid}  score={score}  message={message}")

            self._save_iteration(iteration + 1, output, result)

            if is_valid:
                print("\n✓ All constraints satisfied!")
                self._save_final(problem_data, output, result, verifier_code, success=True)
                return output, result

            print("  [critic] generating repair suggestions...")
            feedback = self._generate_repair_suggestions(output, result)
            self._log_iteration(iteration + 1, output, result, feedback)
            self.messages.append({"role": "user", "content": feedback})

            # Keep only [system, original problem, latest assistant, latest feedback]
            self.messages = self.messages[:2] + self.messages[-2:]

        print("\n✗ Max iterations reached without satisfying all constraints")
        self._save_final(problem_data, last_output, last_result, verifier_code, success=False)
        return last_output, last_result


if __name__ == "__main__":
    pipeline = SelfValidatingPipeline(
        max_iterations=10,
        reuse_verifier=False,
    )
    output, result = pipeline.run("cases/case3.json")

    print("\n" + "=" * 50)
    print("FINAL OUTPUT")
    print("=" * 50)
    print(output)
