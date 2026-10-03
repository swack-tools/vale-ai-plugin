---
type: regex
pattern: '"command"\s*:\s*"(?:[^"\\]|\\.)*prose_lint\.py(?:[^"\\]|\\.)*CHANGELOG\.md(?:[^"\\]|\\.)*"(?:(?!"name"\s*:\s*")[\s\S])*?(?:status\\*"\s*:\s*\\*"clean|No findings under the selected configuration)(?![\s\S]*(?:"name"\s*:\s*"(?:Edit|Write|MultiEdit|NotebookEdit)"|"command"\s*:\s*"(?=(?:[^"\\]|\\.)*?CHANGELOG\.md)(?=(?:(?:[^"\\]|\\.)*?(?:\\n|[;&|(`]|\$\(|-exec\s))?\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:(?:sed|perl|ruby)\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|awk\s[^\n]*-i\s*inplace|(?:ed|ex)\s+-s\b|dd\s|(?:mv|cp|rm|install|rsync|tee|truncate)\s)|(?:[^"\\]|\\.)*?(?:open\([^)]*[\\"''][wax]\+?[\\"'']|\.(?:write_text|write_bytes|replace|rename)\(|\b(?:os|shutil)\.(?:remove|rename|replace|move|copy\w*)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;]))))'
target: trace
arm: both
---
