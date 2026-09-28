---
name: google-prose
description: Write or revise technical documentation and source comments using Google developer documentation style, then verify the prose with Vale.
---

# Write and revise prose

Use this skill when writing or revising technical prose, including README files,
guides, and source comments. Follow the user's requested scope and terminology.

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

Resolve `../../scripts/prose_lint.py` relative to this skill's directory and use
its absolute path. Run from the user's workspace. Don't assume plugin
environment variables exist in shell tools. A project `.vale.ini` overrides the bundled
policy. Don't turn off a rule or weaken that policy merely to pass a check.
If a finding needs an editorial exception, explain it and follow the user's
project conventions.

The checker doesn't certify the entire Google style guide. Report unresolved
findings or an unavailable checker explicitly. Don't format Google Docs files
or apply a source-code formatter as part of this skill.

A project `.vale-plugin.toml` also controls selection and scope. Use `--doctor
--format json` to inspect effective settings when needed. If the selected scope
is `new-findings`, ask for an explicit Git revision before verification. Don't
invent a baseline or silently override the scope. Follow the companion
`check-prose` skill for comparison commands and result handling. Report skipped
files as unchecked, with their reasons. Keep reviewed vocabulary unchanged
unless the user requests a terminology policy change.
