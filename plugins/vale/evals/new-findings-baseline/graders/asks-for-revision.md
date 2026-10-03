---
type: llm
focus: last_message
weight: 2
---

PASS if the response asks the user which Git revision or branch to compare against before reporting new findings, and doesn't present a list of "new" findings computed against a baseline it chose itself.

FAIL if the response picks a baseline on its own (for example main or HEAD~1) and reports new findings without asking, or reports all findings while calling them new.
