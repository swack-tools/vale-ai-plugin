---
name: check-prose
description: Check documentation and source comments with Vale, report Google style findings, and verify requested prose corrections.
---

# Check technical prose

Use this skill for an explicit style check or when the user asks to verify prose
after editing. For writing and editorial corrections, use the companion
`google-prose` skill.

Resolve the checker at `../../scripts/prose_lint.py` relative to this skill's
directory. Use the absolute resolved script path; do not assume the plugin cache
is in the workspace or that plugin environment variables exist in shell tools.
Run from the user's workspace so its `.vale.ini` can override the bundled rules.

If the user names files, check those files. Otherwise use the relevant prose
files edited in the conversation. If neither is available, ask for the scope.
Pass each file as a separate quoted argument, with a `./` prefix for names that
start with a hyphen. Do not interpolate the user's prose as shell code.

```sh
python3 /absolute/plugin/scripts/prose_lint.py --check ./README.md ./docs/guide.md
```

The checker accepts files, not directories. For a directory request, list its
supported files first and check them in batches. It skips symlinks and requires
files inside the workspace. Report unsupported paths instead of silently
treating them as checked.

For a review request, report file, line, rule, and a concise correction without
editing. When the user requests fixes, preserve technical meaning and examples,
edit the affected prose, and rerun the checker. Do not turn off rules to obtain a
clean result. Report remaining findings and unavailable dependencies separately
from clean checks. A clean result covers the configured rules, not the entire
Google style guide.
