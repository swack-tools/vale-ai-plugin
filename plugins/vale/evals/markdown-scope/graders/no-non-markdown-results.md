---
type: regex
pattern: '\\*"command\\*"\s*:\s*\\*"(?:(?!\\*"(?:name|type|id|file_path|description|content|tool_use_id|old_string|new_string|input|timeout|role)\\*"\s*:)[\s\S])*?prose_lint\.py(?:(?!\\*"name\\*"\s*:\s*\\*")[\s\S])*?(?:notes\.txt|src/app\.py)'
match: not_contains
target: trace
arm: both
---
