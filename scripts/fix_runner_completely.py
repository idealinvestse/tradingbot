#!/usr/bin/env python3
"""Complete fix for runner.py syntax errors"""

from pathlib import Path
import re


def fix_runner_completely():
    """Fix all syntax errors in runner.py"""
    
    runner_path = Path("app/strategies/runner.py")
    
    with open(runner_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find all instances of orphaned function parameters
    # Pattern: lines that look like function parameters but are not in a function definition
    lines = content.split('\n')
    
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip orphaned function parameters after "finally:" blocks
        if i > 0 and 'finally:' in lines[i-2] and 'rm.release_run_slot' in lines[i-1]:
            # Check if next lines look like orphaned parameters
            if i < len(lines) - 1:
                next_line = lines[i+1] if i+1 < len(lines) else ""
                if (line.strip() == "" and 
                    i+1 < len(lines) and 
                    ('symbol: str' in lines[i+1] or 
                     'config_path: Path' in lines[i+1] or
                     lines[i+1].strip().startswith('*,') or
                     lines[i+1].strip().startswith(') ->'))):
                    # Skip until we find a proper function definition or other statement
                    print(f"Found orphaned parameters at line {i+1}")
                    j = i
                    while j < len(lines):
                        if ('def ' in lines[j] or 
                            'async def ' in lines[j] or
                            'class ' in lines[j] or
                            (lines[j].strip() and not lines[j].strip().startswith(')') and 
                             not lines[j].strip().endswith(',') and
                             '"""' not in lines[j] and
                             'Args:' not in lines[j] and
                             'Returns:' not in lines[j] and
                             'import ' in lines[j])):
                            print(f"Skipped to line {j+1}")
                            i = j - 1
                            break
                        j += 1
                    if j >= len(lines):
                        i = j
                    i += 1
                    continue
        
        # Check for unmatched closing parenthesis
        if line.strip() == ') -> dict:':
            print(f"Found unmatched ) -> dict: at line {i+1}, removing")
            i += 1
            continue
        
        # Check for orphaned docstrings without functions
        if '"""' in line and i > 0:
            # Check if this is a docstring without a function
            prev_non_empty = None
            for j in range(i-1, max(0, i-5), -1):
                if lines[j].strip():
                    prev_non_empty = lines[j]
                    break
            
            if prev_non_empty and ') -> dict:' in prev_non_empty:
                # This is an orphaned docstring after bad syntax
                print(f"Found orphaned docstring at line {i+1}, skipping until end of docstring")
                if '"""' in line and line.count('"""') == 2:
                    # Single line docstring
                    i += 1
                    continue
                else:
                    # Multi-line docstring
                    j = i + 1
                    while j < len(lines) and '"""' not in lines[j]:
                        j += 1
                    i = j + 1
                    continue
        
        new_lines.append(line)
        i += 1
    
    # Join and clean up multiple blank lines
    content = '\n'.join(new_lines)
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    # Write back
    with open(runner_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Fixed {runner_path}")
    
    # Verify syntax
    import ast
    try:
        ast.parse(content)
        print("Syntax check passed!")
        return True
    except SyntaxError as e:
        print(f"Syntax error remains at line {e.lineno}: {e.msg}")
        if e.lineno:
            error_lines = content.split('\n')
            start = max(0, e.lineno - 3)
            end = min(len(error_lines), e.lineno + 2)
            print("Context:")
            for i in range(start, end):
                prefix = ">>> " if i == e.lineno - 1 else "    "
                print(f"{prefix}{i+1}: {error_lines[i]}")
        return False


if __name__ == "__main__":
    import sys
    success = fix_runner_completely()
    sys.exit(0 if success else 1)
