Given the problem and CRITICAL CHECK below, output ONLY the verification function. Do not include any examples, test cases, or sample outputs.

Your response must be EXACTLY in this format:

VERIFIER:
```python
def verify(output):
    # output is a STRING containing the generated solution
    # Check ALL CRITICAL requirements from the problem
    # Return tuple: (is_valid: bool, message: str, score: float)
    
    # Your verification logic here
    
    return (is_valid, message, score)
```
Requirements:

- Only output the verify() function
- No examples, test cases, or sample data
- Check ALL CRITICAL constraints from the problem
- Return concrete, specific messages 
- Return monotonic scores where 1.0 = perfect, 0.0 = completely fails, values between indicate partial compliance
- End immediately after the function definition