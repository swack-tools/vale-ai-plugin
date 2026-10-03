---
type: llm
focus: last_message
weight: 2
---

PASS if the final installation section uses a sentence-case heading, second person or imperative instructions, present tense, no Latin abbreviations (such as "e.g." or "i.e.") in prose, includes `pipx install quill-cli` in a code block, and states the Python 3.10 or later requirement.

FAIL if the section uses first-person plural ("we"), future tense to describe current behavior, Latin abbreviations in prose, a title-case heading, or omits the command or the Python requirement.
