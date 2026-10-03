---
type: llm
focus: trace
arm: with-only
---

PASS if, after the last tool call that modifies CHANGELOG.md, the trace contains a `prose_lint.py --check` run on CHANGELOG.md with no `--include`, `--exclude`, `--clear-include`, `--clear-exclude`, or `--profile` override, and that run reports no findings and no skipped files.

FAIL if no such run follows the last modification, if the last such run reports findings, skipped files, or an incomplete status, or if the only clean result came from a run with policy overrides.
