# Develop and deploy

## Repository layout

```text
plugins/vale/          Shared Claude Code and Codex plugin
  .codex-plugin/      Codex package metadata
  .claude-plugin/     Claude Code package metadata
  hooks/              Lifecycle registrations
  scripts/            Python hook runtime
  skills/             Checking and writing skills
  prompts/            Legacy Codex prompt template
  styles/Google/      Pinned upstream rules and license
.agents/plugins/      Codex marketplace catalog
.claude-plugin/       Claude Code marketplace catalog
scripts/              Installation, verification, and site build tools
tests/                Runtime, installation, and labeled prose tests
evals/                Synthetic prompts and paired-trial instructions
docs/                 Documentation source and static assets
.github/workflows/    Checks and GitHub Pages deployment
```

The runtime uses only the Python standard library and the installed Vale
executable. The documentation build uses the pinned dependency in
`requirements-docs.txt`.

## Run the checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 scripts/codex_smoke.py --plugin
python3 scripts/claude_smoke.py
claude plugin validate plugins/vale --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

The unit and integration suite uses temporary directories and real Vale. It
covers direct edits, shell and Model Context Protocol changes, concurrent event ordering, ignored
files, option-like filenames, source comments, Stop retries, and installer
preservation.

The smoke tests install from the local marketplace into temporary client
configuration and drive the real command-line tools with deterministic local
HTTP model fixtures. They verify plugin hook discovery, post-tool feedback, and
a correction after Stop feedback. The Claude Code test also verifies expansion
of `/vale:check-prose`. The fixtures need no remote model account or key.

Run `python3 scripts/codex_smoke.py` without `--plugin` to test the manual project
hook installer. These fixtures test client integration. Their scripted replies
don't evaluate a model's editorial judgment.

Only isolated smoke-test invocations bypass hook trust or tool permissions.
Normal installations use the client's trust and permission controls.

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
other branches can't deploy. There is no manual deployment trigger.

The deployment waits for tests and the documentation build. GitHub's Pages
actions upload and deploy the static artifact with narrowly scoped job
permissions. The workflow pins action versions to commit hashes.

The Pages custom domain is `vale.swacktech.com`. The Domain Name System (DNS) uses a `CNAME` alias record
from `vale` to `swack-tools.github.io`, with proxying off in Cloudflare.
GitHub Pages provides the content and Transport Layer Security (TLS) certificate.
Cloudflare hosts the DNS record. The site needs no Worker.

## Maintain bundled rules

