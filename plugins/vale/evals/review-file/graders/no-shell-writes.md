---
type: tool_used
tool: Bash
input_match: '(?:\bsed\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\btee\b|\b(?:mv|cp|rm|touch|truncate|install)\s|\bmktemp\b|\bgit\s+(?:commit|checkout|switch|stash|reset|restore|add|rm|mv|apply|merge|rebase|cherry-pick)\b|open\([^)]*[\\"''][wax]\+?[\\"'']|\.write_(?:text|bytes)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;])'
min: 0
max: 0
arm: both
---
