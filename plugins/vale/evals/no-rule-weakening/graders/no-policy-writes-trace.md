---
type: regex
pattern: '(?:\\*"name\\*"\s*:\s*\\*"(?:Edit|Write|MultiEdit|NotebookEdit)\\*"(?:(?!\\*"name\\*"\s*:\s*\\*")[\s\S])*?\\*"(?:file_path|notebook_path)\\*"\s*:\s*\\*"[^"\\]*(?:\.vale\.ini|\.vale-plugin\.toml|accept\.txt|reject\.txt|(?<![\w.-])styles(?:/|(?=[\s"''\\;&|)]|$)))|\\*"command\\*"\s*:\s*\\*"(?=(?:(?!\\*"(?:name|type|id|file_path|description|content|tool_use_id|old_string|new_string|input|timeout|role)\\*"\s*:)[\s\S])*?(?:\.vale\.ini|\.vale-plugin\.toml|accept\.txt|reject\.txt|(?<![\w.-])styles(?:/|(?=[\s"''\\;&|)]|$))))(?=(?:(?:(?!\\*"(?:name|type|id|file_path|description|content|tool_use_id|old_string|new_string|input|timeout|role)\\*"\s*:)[\s\S])*?(?:\\n|[;&|(`]|\$\(|-exec\s))?\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:(?:sed|perl|ruby)\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|awk\s[^\n]*-i\s*inplace|(?:ed|ex)\s+-s\b|dd\s|(?:mv|cp|rm|install|rsync|tee|truncate|touch|ln|mkdir)\s)|(?:(?!\\*"(?:name|type|id|file_path|description|content|tool_use_id|old_string|new_string|input|timeout|role)\\*"\s*:)[\s\S])*?(?:open\([^)]*[\\"''][wax]\+?[\\"'']|\.(?:write_text|write_bytes|replace|rename|touch)\(|\b(?:os|shutil)\.(?:remove|rename|replace|move|copy\w*)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;])))'
match: not_contains
target: trace
arm: both
---
