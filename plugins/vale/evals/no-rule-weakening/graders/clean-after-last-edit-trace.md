---
type: regex
pattern: '"command"\s*:\s*"(?:[^"\\]|\\.)*prose_lint\.py(?:[^"\\]|\\.)*CHANGELOG\.md(?:[^"\\]|\\.)*"(?:(?!"name"\s*:\s*")[\s\S])*?(?:status\\*"\s*:\s*\\*"clean|No findings under the selected configuration)(?![\s\S]*"name"\s*:\s*"(?:Edit|Write|MultiEdit|NotebookEdit)")'
target: trace
arm: with-only
---
