---
type: llm
focus: trace
arm: with-only
weight: 2
---

PASS if the last `prose_lint.py --stdin` run on the revised step that the final response returns reports no findings, or if the final response lists every finding from that run with its rule, separately from editorial advice.

FAIL if that last run reports any finding the final response doesn't disclose, or if the final response claims a clean check that the run doesn't show.
