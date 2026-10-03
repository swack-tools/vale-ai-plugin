---
type: llm
focus: trace
weight: 2
---

The workspace contains docs/overview.md, docs/NOTES.MD, notes.txt, and src/app.py.

PASS if every `prose_lint.py` run in the trace submits only Markdown files, at least one completed run (status `findings` or `clean`, not `incomplete` or `skipped`) submitted docs/overview.md and docs/NOTES.MD, and every finding in the final response appears in that completed output. Judge submitted files from the checker's reported `submitted_files` or output when available, otherwise from explicit operands.

FAIL if any checker run submits notes.txt or src/app.py, including through shell expansion such as `$(find ...)`, globs, or `xargs`; if no completed run covers both Markdown files; or if the final response reports findings that don't come from a completed run's output.
