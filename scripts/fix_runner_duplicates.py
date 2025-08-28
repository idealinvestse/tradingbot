#!/usr/bin/env python3
"""Fix duplicate functions in runner.py"""

import re
from pathlib import Path


def fix_runner_duplicates():
    """Remove duplicate run_ai_strategies functions from runner.py"""
    
    runner_path = Path("app/strategies/runner.py")
    
    with open(runner_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Count occurrences of run_ai_strategies
    occurrences = len(re.findall(r'async def run_ai_strategies\(', content))
    print(f"Found {occurrences} occurrences of run_ai_strategies")
    
    # Split content by lines for processing
    lines = content.split('\n')
    
    # Track function boundaries
    in_function = False
    function_count = 0
    keep_first = True
    new_lines = []
    indent_level = 0
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is start of run_ai_strategies
        if 'async def run_ai_strategies(' in line:
            function_count += 1
            
            # Keep only the first occurrence
            if function_count == 1 and keep_first:
                # This is the first one, keep it
                in_function = True
                indent_level = len(line) - len(line.lstrip())
                new_lines.append(line)
            else:
                # Skip this duplicate function
                in_function = True
                indent_level = len(line) - len(line.lstrip())
                
                # Check if this is actually a misnamed run_hyperopt
                # Look ahead to see if it has hyperopt-like parameters
                if i + 2 < len(lines) and 'config_path: Path' in lines[i+1]:
                    # This should be run_hyperopt
                    print(f"Found misnamed function at line {i+1}, converting to run_hyperopt")
                    new_lines.append(line.replace('run_ai_strategies', 'run_hyperopt'))
                    in_function = True
                else:
                    # Skip this duplicate
                    print(f"Skipping duplicate at line {i+1}")
                    # Find end of function to skip
                    j = i + 1
                    while j < len(lines):
                        if lines[j].strip() and not lines[j].startswith(' ' * (indent_level + 1)):
                            # Found end of function
                            break
                        j += 1
                    
                    # Check if next line is a blank line or new function
                    if j < len(lines) and (not lines[j].strip() or lines[j].startswith('def ') or lines[j].startswith('async def ')):
                        i = j - 1  # Will be incremented at end of loop
                        in_function = False
        elif in_function:
            # Check if we've reached end of function
            if line.strip() and not line.startswith(' '):
                in_function = False
                new_lines.append(line)
            elif function_count > 1 and not keep_first:
                # Skip lines of duplicate function
                pass
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
        
        i += 1
    
    # Write back cleaned content
    cleaned_content = '\n'.join(new_lines)
    
    # Remove multiple consecutive blank lines
    cleaned_content = re.sub(r'\n\n\n+', '\n\n', cleaned_content)
    
    with open(runner_path, "w", encoding="utf-8") as f:
        f.write(cleaned_content)
    
    print(f"Fixed {runner_path}")
    
    # Verify the fix
    with open(runner_path, "r", encoding="utf-8") as f:
        verify_content = f.read()
    
    new_count = len(re.findall(r'async def run_ai_strategies\(', verify_content))
    print(f"After fix: {new_count} occurrences of run_ai_strategies")


if __name__ == "__main__":
    fix_runner_duplicates()
