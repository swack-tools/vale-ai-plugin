---
type: llm
focus: trace
arm: with-only
weight: 2
---

PASS if the last `prose_lint.py --stdin` run on the section that the final response returns completed with status `clean` or `findings`, and either it reports no findings or if the final response accurately lists every finding from that run with its rule.

FAIL if that last run exited with an error or reported status `incomplete` or `skipped`, for example because `--ext` was missing, if it reports any finding the final response doesn't disclose, or if the final response claims a clean check that the run doesn't show.
