---
name: check-prose
description: Use when checking saved documentation, unsaved drafts, or source comments with Vale and verifying requested prose corrections.
---

# Check technical prose

Use this skill for an explicit style check or when the user asks to verify prose
after editing. Apply requested corrections to findings with this skill. For
broader writing or editorial restructuring, use the companion `google-prose` skill.

Resolve the checker at `../../scripts/prose_lint.py` relative to this skill's
directory. Use the absolute resolved script path. Don't assume the plugin cache
is in the workspace or that plugin environment variables exist in shell tools.
Run from the user's workspace so its `.vale.ini` can override the bundled rules.

For unsaved prose, use the draft workflow below. For saved prose, check named files. Otherwise use the relevant prose
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

When the user asks to “report findings,” “list findings,” or asks what to
change, report every actionable finding from the selected files. Include the
relative path, line, column when available, rule, excerpt, and a specific
suggested correction. Don't substitute rule
counts, top examples, or the files with the most findings for the finding list.
For a generated Markdown report or a long findings list, use a Markdown table
with one row per finding and columns for file, line, rule, excerpt, and suggested
change. Keep each finding separate so readers can locate and act on it. If a
table would be unwieldy for a short chat response, use a compact list instead.
When the results contain hundreds of findings, ask whether the user wants a
Markdown report saved in the workspace. If they do, create a table with one row
per finding and link the report in the response. Otherwise, provide the complete
list in numbered batches.
If the result is too long for one response, group findings by file and deliver
the complete list in numbered batches. State the total and which batch the
response contains, then continue until you cover all findings. You may first give a
brief summary, but it must accompany the complete list, not replace it.

For structured results, add `--format json`. Exit `2` and status `incomplete`
indicate configuration, parser, or execution errors, which need diagnosis
rather than prose edits. Use `--doctor` to inspect the selected engine and
configuration. `submitted_files` doesn't prove rule coverage. Project coverage
can be unknown even when the result has no findings. If hook feedback omits
findings, read the full JSON report at its reported path before claiming the
review is complete.

## Choose a check scope

Use `--all` only when the user requests a full workspace audit across every
eligible prose file. It can include source files and source comments. It does
not mean every file of a user-specified type.

When the user names an extension such as “all Markdown files,” enumerate only
matching files and pass those paths to `--check`. Don't use `--all` for a
type-limited request. Include tracked and non-ignored untracked files. Exclude
generated or dependency directories such as `.git`, `node_modules`, and build
output unless the user explicitly includes them. For Markdown, use Python's
standard library to run `git ls-files --cached --others --exclude-standard -z`
from the workspace root, split its output at each zero byte, and keep paths whose
suffix lowercased is `.md` or `.mdx`. This includes uppercase and mixed-case
extensions and honors Git ignore rules. In a non-Git workspace, use Python's
`os.walk`, include hidden files, prune generated and dependency directories,
and report that Git ignore rules aren't available. Pass paths through a safe
argument array. If a root-level filename starts with a hyphen, prefix it with
`./`. If no files match, say so and don't run `--all`.

For a named directory request, identify the supported files, then check each
with `--check FILE...`. For a request covering all workspace files with no type
restriction, use `--all`.

For new findings in named files, require an explicit Git baseline:

```sh
python3 /absolute/plugin/scripts/prose_lint.py --check ./guide.md --scope new-findings --base-ref main --format json
```

Use the user's requested revision. Ask for it if absent. Never choose a session
from state filenames. This mode requires Git and doesn't combine with `--all`.
The bundled `changed-files` default reports every finding in the selected files.
A project `.vale-plugin.toml` can select `new-findings`. Inspect effective
settings and their origins with `--doctor --format json` when scope is unclear.
Ask for a missing baseline even when the project selected comparison mode.

Comparison JSON retains all raw `findings`. Only indexes in
`comparison.actionable_indexes` affect findings status and exit code `1`.
Report `comparison.fallback_reason` when present. A fallback keeps full-file
findings actionable. Zero new findings doesn't mean zero existing findings or
complete Google style compliance. For a full audit, run `--all` without a baseline.

A `skipped` result or an entry in `skipped_files` means the wrapper didn't check
that operand. Report the path and reason, even when other files passed. Don't
call an excluded document clean or bypass its policy. Reviewed vocabulary and
format recipes live in the [configuration guide](https://vale.swacktech.com/configuration.html).
Don't add accepted terms or weaken exclusions just to clear findings.

## Check an unsaved draft

Use `--stdin --ext md|txt|rst|adoc|html --format json` with the resolved checker.
Run from the workspace. Pass draft bytes through subprocess input or a quoted
heredoc whose delimiter doesn't occur in the draft. Never interpolate prose
into shell code or create a staging file.

Derive the logical target from the user's request. If project rules depend on
paths and the target is missing, ask for it before checking. Pass that target
with `--path docs/setup.md`. It selects rules without reading or writing the
file. Otherwise the default is `draft.<ext>`. Match the declared extension.
Use `--path=-draft.md` for a name that starts with a hyphen.

```sh
python3 /absolute/plugin/scripts/prose_lint.py --stdin --ext md --path docs/setup.md --format json <<'VALE_DRAFT'
Use this, e.g. for testing.

Run `printf "$HOME"`.
VALE_DRAFT
```

Report the virtual `<stdin:docs/setup.md>` identity, lines, rules, status, and
coverage caveat. Exit codes are `0` for no findings, `1` for findings, and `2`
for incomplete or skipped checks. An empty valid draft has no findings.
Input must be UTF-8 and at most 1 MiB. reStructuredText and AsciiDoc require their usual
parsers. Selection exclusions and profile/configuration precedence still apply.

Draft checks use the complete supplied text, even if the project selects new
findings. Don't supply a Git baseline or combine draft mode with other manual
modes. For requested fixes, preserve commands and technical meaning, revise only
the draft, and submit it again. Report rule counts before and after. The workflow creates no hook
state or user file and doesn't automatically check assistant replies.

Saved files and drafts use normalized root-relative identities for project
patterns, so `[docs/*.md]` can match both. The checker still resolves and
validates saved files against the absolute workspace root and returns absolute
file locations. Don't change project rules silently or claim an unmatched
empty result proves coverage. See the
[draft guide](https://vale.swacktech.com/usage.html#check-an-unsaved-draft).
