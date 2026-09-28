# Installation

## Requirements

Use Python 3.11 or later, Vale 3.23 or later, and a Codex version that supports
`PreToolUse`, `PostToolUse`, and `Stop` hooks. The runtime supports macOS, Linux,
and WSL. Native Windows is not supported because state locking uses `fcntl`.

The package is tested with Codex command-line tool 0.158.0 and Vale 3.23.0. Desktop and IDE
clients must use a hook-capable Codex runtime. Hooks must execute on the machine
that holds the workspace and has Python and Vale installed.

On macOS:

```sh
brew install python vale
```

For Linux and WSL, follow the [Vale installation guide](https://vale.sh/docs/install).
Verify the executables in the same environment that runs Codex:

```sh
python3 --version
vale --version
codex --version
```

## Get the package

```sh
git clone https://github.com/swack-tools/vale-ai-plugin.git
cd vale-ai-plugin
```

Review the scripts before installing hooks. Installation needs no API key,
account, or network access after you have the package and dependencies.

## Install for a project

```sh
python3 scripts/install.py --project /path/to/project
```

The installer copies the package into `.codex/vale` and merges three registrations
into `.codex/hooks.json`. It creates `.codex/config.toml` if none exists and
preserves existing configuration files. It backs up the previous hooks file.

Commit `.codex/vale`, `.codex/hooks.json`, and the configuration file to share
the setup. The hook command resolves the project at runtime, so it does not
contain the installer's absolute path. Do not commit backup files.

## Install for your user

```sh
python3 scripts/install.py --user
```

This installs into `$CODEX_HOME` when set, or `~/.codex` otherwise. Each workspace
gets its own file state. Your user installation can check projects without
adding a tracked hook to each project.

The installer copies the runtime, so moving or removing the source clone does
not break an existing installation. User installations apply to local files
within the current session workspace.

## Activate the hooks

1. Restart Codex so it loads the new configuration.
2. Trust the project if you installed project hooks.
3. Open `/hooks` in the Codex command-line tool and review and trust the Vale definitions.
4. If hooks are off in your configuration, run `codex --enable hooks`.

Codex requires trust for new or changed hook definitions. An installed file or
an enabled feature flag alone does not prove that hooks run. See the
[Codex hook guide](https://learn.chatgpt.com/docs/hooks).

## Verify your setup

In a temporary Markdown file, ask Codex to write this sentence:

```text
We will use this, e.g. for testing.
```

Vale should report `Google.Latin` and other findings. Ask Codex to replace the
sentence with `Use this file for testing.` The check should then pass.

For a direct check without a chat, run from the project root:

```sh
python3 .codex/vale/scripts/prose_lint.py --check README.md
```

For a user installation, replace the script path with
`"${CODEX_HOME:-$HOME/.codex}/vale/scripts/prose_lint.py"`.

## Update or remove

Pull the source repository, then repeat the install command to update. Repeated
installation replaces only the Vale package and its registrations. Review the
updated definitions in `/hooks` when Codex requests it.

```sh
python3 scripts/install.py --project /path/to/project --uninstall
# Or remove the user installation:
python3 scripts/install.py --user --uninstall
```

Removal preserves other hooks, backups, and `config.toml`. It also preserves
session state; see [state storage](behavior.html#state-storage) for cleanup.

## Plugin packaging

The self-contained package lives at `plugins/vale`, with a Codex manifest,
`hooks/hooks.json`, a writing skill, the runtime, and bundled rules. It can move
into a future organization marketplace without changing the runtime layout.
The project and user installers do not require a marketplace.
