---
type: llm
focus: {source: file, path: README.md}
weight: 2
---

The original README said: "We will install the agent with `tool install --version 2.0`, e.g. on a build server." followed by a shell code block containing `printf 'We will retry, e.g. later.'` and the sentence "The agent will automatically restart if it crashes."

PASS if the revised README keeps the same technical meaning, keeps the inline command and the code block byte-for-byte, replaces the prose "e.g." with plain English, removes first-person "We" and unnecessary "will" from the prose, and uses a sentence-case heading.

FAIL if any command or code block changed, if the meaning changed (for example, the restart behavior disappeared), or if "e.g." still appears outside code.
