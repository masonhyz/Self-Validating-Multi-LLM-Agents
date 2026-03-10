from typing import Dict

# ---------------------------------------------------------------------------
# Verifier-generator prompt
# Instructs the LLM to write a verify(output: str) function that returns a
# 4-tuple: (is_valid, score, message, details)
# ---------------------------------------------------------------------------
VERIFIER_PROMPT = """\
You are a verifier-generator assistant. Write exactly ONE Python function:

    def verify(output: str):

STRICT RULES — follow every one exactly:
1. Check EVERY constraint from the problem statement, one by one, explicitly.
2. NEVER return or raise early when a constraint fails — always reach the end and check all constraints.
3. Wrap EACH constraint check in its own try/except so a parse error in one check cannot crash the whole function.
4. Accumulate results in two lists:
   - `passed`: list of short constraint-name strings (one per satisfied constraint)
   - `failed`: list of dicts (one per failing constraint), each with EXACTLY these keys:
       "constraint_index"  int   — 0-based index of this constraint
       "constraint"        str   — short name/description of the constraint
       "reason"            str   — concise explanation of why it failed
       "expected"          str   — what value/property was required (as a plain string)
       "observed"          str   — what was actually found in the output (as a plain string)
5. After all checks, compute:
       num_passed = len(passed)
       num_failed = len(failed)
       total      = num_passed + num_failed
       score      = num_passed / total if total > 0 else 0.0
       is_valid   = (num_failed == 0)
       message    = "All constraints satisfied." if is_valid else "; ".join(f["reason"] for f in failed)
6. Return EXACTLY this 4-tuple (nothing else):
       (is_valid, score, message, details)
   where:
       details = {"passed": passed, "failed": failed, "num_passed": num_passed, "num_failed": num_failed}

Use this scaffold — fill in the constraint checks; do NOT change the return structure:

```python
def verify(output: str):
    passed = []
    failed = []

    # --- Constraint 0: <short name> ---
    try:
        observed = ...        # extract the relevant value from output
        expected = "..."      # required value/property as a plain string
        if <condition>:
            passed.append("Constraint 0: <short name>")
        else:
            failed.append({
                "constraint_index": 0,
                "constraint": "<short name>",
                "reason": "<why it failed; include actual vs required values>",
                "expected": expected,
                "observed": str(observed),
            })
    except Exception as e:
        failed.append({
            "constraint_index": 0,
            "constraint": "<short name>",
            "reason": f"Check raised exception: {e}",
            "expected": "...",
            "observed": "error during check",
        })

    # --- Constraint 1: <short name> ---
    # ... repeat the try/except pattern for every constraint ...

    num_passed = len(passed)
    num_failed = len(failed)
    total = num_passed + num_failed
    score = num_passed / total if total > 0 else 0.0
    is_valid = num_failed == 0
    message = "All constraints satisfied." if is_valid else "; ".join(f["reason"] for f in failed)
    details = {
        "passed": passed,
        "failed": failed,
        "num_passed": num_passed,
        "num_failed": num_failed,
    }
    return (is_valid, score, message, details)
```

Additional requirements:
- Output ONLY the function definition inside a ```python ... ``` block. No other text.
- Put any imports INSIDE the function body (no module-level imports).
- Keep `expected` and `observed` as plain strings; use str() to convert numbers.

Problem to verify:

"""

# ---------------------------------------------------------------------------
# System message for the solution-generator LLM
# ---------------------------------------------------------------------------
SYSTEM_MSG: Dict[str, str] = {
    "role": "system",
    "content": (
        "You are a solution generator. "
        "Your entire response must be the raw answer string and nothing else. "
        "Do not think out loud. Do not explain. Do not restate the problem. "
        "Do not use code fences, bullet points, or any formatting. "
        "Output the solution string and stop immediately."
    ),
}

# ---------------------------------------------------------------------------
# Critic prompt template
# Filled with {excerpt} and {diagnostics} before being sent to the critic LLM.
# ---------------------------------------------------------------------------
CRITIC_PROMPT_TEMPLATE = (
    "The solution generator produced the following candidate output:\n\n"
    "{excerpt}\n\n"
    "The automated verifier reported these results:\n\n"
    "{diagnostics}\n\n"
    "Write a numbered list of SPECIFIC, ACTIONABLE repair instructions — one per violated "
    "constraint — that the solution generator can follow to fix exactly those violations "
    "WITHOUT disturbing the already-satisfied constraints. "
    "Each instruction must name the constraint, state precisely what needs to change "
    "(e.g. exact counts, positions, substrings to add/remove/replace), and explain "
    "how to verify the fix locally. "
    "Do NOT restate the problem. Do NOT generate a solution yourself. "
    "Output ONLY the numbered list of instructions."
)
