---
type: llm
focus: trace
arm: with-only
---

PASS if the trace shows a `prose_lint.py --stdin` run whose input is the revised runbook step that the final response returns, either verbatim or with only the edits made in response to that run's findings followed by another stdin run on the edited text.

FAIL if the only stdin runs check different or unrelated text, or if the final response returns a revision that was never submitted to the checker.
