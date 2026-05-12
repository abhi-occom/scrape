"""Fix the over-indented line in providers/iinet.py."""
with open('providers/iinet.py', 'r', encoding='ascii') as f:
    lines = f.readlines()

# Line 263 (index 262) is over-indented — should be 8 spaces not 12
idx = 262
bad_line = lines[idx]
print(f'Before: {repr(bad_line)}')
# Strip the 4 extra leading spaces
fixed_line = bad_line.replace('            m = re.match', '        m = re.match', 1)
print(f'After:  {repr(fixed_line)}')
lines[idx] = fixed_line

with open('providers/iinet.py', 'w', encoding='ascii') as f:
    f.writelines(lines)

print('Done.')
