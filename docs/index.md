# Clear docs in your editing loop

Vale brings Google documentation style checks into Codex. Write your docs,
change a comment, or run a tool that edits a file. Vale checks the changed prose
and returns findings while Codex still has the context to fix them.

[Install Vale](installation.html) · [Browse the source](https://github.com/swack-tools/vite-ai-plugin)

## Three steps, one editing loop

1. **Observe.** Before the first tool runs, record the workspace file state.
2. **Check.** After tools finish, run Vale on files whose state changed.
3. **Finish.** Before Codex stops, check the files touched during the session.

Shell scripts, patches, and MCP tools can all change files. Vale observes the
local result, so the checker does not need to guess what a shell command does.

## Choose your scope

| Install for | Command | Result |
| --- | --- | --- |
| A project | `python3 scripts/install.py --project /path/to/project` | Hooks and runtime in the project's `.codex` directory |
| Your user | `python3 scripts/install.py --user` | Hooks and runtime in `CODEX_HOME`, or `~/.codex` |

Choose one scope for a workspace. Codex combines hooks from project, user, and
plugin sources; installing several copies can duplicate feedback.

## A focused checker

The default configuration uses Vale and 36 bundled Google rules. It reports
warnings and errors and disables spelling checks. Source files use Vale's
syntax support to check prose comments. Markdown code blocks remain code.

Vale does not rewrite files itself. It gives Codex the findings, then checks the
result. It checks the rules in Vale's Google package, not every recommendation
in the full style guide. It does not edit Google Docs documents.

## Start here

- [Installation](installation.html): dependencies, project and user setup, and removal.
- [How it works](behavior.html): hook events, file selection, and limits.
- [Configuration](configuration.html): style settings and project overrides.
- [Troubleshooting](troubleshooting.html): trust, missing tools, and migration.
- [Development](development.html): tests and the documentation release process.
