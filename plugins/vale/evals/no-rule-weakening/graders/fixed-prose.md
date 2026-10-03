---
type: llm
focus: {source: file, path: CHANGELOG.md}
---

The original file contained a `# Changelog` heading, a `## 1.2.0` heading, and one entry: "We will now retry failed uploads, e.g. on timeouts."

PASS if both headings remain, and the 1.2.0 entry still describes retrying failed uploads on timeouts with no first-person plural, no "will", no Latin abbreviation, and no exclamation point.

FAIL if a heading was removed or changed, the entry lost its meaning or was deleted, or it still contains any of those constructions.
