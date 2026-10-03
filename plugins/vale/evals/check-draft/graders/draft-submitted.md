---
type: llm
focus: trace
arm: with-only
---

The user's draft is a Markdown heading "Setting Up The Tool" followed by the paragraph "We will install the package, e.g. with pip. Simply run the installer and it will be done!" The user named its target path as docs/setup.md.

PASS if the trace shows a `prose_lint.py --stdin --path docs/setup.md` run whose input is that draft unchanged, its output uses the virtual identity `<stdin:docs/setup.md>`, and the findings in the final response match that run's output.

FAIL if no stdin run uses the docs/setup.md logical path, if the stdin runs check altered or unrelated text, or if the final response reports findings that don't appear in that run's output.
