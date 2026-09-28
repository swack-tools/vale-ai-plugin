# Troubleshooting

## No feedback after an edit

Check the installation layer, then check trust:

1. Confirm that the plugin `hooks/hooks.json`, Codex `hooks.json`, or Claude Code
   `settings.json` contains Vale entries for
   `PreToolUse`, `PostToolUse`, and `Stop`.
2. Restart the client session after installation.
3. Open `/hooks` and trust the current definitions.
4. Trust the project if the hooks are installed in `.codex`.
5. Confirm that hooks are enabled and that Python and Vale are on the client's `PATH`.

A GUI app can have a different `PATH` from your terminal. Restart it
from an environment that includes both executables, or configure the host's
app environment.

An existing `.vale.ini` takes precedence. Check its file patterns and alert
level; an error-only policy intentionally omits warnings.

## The hook reports an incomplete check

Missing Vale, invalid configuration, timeouts, and file-size limits produce
an explicit diagnostic. They do not count as a clean lint result. Install the
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
`CLAUDE_PROJECT_DIR`, and required `jq`. It did not observe general shell edits.

The newer local OxiDex checker has different behavior: it uses a Python script,
pre-tool snapshots for shell calls, and additional filtering. It still has
project-specific assumptions and requires matching pre-tool state for shell
attribution. A hook copied from either version needs the matching registration
and dependencies.

Vale uses the shared Codex and Claude Code event contract, snapshots all tool calls, preserves tool
output, and adds a Stop check. It uses no `jq` dependency and does not silently
skip missing Vale. It passes absolute file paths after `--` to protect filenames
that resemble command options.

Install Vale first, inspect the merged configuration, and remove only the old
prose-lint registration when migrating. Preserve unrelated hooks. If the
project already has `.vale.ini`, either retain that policy or update it
explicitly to the [new defaults](configuration.html).

## Google documentation style

The hook runs the Vale prose linter with the rules from
[vale-cli/Google](https://github.com/vale-cli/Google). The rules implement an
automated subset of the
[Google developer documentation style guide](https://developers.google.com/style/).
It does not format Google Docs files.

## Command or skill is missing

Confirm that the marketplace plugin is installed and enabled, then start a new
session. The manual hook installer installs hooks only. In Claude Code, use
`/vale:check-prose`. In Codex, use `$vale:check-prose` or `/skills`.

For `/prompts:vale`, run `scripts/install_codex_command.py` after installing the
Codex plugin. Custom prompt support is deprecated; use the skill if your client
does not expose that command. Do not assume a Claude Code command name works in
Codex.

## Stop hook feedback

If the message contains Vale findings and the agent continues with a correction,
this is the requested Stop block. Claude Code can display that continuation as a
Stop hook error. A Python traceback or missing executable is a separate failure.
