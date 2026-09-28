---
name: google-prose
description: Resolve Vale or Vale findings in documentation and source comments using Google developer documentation style.
---

# Resolve prose findings

Use the path, line, rule name, and message from Vale to locate each finding.
Read the surrounding paragraph or comment before changing it. Preserve technical
meaning, quoted text, URLs, identifiers, and executable code.

Prefer active voice, direct instructions, and sentence case headings. Replace
Latin abbreviations with plain English. Remove unnecessary future tense and
first-person plural when the passage describes current behavior.

Run the package checker from the workspace root to verify the affected files:

```sh
python3 /path/to/vale/scripts/prose_lint.py --check docs/example.md
```

Resolve the script relative to this skill's plugin root or use the installed
`.codex/vale/scripts/prose_lint.py`. A project `.vale.ini` overrides the bundled
policy. Do not turn off a rule or weaken that policy merely to pass a check.
If a finding needs an editorial exception, explain it and follow the user's
project conventions.

The checker does not certify the entire Google style guide. Report unresolved
findings or an unavailable checker explicitly. Do not format Google Docs files
or apply a source-code formatter as part of this skill.
