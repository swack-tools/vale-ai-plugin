# Marketplace distribution

## One repository, two catalogs

This repository is a marketplace for both clients. It follows the same
repository layout as
[Trakt AI plugin](https://github.com/swack-tools/trakt-ai-plugin).
You don't need a separate organization marketplace to install Vale.

| Client | Catalog | Plugin manifest |
| --- | --- | --- |
| Codex | `.agents/plugins/marketplace.json` | `plugins/vale/.codex-plugin/plugin.json` |
| Claude Code | `.claude-plugin/marketplace.json` | `plugins/vale/.claude-plugin/plugin.json` |

Both catalogs use the name `vale` and point to `./plugins/vale`. The install
identifier is `vale@vale`: plugin name, then marketplace name. The package
contains the checker, pinned Google rules, shared hooks, and two skills. It
requires no Model Context Protocol server, hosted service, OAuth 2.0 connection, or API key.

These are repository marketplaces. Publishing them doesn't list Vale in a
client's official curated marketplace.

## Add the repository

Claude Code:

```text
/plugin marketplace add swack-tools/vale-ai-plugin
/plugin install vale@vale
```

Codex terminal:

```sh
codex plugin marketplace add swack-tools/vale-ai-plugin
codex plugin add vale@vale
```

See [installation](installation.html) for dependencies, trust, and project scope.
To try unpublished changes, replace the GitHub source with the absolute path to
your local repository in the marketplace add command. Start a new session after
installing the changed package.

## Updates and removal

Claude Code terminal:

```sh
claude plugin marketplace update vale
claude plugin update vale@vale
# Remove the user installation:
claude plugin uninstall vale@vale --scope user
```

Use `--scope project` for a project installation. Keep its marketplace settings
if other team members still use them.

Codex terminal:

```sh
codex plugin marketplace upgrade vale
codex plugin add vale@vale
# Remove the plugin:
codex plugin remove vale@vale
```

Restart the client after an update and review changed hooks when requested.
The legacy Codex prompt has a separate lifecycle: rerun its installer after
pulling updates, or remove it with `--uninstall`.

## Add Vale to a future organization marketplace

Copy the complete `plugins/vale` directory. Keep both manifests, the bundled
rules and license, and the relative paths. Add a catalog entry for each client
that points to the package's location in the new repository. Use that
marketplace's name after `@` when installing.

Keep one active Vale installation per workspace. A manual hook installation and
an enabled marketplace plugin both register hooks. Neither replaces the other.

## Host compatibility

Both clients discover `hooks/hooks.json`. It uses the quoted
`CLAUDE_PLUGIN_ROOT` path. Claude Code defines that variable for plugin hooks.
Codex also defines it for compatibility. The runtime emits shared event JSON
for `PreToolUse`, `PostToolUse`, and `Stop`.

Skills resolve the checker relative to their own installed path. They don't
assume that plugin environment variables are available inside tools run by the
agent. Claude Code exposes skills as slash commands. Codex uses skill mentions.
Older clients that still support custom prompts can use the `/prompts:vale`
wrapper. Codex 0.158.0 rejects that legacy command. Use `/skills` or
`$vale:check-prose` instead.

References include [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins),
[Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference),
[Claude Code skills](https://code.claude.com/docs/en/skills), and
[Codex custom prompts](https://developers.openai.com/codex/custom-prompts).
