# Vale

Vale checks documentation and code comments after Codex tools run and before a
chat turn finishes. It uses [Vale](https://vale.sh) and bundled Google style rules.
It works with patches, shell commands, and tools that change local files.

## Install

Requires Python 3.11+, Vale 3.23+, and Codex with lifecycle hooks. Supports macOS,
Linux, and WSL. Tested with Codex command-line tool 0.158.0 and Vale 3.23.0.

```sh
git clone https://github.com/swack-tools/vite-ai-plugin.git
cd vite-ai-plugin

# Choose one scope.
python3 scripts/install.py --project /path/to/project
python3 scripts/install.py --user
```

On macOS, install dependencies with `brew install python vale`. On Linux or WSL,
use the [Vale installation guide](https://vale.sh/docs/install).

Restart Codex, trust the project if needed, and use `/hooks` to review and trust
Vale. The installer preserves other hooks and saves a backup before each change.
To remove Vale, repeat the install command with `--uninstall`.

The plugin package is in `plugins/vale`. A central plugin marketplace is optional.

Read the [documentation](https://vite.swacktech.com) for setup, configuration,
troubleshooting, and contribution instructions.

## Behavior

- Checks files changed since the first tool call in a session.
- Uses the project `.vale.ini` when present; otherwise uses bundled Google rules.
- Sends findings to Codex and requests one correction pass before completion.
- Leaves files unchanged. Codex applies any corrections.

Vale checks automated style rules. It cannot certify every recommendation in the
Google guide or format Google Docs documents.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/codex_smoke.py
```

The smoke test drives the installed Codex command-line tool with a local deterministic model
fixture. It requires no account or model API key.

GitHub Actions checks pull requests. It deploys documentation to GitHub Pages
only after a push to `main`, including a pull request merge.

MIT license. Bundled Google rules retain their upstream license.
