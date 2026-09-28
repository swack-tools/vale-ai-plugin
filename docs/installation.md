# Installation

## Requirements

Install Python 3.11+, Vale 3.23+, and Claude Code or Codex with plugin and
lifecycle hook support. The runtime supports macOS, Linux, and Windows Subsystem for Linux. Native
Windows isn't supported because state locking uses `fcntl`.

Tested with Codex 0.158.0, Claude Code 2.1.277, and Vale 3.23.0. Hooks run on the
machine that holds the workspace. Install Python and Vale there.

```sh
# macOS
brew install python vale
python3 --version
vale --version
```

### Optional markup parsers

Markdown and source comments use Vale's built-in parsers. Install these tools
only if your project uses the corresponding markup format:

| Format | Package | Required command |
| --- | --- | --- |
| reStructuredText: `.rst` | Python Docutils | `rst2html` |
| AsciiDoc: `.adoc` | Ruby Asciidoctor | `asciidoctor` |

Install Docutils in a Python environment available to the agent:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install docutils
export PATH="$PWD/.venv/bin:$PATH"
rst2html --version
```

With Ruby installed, install Asciidoctor:

```sh
gem install asciidoctor
asciidoctor --version
```

Ensure the agent's process inherits the parser commands on `PATH`. Restart the
agent after changing its environment. A missing parser prevents that format's
check from completing. It doesn't mean the document has no findings.

For Linux and Windows Subsystem for Linux, use the [Vale installation guide](https://vale.sh/docs/install).
Vale needs no account or API key. Review the package scripts before enabling
hooks. Choose one installation method per workspace to avoid duplicate feedback.

## Claude plugin

In Claude Code:

```text
/plugin marketplace add swack-tools/vale-ai-plugin
/plugin install vale@vale
```

Or use the terminal to select a scope. User scope is the default:

```sh
claude plugin marketplace add swack-tools/vale-ai-plugin
claude plugin install vale@vale --scope user
```

For a project shared with your team:

```sh
claude plugin marketplace add swack-tools/vale-ai-plugin --scope project
claude plugin install vale@vale --scope project
```

Review the resulting `.claude/settings.json` before committing it. Restart
Claude Code and inspect `/hooks`. The plugin provides three hooks and two skills:
`/vale:check-prose` and `/vale:google-prose`. Skills also support automatic
selection when your request matches their purpose.

## Codex plugin

In your terminal:

```sh
codex plugin marketplace add swack-tools/vale-ai-plugin
codex plugin add vale@vale
```

Start a new chat. Open `/hooks` to review and trust Vale's definitions. Trust
project configuration when prompted. If hooks are off, start Codex with
`codex --enable hooks`.

Invoke `$vale:check-prose` or `$vale:google-prose`, or select the skill through `/skills`.
Codex manages the plugin installation through your user configuration.
For a portable project hook installation, use the installer below.

### Legacy slash command compatibility

Codex 0.158.0 doesn't recognize `/prompts:vale`. Use the `/skills` slash command
and select `vale:check-prose`, or mention `$vale:check-prose` directly.

For older clients that still support deprecated custom prompts, this repository
includes a legacy template and installer:

```sh
git clone https://github.com/swack-tools/vale-ai-plugin.git
cd vale-ai-plugin
python3 scripts/install_codex_command.py
```

On a compatible legacy client, start a new chat and run
`/prompts:vale README.md review only`. The command
invokes the installed plugin's checking skill. Install the Codex plugin first.
The installer writes `$CODEX_HOME/prompts/vale.md`, or
`~/.codex/prompts/vale.md`, and refuses to replace an unrelated command.
The template isn't a supported command on the tested Codex 0.158.0 runtime.
Custom prompts are user-scoped. They don't travel with a project checkout.

## Project or user hooks without a marketplace

Clone the package if you haven't already done so:

```sh
git clone https://github.com/swack-tools/vale-ai-plugin.git
cd vale-ai-plugin
```

Choose one command:

```sh
python3 scripts/install.py --host codex --project /path/to/project
python3 scripts/install.py --host codex --user
python3 scripts/install.py --host claude --project /path/to/project
python3 scripts/install.py --host claude --user
```

The default host is Codex for compatibility with earlier releases. This method
installs the runtime and hooks only. Use the marketplace for discoverable skills
and commands.

| Host | Project configuration | User configuration |
| --- | --- | --- |
| Codex | `.codex/hooks.json` and `.codex/vale/` | `$CODEX_HOME`, or `~/.codex` |
| Claude Code | `.claude/settings.json` and `.claude/vale/` | `$CLAUDE_CONFIG_DIR`, or `~/.claude` |

The installer preserves other hooks and settings and backs up the configuration
before each update. For Codex it creates `config.toml` only if the file is
missing. Project commands resolve their runtime from the current directory or
an ancestor, so they work after moving the checkout and from subdirectories.
The copied runtime doesn't depend on the original clone.

Commit the installed runtime and configuration to share project hooks. Don't
commit backup files. Restart your client and review `/hooks`. Codex requires
explicit trust for new or changed hook definitions.

## Verify your setup

In a temporary Markdown file, ask your agent to write:

```text
We will use this, e.g. for testing.
```

Expect findings such as `Google.Latin`. Replace the sentence with
`Use this file for testing.` and check again. For a direct check from the
workspace root after a project hook installation:

```sh
python3 .codex/vale/scripts/prose_lint.py --check README.md
# Claude Code project installation:
python3 .claude/vale/scripts/prose_lint.py --check README.md
```

For plugin installations, use the checking skill. It resolves the installed
runtime path. See [usage examples](usage.html).

## Update or remove

For marketplace plugin updates and removal, see the
[marketplace guide](marketplaces.html#updates-and-removal).

For manual hooks, pull the source repository. Repeat the original install
command. To remove them, add `--uninstall` with the same host and scope:

```sh
python3 scripts/install.py --host claude --project /path/to/project --uninstall
python3 scripts/install.py --host codex --user --uninstall
python3 scripts/install_codex_command.py --uninstall
```

Removal preserves unrelated configuration and backups. Session state remains.
See [state storage](behavior.html#state-storage) for cleanup instructions.

## Enable automatic new-findings feedback

Marketplace hooks and manual installations read `.vale-plugin.toml` from each
workspace. To enable comparison for either client, add this project setting:

```toml
scope = "new-findings"
```

For a hook-only installation, an explicit installer option takes precedence
over project scope:

```sh
python3 scripts/install.py --host codex --project /path/to/project --feedback-scope new-findings
python3 scripts/install.py --host claude --user --feedback-scope new-findings
```

Both hosts support this option for both project and user installations. Choose
one command and avoid duplicate marketplace hooks. The installer adds
`--scope new-findings` to all three event commands and preserves its ownership
marker. It also forwards the option through portable project launchers.

Restart the client and trust the updated hooks. A fresh session captures the
initial documents before editing. Read the [source-text retention and limits](behavior.html#initial-document-baselines)
before enabling this mode. It's most useful with the bundled Google policy.
Custom project policies keep full-file feedback.

Repeat an explicit `--feedback-scope` when updating to retain that override.
Omitting it restores project policy, or `changed-files` when no project scope
exists. Use `--feedback-scope changed-files` to force full-file feedback even
when the project selects comparison. Changing scope during an active
session doesn't reconstruct its original source text. Start a new session.

For a locally maintained plugin package, the equivalent hook command is:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" --scope new-findings
```

Apply it to `PreToolUse`, `PostToolUse`, and `Stop`. Keep local package changes
under your own version control. A marketplace update can replace them.
Manual skill comparisons also read project scope. An explicit command option
takes precedence. Manual comparisons always require a Git reference.
