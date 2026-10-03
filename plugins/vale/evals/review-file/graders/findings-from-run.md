---
type: llm
focus: trace
arm: both
---

PASS if the trace shows a completed `prose_lint.py --check` run whose submitted files include docs/guide.md, and every finding in the final response appears in that run's output.

FAIL if no completed run checked docs/guide.md, if that run was skipped or incomplete, or if the final response reports findings that don't come from that run.
