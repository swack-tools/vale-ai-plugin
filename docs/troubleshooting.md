# Troubleshooting

## No feedback after an edit

Check the installation layer, then check trust:

1. Confirm that the plugin `hooks/hooks.json`, Codex `hooks.json`, or Claude Code
   `settings.json` contains Vale entries for
   `PreToolUse`, `PostToolUse`, and `Stop`.
2. Restart the client session after installation.
3. Open `/hooks` and trust the current definitions.
4. Trust the project if you installed the hooks in `.codex`.
5. Confirm that the client enables hooks and has Python and Vale on its `PATH`.

A GUI app can have a different `PATH` from your terminal. Restart it
from an environment that includes both executables, or configure the host's
app environment.

An existing `.vale.ini` takes precedence. Check its file patterns and alert
level. An error-only policy intentionally omits warnings.

## The hook reports an incomplete check

Missing Vale, invalid configuration, timeouts, and file-size limits produce
an explicit diagnostic. They don't count as a clean lint result. Install the
missing dependency or correct the configuration, then retry the check.

If project rules are missing, run `vale sync` yourself from the project root.
The bundled default rules need no synchronization.

## Feedback appears twice

Both clients run matching hooks from all active sources. Remove duplicate Vale
installations across project hooks, user hooks, and an installed plugin.
Use `/hooks` to inspect the source of each registration.

## The agent finishes with unresolved findings

The Stop hook requests one correction pass. When the client reports that the Stop
hook is already active, Vale surfaces remaining findings without another block.
This prevents an endless loop. Ask the agent to fix the remaining findings, or run
the direct checker to inspect them.

## Migrate the original hook

[PR #971](https://github.com/swack-tools/oxidex/pull/971) registered a Claude
`PostToolUse` hook for `Edit|Write`. It read `tool_input.file_path`, expected
`CLAUDE_PROJECT_DIR`, and required `jq`. It didn't observe general shell edits.

The newer local OxiDex checker has different behavior: it uses a Python script,
pre-tool snapshots for shell calls, and additional filtering. It still has
project-specific assumptions and requires matching pre-tool state for shell
attribution. A hook copied from either version needs the matching registration
and dependencies.

Vale uses the shared Codex and Claude Code event contract, snapshots all tool calls, preserves tool
output, and adds a Stop check. It uses no `jq` dependency and doesn't silently
skip missing Vale. It validates file paths against the absolute workspace root,
then passes normalized root-relative paths after `--` so project-relative Vale
patterns work and filenames can't become command options. Findings map back to
absolute paths.

Install Vale first, inspect the merged configuration, and remove only the old
prose-lint registration when migrating. Preserve unrelated hooks. If the
project already has `.vale.ini`, either retain that policy or update it
explicitly to the [new defaults](configuration.html).

## Google documentation style

The hook runs the Vale prose linter with the rules from
[vale-cli/Google](https://github.com/vale-cli/Google). The rules implement an
automated subset of the
[Google developer documentation style guide](https://developers.google.com/style/).
It doesn't format Google Docs files.

## Command or skill is missing

Install and enable the marketplace plugin, then start a new session. The manual hook installer installs hooks only. In Claude Code, use
`/vale:check-prose`. In Codex, use `$vale:check-prose` or `/skills`.

Codex 0.158.0 rejects `/prompts:vale`. Use `/skills` and select `vale:check-prose`,
or mention `$vale:check-prose` directly. The legacy installer
`scripts/install_codex_command.py` is only for older clients that still support
deprecated custom prompts. Don't assume a Claude Code command name works in
Codex.

## Stop hook feedback

If the message contains Vale findings and the agent continues with a correction,
this is the requested Stop block. Claude Code can display that continuation as a
Stop hook error. A Python traceback or missing executable is a separate failure.

## Missing markup parser

If a check reports `rst2html not found` or `asciidoctor not found`, install the
[optional parser](installation.html) and make its executable available to the
agent on `PATH`. Verify the command in the same environment as the agent.

## Incomplete checks and large reports

Run the checker with `--doctor` to inspect its engine, configuration, and parser
readiness. Use `--format json --check FILE` to distinguish `errors` from prose
`findings`. Fix configuration or dependency problems before claiming a clean
check. An empty result with unknown project coverage isn't proof that a rule
matched the file.

If hook feedback omits findings, open the reported JSON file. If saving that
report fails, the hook reports the failure instead of claiming the report exists.
After a timeout, reduce the changed batch or resolve the stalled parser. Later
events retry pending files. Don't delete active session lock files.

## New-findings mode reports old prose

Inspect `comparison.fallback_reason` in manual JSON or the fallback explanation
in hook feedback. Custom policy dependencies, changed rules, missing snapshots,
external parsers, and comparison limits can require full-file feedback. This
is conservative behavior, not evidence that every reported occurrence is new.

For hook comparisons, install the mode for all three events, restart the client,
and begin a new session before editing. A post-tool event can't recover the
original bytes after a tool changes them. Don't delete active baseline files
to suppress findings. Use a full `--check` or `--all` to audit current prose.

## JSON is clean but contains findings

In new-findings mode, `status` reflects `comparison.actionable_indexes`.
The raw array includes matched existing findings. Report the counts and scope.
Use the default scope for a full-file audit. An error always takes precedence
over a clean comparison.
