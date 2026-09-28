# Vale AI plugin

Check documentation and source comments with [Vale](https://vale.sh) and bundled
Google style rules in **Claude Code and Codex**. The plugin includes automatic
hooks, an on-demand checking command, and shared writing and review skills.

## Install

Requires Python 3.11+, Vale 3.23+, and a client with plugin and lifecycle hook
support. Supports macOS, Linux, and WSL. On macOS: `brew install python vale`.

### Claude

Run these commands in Claude Code:

```text
/plugin marketplace add swack-tools/vale-ai-plugin
/plugin install vale@vale
/vale:check-prose README.md
```

For a shared project installation, use the terminal:

```sh
claude plugin marketplace add swack-tools/vale-ai-plugin --scope project
claude plugin install vale@vale --scope project
```

### Codex

Run these commands in your terminal:

```sh
codex plugin marketplace add swack-tools/vale-ai-plugin
codex plugin add vale@vale
```

Start a new chat, review and trust Vale in `/hooks`, then invoke `$vale:check-prose`
or select it through the `/skills` slash command. Codex 0.158.0 does not support
custom `/prompts:vale` commands. A legacy prompt template and installer are
included only for older clients that retain custom prompt support. See the
installation guide for that compatibility path.

[Installation guide](https://vale.swacktech.com/installation.html) ·
[Commands, skills, and examples](https://vale.swacktech.com/usage.html) ·
[Marketplace guide](https://vale.swacktech.com/marketplaces.html)

## Usage

- **Automatic checks:** observe file changes after tools run and before a turn ends.
- **Review:** `/vale:check-prose README.md review only` in Claude Code, or
  `$vale:check-prose Review README.md without editing` in Codex.
- **Write and fix:** use the `google-prose` skill to revise technical prose and
  verify it with Vale.
- **Direct checks:** run `python3 plugins/vale/scripts/prose_lint.py --check README.md`.

The checker leaves files unchanged; the agent applies requested corrections.
A project `.vale.ini` overrides the bundled Google rules. The Stop hook requests
one correction pass and then reports remaining findings. Vale checks an
automated subset of the Google style guide; it does not format Google Docs.

## Hooks without a marketplace

Clone this repo, then choose a host and scope:

```sh
python3 scripts/install.py --host codex --project /path/to/project
python3 scripts/install.py --host claude --user
```

Both hosts support `--project` and `--user`. These commands install hooks only.
They preserve other settings and back up changes. Add `--uninstall` to remove
Vale. Use one installation method per workspace to avoid duplicate hooks.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/codex_smoke.py --plugin
python3 scripts/claude_smoke.py
```

The smoke tests use the real clients with local model fixtures and temporary
configuration. No model account or API key is required. See the
[development guide](https://vale.swacktech.com/development.html) for details.

GitHub Actions checks pull requests and deploys the documentation only on pushes
to `main`, including pull request merges. MIT license; bundled Google rules
retain their upstream license.
