---
description: Check an unsaved Markdown draft through stdin without creating files.
tags: [check-prose, draft, smoke]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Before I save this as docs/setup.md, run a Vale style check on the draft and list every finding with its line and rule. Don't create any files.

```markdown
# Setting Up The Tool

We will install the package, e.g. with pip. Simply run the installer and it will be done!
```
