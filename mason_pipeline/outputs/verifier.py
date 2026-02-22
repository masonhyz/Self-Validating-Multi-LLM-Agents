def verify(output: str):
    # Initialize constraints list with their satisfaction status
    constraints = [
        # Constraint 1: The string contains exactly 1 occurrence of the substring '2026'.
        lambda s: s.count('2026') == 1,
        # Constraint 2: The string contains no occurrence of '000'.
        lambda s: '000' not in s,
        # Constraint 3: The string must not start with '0'.
        lambda s: s[0] != '0',
        # Constraint 4: The string must end with an odd digit.
        lambda s: int(s[-1]) % 2 == 1,
        # Constraint 5: The total number of even digits (0,2,4,6,8) is exactly 10.
        lambda s: sum(1 for c in s if c in '02468') == 10
    ]
    
    # Check string length (implicit requirement of 20 digits)
    is_20_digits = len(output) == 20
    
    # If length is not 20, none of the constraints can be satisfied
    if not is_20_digits:
        failed_constraints = []
        if not is_20_digits:
            failed_constraints.append("length is not 20")
        return (False, 0.0, f"Invalid string: {'; '.join(failed_constraints)}")
    
    # Evaluate each constraint
    satisfied = 0
    failed = []
    
    for i, constraint in enumerate(constraints):
        try:
            if constraint(output):
                satisfied += 1
            else:
                failed.append(f"constraint {i+1}")
        except Exception:
            failed.append(f"constraint {i+1}")
    
    # Determine validity
    is_valid = len(failed) == 0
    
    # Calculate score
    total_constraints = len(constraints)
    score = satisfied / total_constraints
    
    # Build message
    if is_valid:
        message = "All constraints satisfied."
    else:
        message = f"Failed constraints: {', '.join(failed)}."
    
    return (is_valid, score, message)