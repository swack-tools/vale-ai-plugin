---
type: llm
focus: last_message
weight: 2
---

The bundled Google rules report five findings across the two Markdown files:

1. `docs/overview.md` line 3, `Google.We`: first-person plural "We".
2. `docs/overview.md` line 3, `Google.Will`: "will" in "We will cover".
3. `docs/overview.md` line 3, `Google.Latin`: "e.g." instead of "for example".
4. `docs/NOTES.MD` line 3, `Google.Will`: "will" in "This will be simple".
5. `docs/NOTES.MD` line 3, `Google.Exclamation`: the exclamation point.

PASS if the response reports all five findings as separate items with file, line, and rule, treats `docs/NOTES.MD` as Markdown, and doesn't present notes.txt or src/app.py as checked.

FAIL if any of the five findings is missing, if the response replaces the list with counts or examples, or if it reports findings from notes.txt or src/app.py as part of this Markdown check.
