---
type: llm
focus: last_message
weight: 2
---

The bundled Google rules report seven findings for docs/guide.md:

1. Line 1, `Google.Headings`: the heading "Getting Started With The CLI" isn't sentence case.
2. Line 1, `Google.WordList`: "CLI" instead of "command-line tool".
3. Line 3, `Google.We`: first-person plural "We".
4. Line 3, `Google.Will`: "will" in "We will walk you through".
5. Line 3, `Google.Latin`: "e.g." instead of "for example".
6. Line 5, `Google.Will`: "will" in "it will just work".
7. Line 5, `Google.Exclamation`: the exclamation point.

PASS if the response reports all seven findings as separate items and states that it didn't edit the file. Each item must include the path, line, column (the checker reports one for every finding), rule, the matched excerpt, and a specific suggested correction, as the `check-prose` skill requires.

FAIL if any of the seven findings is missing, if the response replaces the list with counts or examples, if any item lacks the path, line, column, rule, excerpt, or suggested correction, says it edited the file, or claims complete Google style-guide compliance.
