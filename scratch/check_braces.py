import re

with open(r"c:\Users\Elite computers\OneDrive\Documents\LNBTI\AntiGravity\aethersync\frontend\static\style.css", "r", encoding="utf-8") as f:
    content = f.read()

# Simple bracket matcher
stack = []
line_no = 1
col_no = 1
errors = []

# Strip comments to avoid false alarms
content_clean = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

open_braces = 0
for idx, char in enumerate(content):
    if char == '\n':
        line_no += 1
        col_no = 1
    else:
        col_no += 1
        
    if char == '{':
        open_braces += 1
        stack.append((line_no, col_no))
    elif char == '}':
        open_braces -= 1
        if open_braces < 0:
            errors.append(f"Stray closing brace '}}' at line {line_no}, col {col_no}")
            open_braces = 0 # reset
        elif stack:
            stack.pop()

while stack:
    l, c = stack.pop()
    errors.append(f"Unmatched opening brace '{{' at line {l}, col {c}")

if errors:
    print("CSS Brace Verification Errors found:")
    for err in errors:
        print(" -", err)
else:
    print("CSS Braces check: All braces matched correctly!")
