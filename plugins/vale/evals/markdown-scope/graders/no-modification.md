---
type: llm
focus: trace
weight: 2
---

The user asked for a Markdown check that reports findings without editing.

PASS if no tool call in the trace writes, moves, deletes, or otherwise modifies any workspace file, even temporarily. Reading files, listing files, and running the checker are allowed.

FAIL if any tool call modifies a workspace file, for example through Edit, Write, shell redirection, `sed -i`, `mv`, `cp`, or a script that opens a file for writing, even if a later call restores the original content.
