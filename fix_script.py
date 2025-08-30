with open('app/strategies/runner.py', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
dataclass_count = 0
function_count = 0

while i < len(lines):
    line = lines[i]
    
    if line.strip() == '@dataclass' and i+1 < len(lines) and lines[i+1].strip() == 'class RunResult:':
        dataclass_count += 1
        if dataclass_count == 1:
            new_lines.append(line)
        elif dataclass_count == 2:
            # Skip the duplicate RunResult class (4 lines)
            i += 4
            continue
    elif line.strip().startswith('def _run('):
        function_count += 1
        if function_count == 1:
            new_lines.append(line)
        elif function_count == 2:
            # Skip the duplicate _run function until we find an empty line
            while i < len(lines) and lines[i].strip() != '':
                i += 1
            i += 1  # Skip the empty line too
            continue
    else:
        new_lines.append(line)
    
    i += 1

with open('app/strategies/runner.py', 'w') as f:
    f.writelines(new_lines)