---
type: regex
pattern: '\b[Ww]e\b|\b[Ww]ill\b|e\.g\.|!'
match: not_contains
target: {source: file, path: CHANGELOG.md}
---
