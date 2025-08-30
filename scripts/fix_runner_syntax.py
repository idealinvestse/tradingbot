#!/usr/bin/env python3
"""Fix syntax errors in runner.py by removing orphaned function parameters"""

from pathlib import Path


def fix_runner_syntax():
    """Remove orphaned function parameters causing syntax error"""

    runner_path = Path("app/strategies/runner.py")

    with open(runner_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Find and remove orphaned parameters (lines 813-831)
    new_lines = []
    skip_mode = False
    skip_start_line = 812  # 0-indexed
    skip_end_line = 836  # 0-indexed

    for i, line in enumerate(lines):
        # Check if we're in the problematic section
        if i == skip_start_line and "symbol: str" in line:
            skip_mode = True
            print(f"Found orphaned parameters starting at line {i+1}, removing...")
            continue
        elif skip_mode and i > skip_start_line:
            # Skip until we find the next valid Python statement
            if "cid = correlation_id or uuid.uuid4().hex" in line:
                skip_mode = False
                print(f"Found end of orphaned section at line {i+1}")
                # Don't add this line, it's part of the removed function
                continue
            else:
                continue  # Skip this line

        # Add normal lines
        if not skip_mode:
            new_lines.append(line)

    # Write back the fixed content
    with open(runner_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"Fixed {runner_path}")
    print("Removed orphaned function parameters")

    # Verify the file is syntactically correct
    import py_compile

    try:
        py_compile.compile(str(runner_path), doraise=True)
        print("✓ Syntax check passed!")
    except py_compile.PyCompileError as e:
        print(f"✗ Syntax error remains: {e}")
        return False

    return True


if __name__ == "__main__":
    fix_runner_syntax()
