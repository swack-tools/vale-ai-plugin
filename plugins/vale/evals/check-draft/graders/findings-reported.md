---
type: llm
focus: last_message
weight: 2
---

The bundled Google rules report six findings for this draft:

1. Line 1, `Google.Headings`: the heading "Setting Up The Tool" isn't sentence case.
2. Line 3, `Google.We`: first-person plural "We".
3. Line 3, `Google.Will`: "will" in "We will install".
4. Line 3, `Google.Latin`: "e.g." instead of "for example".
5. Line 3, `Google.Will`: "will" in "it will be done".
6. Line 3, `Google.Exclamation`: the exclamation point.

PASS if the response reports all six findings as separate items. Each item must include the draft's virtual path (`<stdin:docs/setup.md>` or `docs/setup.md`), line, column (the checker reports one for every finding), rule, the matched excerpt, and a specific suggested correction, as the `check-prose` skill requires. The two `Google.Will` findings may share one item only if the response states that the rule matched twice and gives both columns.

FAIL if any of the six findings is missing, if any item lacks the path, line, column, rule, excerpt, or suggested correction, if the response gives counts or examples instead of the full list, or if it claims the draft is clean.
