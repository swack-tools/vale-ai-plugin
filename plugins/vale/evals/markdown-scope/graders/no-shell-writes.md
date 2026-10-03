---
type: tool_used
tool: Bash
input_match: '(?:\b(?:sed|perl|ruby)\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|\bawk\s+[^\n]*-i\s*inplace|\b(?:ed|ex)\s+-s\b|\bdd\s[^\n]*\bof=|\b(?:ln|chmod|unlink|rsync)\s|\b(?:os|shutil|pathlib)\.(?:remove|unlink|rename|replace|move|copy\w*|rmtree)\(|\.(?:unlink|rename|replace|touch)\(|\btee\b|\b(?:mv|cp|rm|touch|truncate|install)\s|\bmktemp\b|\bgit\s+(?:commit|checkout|switch|stash|reset|restore|add|rm|mv|apply|merge|rebase|cherry-pick)\b|open\([^)]*[\\"''][wax]\+?[\\"'']|\.write_(?:text|bytes)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;])'
min: 0
max: 0
arm: both
---
