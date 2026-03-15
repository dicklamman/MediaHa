import re

with open('home-assistant-addon/src/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace
old = '# Check if contains any Japanese characters (indicating Japanese o3ics)'
new = '# Check if contains any Japanese characters (hiragana or katakana) - indicating Japanese o3ics'

if old in content:
    content = content.replace(old, new)
    with open('home-assistant-addon/src/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated successfully')
else:
    print('Pattern not found')
