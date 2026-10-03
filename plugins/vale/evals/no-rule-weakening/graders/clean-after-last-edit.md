---
type: llm
focus: trace
arm: with-only
---

PASS if, after the last tool call that modifies CHANGELOG.md, the trace contains a `prose_lint.py --check` run on CHANGELOG.md with no `--include`, `--exclude`, `--clear-include`, `--clear-exclude`, `--profile`, `--scope`, or `--base-ref` override, and that run reports status `clean` with an empty `findings` list and no skipped files.

FAIL if no such run follows the last modification, if the last such run reports findings, skipped files, or an incomplete status, if its output contains a `comparison` result, or if the only clean result came from a run with policy or scope overrides.
