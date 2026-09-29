# Vale AI plugin

Check documentation and source comments with [Vale](https://vale.sh) and bundled
Google style rules in **Claude Code and Codex**. The plugin includes automatic
hooks, an on-demand checking command, and shared writing and review skills.

## Install

Requires Python 3.11+, Vale 3.23+, and a client with plugin and lifecycle hook
support. Supports macOS, Linux, and Windows Subsystem for Linux. On macOS: `brew install python vale`.

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
or select it through the `/skills` slash command. Codex 0.158.0 doesn't support
custom `/prompts:vale` commands. The repository includes a legacy prompt template and installer only for older
clients that retain custom prompt support. See the
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
- **Audit scope:** use `--all` for every eligible workspace file, or
  `--check FILE --scope new-findings --base-ref main` for conservative comparison.
- **Direct checks:** run `python3 plugins/vale/scripts/prose_lint.py --check README.md`.

The checker leaves files unchanged. The agent applies requested corrections.
A project `.vale.ini` overrides the bundled Google rules. The Stop hook requests
one correction pass. Final warning visibility depends on the client. See the
[delivery limits](https://vale.swacktech.com/development.html#feedback-delivery). Vale checks an
automated subset of the Google style guide. It doesn't format Google Docs.

Automatic new-findings feedback is opt-in through project policy or the installer’s
`--feedback-scope new-findings` option. It retains initial source text locally
and falls back to full-file feedback when comparison is uncertain. See the
[scope and privacy details](https://vale.swacktech.com/behavior.html#initial-document-baselines)
and the [feature guide](https://vale.swacktech.com/features.html).

## Project policy

Use `.vale-plugin.toml` to share file selection and feedback scope across both
clients. Command options override project settings. Use `.vale.ini` and reviewed
Vale vocabulary files for terminology. Explicit Views can select OpenAPI
descriptions without checking identifiers. See the
[configuration recipes](https://vale.swacktech.com/configuration.html) for
precedence, safe exclusions, vocabulary, and format selection.

## Procedural writing

Use `/vale:procedural-prose` in Claude Code or `$vale:procedural-prose` in Codex
for runbooks and instructions. This experimental skill preserves conditions,
commands, and requirement strength. The optional `ste-inspired` profile uses
the same Google checks. It adds no Simplified Technical English enforcement or certification. See the
[profile guide](https://vale.swacktech.com/profiles.html) for activation,
project configuration, examples, rollback, and evaluation limits.

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
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/codex_smoke.py --plugin
python3 scripts/claude_smoke.py
```

CI tests Linux and macOS on Python 3.11 and 3.14, requires both optional markup
parsers, and validates both marketplace packages. Eight native jobs cover both
operating systems, four installation paths, and both feedback scopes. They check
fresh installs, local plugin updates, and unresolved Stop behavior. The smoke tests use
the real clients with local model fixtures and temporary configuration. The fixtures need no model account or API key. See the
[development guide](https://vale.swacktech.com/development.html) for details.

GitHub Actions checks pull requests and deploys the documentation only on pushes
to `main`, including pull request merges. See the [license](LICENSE). Bundled Google rules
retain their upstream license.

## Writing evaluation

The source checkout includes twelve labeled prose fixtures and an offline
validator for paired writing trials. It checks protected literals and requires
explicit semantic reviews. The real-model pilot remains unrun. See the
[writing evaluation guide](https://vale.swacktech.com/evaluation.html) for
reproducible inputs, review criteria, and evidence limits.

## Diagnostics

Run `python3 plugins/vale/scripts/prose_lint.py --doctor` to inspect the engine,
configuration, and optional markup parsers. Add `--format json` to a file check
for structured findings and incomplete-check diagnostics. Refer to the
[command documentation](https://vale.swacktech.com/usage.html) for examples.