The Google rules come from the official
[Google v0.7.1 release](https://github.com/vale-cli/Google/releases/tag/v0.7.1).
The archive has this `SHA-256` digest:

```text
4b67fca1f2a88595b2a578ab98bbf3017a23af677b04f93e862843f3ea1a9a0b
```

Keep the upstream license with the rules. To update, review the release,
replace the bundled package, update the recorded version and checksum, and
run the full test suite and documentation lint before merging.

## Verify parsers and hook performance

Install the [optional parsers](installation.html#optional-markup-parsers), then
require their integration cases during validation:

```sh
VALE_REQUIRE_PARSERS=1 python3 -m unittest discover -s tests -v
python3 scripts/benchmark_hooks.py --files 1000 4000 20000 --samples 5 --output /tmp/vale-benchmark.json
```

The benchmark uses disposable Git repositories and measures complete hook
processes after one warm-up per event. It records medians, individual samples,
and state writes. Compare runs on the same machine. Results depend on filesystem
and system load. Unit tests verify that repeated pre-tool events skip discovery
and unchanged events preserve state, without machine-specific timing thresholds.

A local macOS comparison with 20,000 small Python files alternated the old and
new hooks over five samples after a warm-up. Repeated pre-tool events measured
2.074 seconds before and 0.228 seconds after the fast path. Post-tool events
measured 1.718 and 1.715 seconds, respectively: broad edit
detection still requires a scan. These measurements demonstrate the removed
pre-tool work, not a prediction for other repositories or machines.

## Maintain comparison safety

`finding_diff.py` matches occurrences. `baseline.py` owns private initial
text, bounded policy fingerprints, and Git blob reads. `vale_runner.py` provides
the shared file and in-memory document adapter. `lint_result.py` retains raw
findings and selects actionable indexes for feedback. `prose_lint.py` coordinates
command-line scopes and lifecycle state. These modules share one monotonic deadline.

When updating bundled rules or configuration, review the locality assumptions
before updating the trusted rule hashes and complete policy digest in
`baseline.py`. Leaving an old hash produces
full-file feedback. Don't update hashes merely to silence the fallback.
Test inserted lines, duplicates, moved paragraphs, changed context, policy
changes, corrupt baselines, byte caps, and both installation scopes.

The scope fixture begins with one `Google.Latin` finding and adds another in a
separate paragraph. A full audit reports two findings. Comparison retains both
raw records and makes one actionable: a 50% reduction in actionable findings
for this fixture, with the new occurrence retained. This doesn't predict the
reduction in another repository. Comparison adds source storage and engine work.

## Documentation quality gate

Documentation uses the same bundled Google rules as the plugin, with a stricter
alert threshold for repository prose:

```sh
python3 scripts/check_docs.py
```

This command checks suggestions as well as warnings and errors. It inspects
structured findings and fails on any alert, even when Vale itself returns zero.
The workflow uses this stricter gate for every authored guide, skill, and prompt. Third-party rules and license
text retain their upstream wording. Zero automated findings doesn't replace
editorial review of accuracy, accessibility, or complete Google style guidance.

The build job also runs `python3 scripts/check_docs.py site/*.html` after
rendering. This checks generated navigation, labels, and footer text alongside
the guide content. Source and rendered checks both require zero findings.

## Continuous integration coverage

Every pull request and push to `main` runs the following checks:

| Job | Coverage |
| --- | --- |
| Unit and integration matrix | Linux and macOS with Python 3.11 and 3.14 |
| Required markup parsers | Docutils 0.23 and Asciidoctor 2.0.26 on every matrix job |
| Native client matrix | Codex 0.158.0 and Claude Code 2.1.277 on Linux, each with both feedback scopes |
| Documentation | Google rules at suggestion level for source files and generated HTML |

The parser jobs set `VALE_REQUIRE_PARSERS=1`, so missing optional parsers fail
CI instead of skipping their integration tests. A macOS filesystem limitation
still skips the raw-byte filename case. The native jobs install pinned public
clients and use temporary projects with local model fixtures. They verify
marketplace discovery, skill availability, tool feedback, project policy, and
the Stop correction pass without model credentials or paid model calls.

Run the comparison fixtures locally with these commands:

```sh
python3 scripts/codex_smoke.py --plugin --feedback-scope new-findings
python3 scripts/claude_smoke.py --scope project --feedback-scope new-findings
```

Use `--feedback-scope changed-files` for the other matrix mode. These fixtures
exercise client integration. They don't evaluate editorial model judgment or
interactive trust dialogs. CI retains unit-test logs and native request/output logs for seven
days. The logs contain disposable fixture data. No project documents or real
model credentials belong in them.

Native fixture cleanup retries only transient nonempty-directory errors, for
at most three seconds of retry delay. Other cleanup failures remain visible.
All matrix jobs and the documentation build must pass before a push to `main`
can deploy Pages. Pull requests never deploy.

## Evaluate writing changes

The default suite also checks twelve labeled prose fixtures with real Vale and
validates synthetic paired-trial records without model access. It tests changed
commands, incomplete reviews, mismatched models, and altered evidence. These
checks separate integration reliability from editorial quality.

Use the [writing evaluation guide](evaluation.html) to prepare six baseline/skill
pairs, record isolated runs, and review technical meaning. The offline validator
checks evidence completeness and protected literals. It doesn't judge writing
quality or call a model. The real-model pilot remains unrun, so editorial
effectiveness remains an open evaluation question.

## Procedural skill discovery

The native fixtures also assert that the procedural skill is available. Exercise
its explicit invocation with either client:

```sh
python3 scripts/codex_smoke.py --plugin --skill procedural-prose
python3 scripts/claude_smoke.py --skill procedural-prose
```

These local model fixtures verify client integration. They don't measure writing
quality. Use the [paired evaluation](evaluation.html) for that separate task.

Hosted native jobs invoke `check-prose` in full-file mode and
`procedural-prose` in new-findings mode for both clients. Both modes still
verify hook feedback and the correction pass.
