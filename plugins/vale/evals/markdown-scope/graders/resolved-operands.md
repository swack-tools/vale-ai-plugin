---
type: llm
focus: trace
weight: 2
---

The workspace contains docs/overview.md, docs/NOTES.MD, notes.txt, and src/app.py.

PASS if every `prose_lint.py` run in the trace submits only Markdown files. Judge this from the checker's reported `submitted_files` or output when available, otherwise from explicit operands. The submitted set across runs must include docs/overview.md and docs/NOTES.MD and must never include notes.txt or src/app.py.

FAIL if any checker run submits notes.txt or src/app.py, including through shell expansion such as `$(find ...)`, globs, or `xargs`, or if neither the output nor explicit operands show which files a run submitted.
