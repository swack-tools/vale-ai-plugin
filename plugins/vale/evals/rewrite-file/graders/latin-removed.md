---
type: regex
pattern: '^(?!printf ).*e\.g\.'
flags: m
match: not_contains
target: {source: file, path: README.md}
---
