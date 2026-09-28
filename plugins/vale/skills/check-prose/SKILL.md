---
name: check-prose
description: Check documentation and source comments with Vale, report Google style findings, and verify requested prose corrections.
---

# Check technical prose

Use this skill for an explicit style check or when the user asks to verify prose
after editing. For writing and editorial corrections, use the companion
`google-prose` skill.

Resolve the checker at `../../scripts/prose_lint.py` relative to this skill's
directory. Use the absolute resolved script path. Don't assume the plugin cache
is in the workspace or that plugin environment variables exist in shell tools.
Run from the user's workspace so its `.vale.ini` can override the bundled rules.

If the user names files, check those files. Otherwise use the relevant prose
files edited in the conversation. If neither is available, ask for the scope.
Pass each file as a separate quoted argument, with a `./` prefix for names that
start with a hyphen. Don't interpolate the user's prose as shell code.

```sh
python3 /absolute/plugin/scripts/prose_lint.py --check ./README.md ./docs/guide.md
```

The checker accepts files, not directories. For a directory request, list its
supported files first and check them in batches. It skips symlinks and requires
files inside the workspace. Report unsupported paths instead of silently
treating them as checked.

For a review request, report file, line, rule, and a concise correction without
editing. When the user requests fixes, preserve technical meaning and examples,
edit the affected prose, and rerun the checker. Don't turn off rules to obtain a
clean result. Report remaining findings and unavailable dependencies separately
from clean checks. A clean result covers the configured rules, not the entire
Google style guide.

For structured results, add `--format json`. Exit `2` and status `incomplete`
indicate configuration, parser, or execution errors, which need diagnosis
rather than prose edits. Use `--doctor` to inspect the selected engine and
configuration. `submitted_files` doesn't prove rule coverage. Project coverage
can be unknown even when the result has no findings. If hook feedback omits
findings, read the full JSON report at its reported path before claiming the
review is complete.

## Choose a check scope

Use `--all` only when the user requests a full workspace audit. It enumerates
eligible files under the same exclusions as hooks. Keep `--check FILE...` for
named files or a requested directory's enumerated files.

For new findings in named files, require an explicit Git baseline:

```sh
python3 /absolute/plugin/scripts/prose_lint.py --check ./guide.md --scope new-findings --base-ref main --format json
```

Use the user's requested revision. Ask for it if absent. Never choose a session
from state filenames. This mode requires Git and doesn't combine with `--all`.
The default `changed-files` scope reports every finding in the selected files.

Comparison JSON retains all raw `findings`. Only indexes in
`comparison.actionable_indexes` affect findings status and exit code `1`.
Report `comparison.fallback_reason` when present. A fallback keeps full-file
findings actionable. Zero new findings doesn't mean zero existing findings or
complete Google style compliance. For a full audit, run `--all` without a baseline.
