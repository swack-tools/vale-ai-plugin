---
type: llm
focus: trace
weight: 2
---

The user asked for a draft check without creating any files.

PASS if no tool call in the trace creates, writes, or copies a file, including temporary files that a later call deletes. Passing the draft through stdin, a quoted heredoc, or subprocess input is allowed.

FAIL if any tool call writes the draft or other content to a file, for example through the Write tool, shell redirection such as `>` or `tee` to a path, `mktemp`, or a script that opens a file for writing.
