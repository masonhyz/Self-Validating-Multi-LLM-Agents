# Verifier Generation Instructions

You are tasked with creating a verification function that checks if generated outputs satisfy the VERIFIABLE CONSTRAINTS specified in the problem.

## Your Task
Generate ONLY a Python function named `verify` that takes a string input and returns validation results.

## Required Function Signature
```python
def verify(output):
    # output is a STRING containing the generated solution
    # do not nest any other functions inside verify function and do not assume any other functions can be called from inside this function
    # Check ONLY the VERIFIABLE CONSTRAINTS from the problem
    # Return tuple: (is_valid: bool, message: str, score: float, details: dict)
    # OR return tuple: (is_valid: bool, message: str, score: float)
    
    # Your verification logic here
    
    return (is_valid, message, score, details)
```

## Critical Requirements

### Input Format
- `output` parameter is always a STRING
- The string has markdown code blocks already removed
- Handle the string as-is - no additional parsing needed

### Return Format
You MUST return a tuple with exactly 3 or 4 elements:
1. **is_valid** (bool): True if ALL verifiable constraints are satisfied
2. **message** (string): Specific, actionable feedback with current measurements
3. **score** (float): Granular score between 0.0 and 1.0 where:
   - 1.0 = perfectly satisfies all constraints
   - 0.0 = completely fails all constraints  
   - 0.1-0.9 = partial satisfaction (be granular, not binary!)
4. **details** (dict, optional): Structured metrics for debugging

### Scoring Guidelines
- **Be granular**: Avoid binary 0.0/1.0 scores unless truly warranted
- **Be proportional**: Calculate how close the output is to meeting each constraint
- **Consider multiple constraints**: Weight different constraint violations appropriately
- **Show progress**: If multiple attempts are made, scoring should reflect incremental improvements

### Message Guidelines
- Include specific measurements: "Current count: X (target: Y)"
- Be actionable: "Need to adjust Z by N units to meet constraint"
- Reference actual values from the output
- Explain what specifically failed and by how much

### What to Check
- Check ONLY the "VERIFIABLE CONSTRAINTS" section from the problem
- Ignore subjective quality, style, or content preferences unless explicitly listed as constraints
- Focus on measurable, objective criteria that can be programmatically verified
- Examples of verifiable constraints:
  - Length/count requirements (characters, words, lines, items)
  - Format requirements (JSON structure, specific patterns)
  - Numerical constraints (ranges, calculations, totals)
  - Presence/absence of specific elements
  - Ordering or sequence requirements

### Implementation Tips
- Use appropriate Python libraries for parsing/analysis (re, json, etc.)
- Handle edge cases and malformed inputs gracefully
- Provide detailed measurements in the details dict for complex constraints
- Break down composite scores when checking multiple constraints

## Response Format
Your response must be EXACTLY:

```
VERIFIER:
```python
def verify(output):
    # Your implementation here
    return (is_valid, message, score, details)
```


## Restrictions
- Output ONLY the function definition
- No examples, test cases, or function calls
- No explanatory text before or after
- No sample data or hardcoded tests
- No import statements outside the function (put imports inside if needed)
- End immediately after the function definition

## CRITICAL: Automated Execution Context

**IMPORTANT**: Your verifier function will be executed AUTOMATICALLY without any human review or modification. 

- No human will read or edit your code before execution
- The function must work perfectly as-written with the exact constraints from the problem
- Do not use placeholder values that need manual adjustment
- Do not include comments suggesting future modifications
- Extract constraint values directly from the problem statement
- The function will be called repeatedly in an automated feedback loop

### Example Problem Analysis
If the problem says "less than 250 words":
- Extract: maximum_words = 250 (not a placeholder like 100)
- Check: word_count < 250 (not >= some arbitrary number)
- Score proportionally: e.g., score = max(0.0, 1.0 - max(0, (word_count - 250) / 50))

### Forbidden Patterns
❌ `target_words = 100  # Define desired word count` 
✅ `max_words = 250  # From constraint: less than 250 words`

❌ `score = 0.8 if condition else 0.2  # Binary scoring`
✅ `score = calculate_proportional_score(actual, target)  # Granular scoring`

❌ `# TODO: adjust threshold if needed`
✅ `# Constraint requires exactly what problem specifies`