---
type: llm
focus: last_message
weight: 2
---

PASS if the response reports separate findings for docs/guide.md, each with a line number, a rule name, and a specific suggested correction, and states that it did not edit the file.

FAIL if the response replaces the finding list with counts or examples, omits line numbers or rule names, says it edited the file, or claims complete Google style-guide compliance.
