---
type: tool_used
tool: Bash
input_match: '(?:(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:sed|perl|ruby)\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?awk\s[^\n]*-i\s*inplace|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:ed|ex)\s+-s\b|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?dd\s[^\n]*\bof=|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:mv|cp|rm|touch|truncate|install|ln|chmod|unlink|rsync|tee)\s|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?mktemp\b|(?:^|"command":"|\\n|[;&|(`]|\$\(|-exec\s)\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?git\s+(?:commit|checkout|switch|stash|reset|restore|add|rm|mv|apply|merge|rebase|cherry-pick)\b|\s-delete\b|open\([^)]*[\\"''][wax]\+?[\\"'']|\b(?:os|shutil|pathlib)\.(?:remove|unlink|rename|replace|move|copy\w*|rmtree)\(|\.(?:unlink|rename|replace|touch|write_text|write_bytes)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;])'
min: 0
max: 0
arm: both
---
