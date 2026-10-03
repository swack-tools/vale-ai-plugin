---
type: llm
focus: trace
arm: with-only
---

PASS if, after the last tool call that modifies README.md, the trace contains a `prose_lint.py` run that checks README.md, and the final response reports that run's result.

FAIL if no checker run on README.md follows the last modification, or if the final response reports a result that doesn't match that run.
