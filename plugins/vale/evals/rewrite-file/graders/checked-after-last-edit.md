---
type: regex
pattern: '"command"\s*:\s*"(?:[^"\\]|\\.)*prose_lint\.py(?:[^"\\]|\\.)*README\.md(?:[^"\\]|\\.)*"(?![\s\S]*(?:"name"\s*:\s*"(?:Edit|Write|MultiEdit|NotebookEdit)"|"command"\s*:\s*"(?=(?:[^"\\]|\\.)*?README\.md)(?=(?:(?:[^"\\]|\\.)*?(?:\\n|[;&|(`]|\$\(|-exec\s))?\s*(?:(?:sudo|command|env|xargs)\s+(?:-\S+\s+)*)?(?:(?:sed|perl|ruby)\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*i|awk\s[^\n]*-i\s*inplace|(?:ed|ex)\s+-s\b|dd\s|(?:mv|cp|rm|install|rsync|tee|truncate)\s)|(?:[^"\\]|\\.)*?(?:open\([^)]*[\\"''][wax]\+?[\\"'']|\.(?:write_text|write_bytes|replace|rename)\(|\b(?:os|shutil)\.(?:remove|rename|replace|move|copy\w*)\(|(?:^|[\s;&|(])>>?\s*(?!&|/dev/null)[^\s&|;]))))'
target: trace
arm: both
---
