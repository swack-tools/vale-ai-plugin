# Clear prose in your editing workflow

Vale brings Google documentation style checks into your editing workflow.
Install the plugin in Claude Code or Codex to get automatic checks, an
on-demand checking command, and shared writing skills.

[Install Vale](installation.html) · [Try the examples](usage.html) ·
[Browse the source](https://github.com/swack-tools/vale-ai-plugin)

## Three ways to use Vale

| Need | Use |
| --- | --- |
| Check edits while you work | Automatic pre-tool, post-tool, and Stop hooks |
| Review selected files | `check-prose` skill and command |
| Write or improve technical prose | `google-prose` skill |
| Revise a runbook procedure | `procedural-prose` skill |

Claude Code exposes `/vale:check-prose`, `/vale:google-prose`, and
`/vale:procedural-prose`. Codex accepts `$vale:check-prose`,
`$vale:google-prose`, and `$vale:procedural-prose` skill mentions or the
`/skills` picker. The repository also has a legacy `/prompts:vale` template for
older Codex clients that support custom prompts. It isn't a current standalone
command. Codex 0.158.0 uses the skill interfaces.

## One package for both clients

The repository includes marketplaces for Claude Code and Codex. Add
`swack-tools/vale-ai-plugin` and install `vale@vale`. Choose Claude Code project
or user scope, Codex's plugin installation, or the manual project and user hook
installers. See the [installation guide](installation.html).

Use one installation method per workspace. Both clients can combine hooks from
multiple sources, which can duplicate feedback.

## Automatic checks in your editing loop

1. **Observe.** Before the first tool runs, record the workspace file state.
2. **Check.** After tools finish, run Vale on files whose state changed.
3. **Finish.** Before the agent stops, check files touched during the session.

Shell scripts, patches, editors, and Model Context Protocol tools can all change local files. Vale
observes the result without guessing what a shell command does.

## A focused checker

The default configuration uses 36 bundled Google rules. It reports warnings and
errors and disables spelling checks. Source files use Vale's syntax support to
check prose comments. Markdown code blocks remain code.

Vale leaves files unchanged and gives the agent findings to resolve. It checks
an automated subset of the Google style guide and doesn't format Google Docs.
An existing project `.vale.ini` takes precedence over the bundled configuration.

## Explore the documentation

- [Installation](installation.html): dependencies, marketplaces, scopes, and removal.
- [Usage](usage.html): commands, skills, and examples.
- [Marketplaces](marketplaces.html): distribution, updates, and client compatibility.
- [How it works](behavior.html): hook events, file selection, and limits.
- [Configuration](configuration.html): style settings and project overrides.
- [Troubleshooting](troubleshooting.html): trust, missing tools, and migration.
- [Development](development.html): tests and the documentation release process.
