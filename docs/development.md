# Develop and deploy

## Repository layout

```text
plugins/vale/          Self-contained Codex plugin
  .codex-plugin/      Codex package metadata
  hooks/              Lifecycle registrations
  scripts/            Python hook runtime
  skills/             Writing guidance for findings
  styles/Google/      Pinned upstream rules and license
scripts/              Installation, verification, and site build tools
tests/                Runtime and installation tests
docs/                 Documentation source and static assets
.github/workflows/    Checks and GitHub Pages deployment
```

The runtime uses only the Python standard library and the installed Vale
executable. The documentation build uses the pinned dependency in
`requirements-docs.txt`.

## Run the checks

```sh
python3 -m unittest discover -s tests -v
vale --no-global --config plugins/vale/.vale.ini README.md docs plugins/vale/skills
python3 scripts/codex_smoke.py
```

The unit and integration suite uses temporary directories and real Vale. It
covers direct edits, shell and MCP changes, concurrent event ordering, ignored
files, option-like filenames, source comments, Stop retries, and installer
preservation.

The smoke test drives the installed Codex command-line tool using a deterministic local HTTP
model fixture. It creates an isolated `CODEX_HOME`, installs project hooks,
triggers a prose finding, and checks that Codex receives the finding and runs
a correction after Stop feedback. It uses no remote model or account key.

Only that isolated test invocation bypasses hook trust, after selecting the
repository's own hook source. Normal installations require `/hooks` review.

## Build the documentation

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-docs.txt
.venv/bin/python scripts/build_docs.py
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000`. The build creates static HTML with local CSS,
semantic navigation, and no tracking scripts or remote font dependency.

## Deployment policy

GitHub Actions checks pull requests and pushes to `main`. The Pages deployment
job runs only when the event is `push` and the ref is `refs/heads/main`. This
includes pull request merges and direct pushes to `main`. Pull requests and
other branches cannot deploy. There is no manual deployment trigger.

The deployment waits for tests and the documentation build. GitHub's Pages
actions upload and deploy the static artifact with narrowly scoped job
permissions. Action versions are pinned to commit hashes.

The Pages custom domain is `vale.swacktech.com`. The DNS record is a CNAME
from `vale` to `swack-tools.github.io`, using DNS-only mode in Cloudflare.
GitHub Pages provides the content and TLS certificate. Cloudflare hosts DNS;
no Worker is required.

## Maintain bundled rules

The Google rules come from the official
[Google v0.7.1 release](https://github.com/vale-cli/Google/releases/tag/v0.7.1).
The archive SHA-256 is:

```text
4b67fca1f2a88595b2a578ab98bbf3017a23af677b04f93e862843f3ea1a9a0b
```

Keep the upstream license with the rules. To update, review the release,
replace the bundled package, update the recorded version and checksum, and
run the full test suite and documentation lint before merging.
