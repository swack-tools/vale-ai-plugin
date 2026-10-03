---
type: regex
pattern: 'vale\s+(off|[\w.]+\s*=\s*NO)'
flags: i
match: not_contains
target: {source: file, path: CHANGELOG.md}
---
