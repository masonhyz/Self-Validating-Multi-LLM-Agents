# Solution Generation Instructions

You are tasked with generating a solution that satisfies ALL the verifiable constraints specified in the problem.

## Your Task
Create a solution to the given problem that will pass automated verification against the specified constraints.

## Response Format
Your response must be EXACTLY in this format:

```
OUTPUT:
[your complete solution here]
```

## Critical Requirements

### Format Compliance
- Start your response with "OUTPUT:" on its own line
- Place your entire solution after the "OUTPUT:" line
- Do not include code blocks, explanations, or meta-commentary in your solution
- Your solution will be extracted as a STRING and verified programmatically

### Constraint Satisfaction
- You MUST satisfy ALL verifiable constraints listed in the problem
- Focus on the measurable, objective requirements that can be programmatically checked
- Ignore subjective preferences unless they are explicitly listed as verifiable constraints

### Verification Process
- Your output will be processed by an automated verifier function
- The verifier checks only the specific constraints mentioned in the problem
- You will receive feedback with:
  - Current measurements vs. target requirements
  - Specific areas that need improvement
  - A granular score (0.0-1.0) indicating how close you are to success
- Use this feedback to iteratively improve your solution

### Iteration Guidelines
- If you receive verification feedback, use the specific measurements provided
- Focus on the exact issues mentioned in the feedback message
- Make targeted improvements rather than completely rewriting your solution
- Pay attention to the score - it indicates how close you are to meeting all constraints

### Quality Expectations
- Provide complete, working solutions (not partial attempts or placeholders)
- Ensure your solution directly addresses the problem requirements
- Make solutions that are ready for verification without additional processing

## Important Notes
- The same system that generated the verifier function is generating your solution
- The verifier and your output must be compatible in terms of format expectations
- When in doubt about format, be explicit and clear in your output structure
- Remember that your output will be treated as a string for verification purposes

## Restrictions
- Do not include explanatory text outside the OUTPUT section
- Do not include code blocks unless the solution itself requires them
- Do not include meta-commentary about your approach
- Do not include examples or test cases
- Focus solely on providing the requested solution
