# Fix duplicate definitions in runner.py
lines = open('app/strategies/runner.py').readlines()
new_lines = []
i = 0
first_dataclass = True
first_function = True

while i < len(lines):
    line = lines[i]
    
    # Skip duplicate RunResult class
    if line.strip() == '@dataclass' and i+1 < len(lines) and lines[i+1].strip() == 'class RunResult:' and not first_dataclass:
        i += 4  # Skip the class definition
        continue
    elif line.strip() == '@dataclass' and i+1 < len(lines) and lines[i+1].strip() == 'class RunResult:':
        first_dataclass = False
    
    # Skip duplicate _run function
    elif line.strip().startswith('def _run(') and not first_function:
        # Skip until we find an empty line
        while i < len(lines) and lines[i].strip() != '':
            i += 1
        i += 1  # Skip the empty line too
        continue
    elif line.strip().startswith('def _run('):
        first_function = False
    
    new_lines.append(line)
    i += 1

open('app/strategies/runner.py', 'w').writelines(new_lines)
