---
name: rewrite-prose
description: Apply Vale's recommended prose corrections to saved documentation, then verify the edits. Use for requested prose rewrites or bulk Markdown cleanup.
---

# Rewrite technical prose

Use this skill when the user asks to apply Vale recommendations or rewrite
prose and verify the result. Resolve `../../scripts/prose_lint.py` relative to
this skill and use its absolute path. Run the checker from the workspace root
so a project `.vale.ini` can override the bundled profile.

## Select files

Use the user's requested scope exactly. For “all Markdown files,” enumerate
only `*.md` and `*.mdx` files, including hidden files while respecting ignore
rules. Exclude dependency and generated output directories unless the user
includes them. Use null-delimited path handling, then call the checker with
explicit `--check FILE...` operands in manageable batches. Don't use `--all`
for a Markdown-only request. That mode can include source files and comments.
If no Markdown files match, report that and stop.

For named files, check only those files. For a directory, enumerate supported
files within that directory. Don't expand a narrower request to the whole
workspace.

## Apply findings

Run the checker with `--format json` and inspect every finding. Apply Vale's
suggested replacement when the finding provides one and the replacement
preserves the sentence's technical meaning. Read the surrounding paragraph
before editing. Apply direct spelling, punctuation, capitalization, and
word-choice corrections where context confirms them. When a finding needs a
sentence rewrite or Vale provides no safe replacement, revise only when the
intended meaning is clear. Otherwise leave it unchanged and report it for
review.

Preserve commands, code blocks, identifiers, URLs, quoted text, product names,
and technical behavior unless the user explicitly asks to change them. Don't
weaken Vale rules or add vocabulary exceptions to make the check pass. Don't
claim that you applied every recommendation if a finding was ambiguous or you
skipped a file.

## Verify and report

Rerun Vale on every file you changed. Report the files changed, findings
resolved, and unresolved findings. For a Markdown report or a long results
set, offer or create a report with one row per finding and columns for file,
line, rule, original text, suggested change, and status. Never replace a
requested list of findings with aggregate counts or selected examples.

Follow the `check-prose` skill for incomplete checks, comparison scope,
coverage caveats, and skipped-file handling. A clean result covers configured
rules. It doesn't certify complete Google style-guide compliance.
