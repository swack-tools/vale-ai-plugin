---
type: llm
focus: trace
arm: with-only
---

The user's draft is a Markdown heading "Setting Up The Tool" followed by the paragraph "We will install the package, e.g. with pip. Simply run the installer and it will be done!"

PASS if the trace shows a `prose_lint.py --stdin` run whose input is that draft unchanged, and the findings in the final response match that run's output.

FAIL if the stdin runs check altered or unrelated text, or if the final response reports findings that don't appear in the output of a run on the unchanged draft.
