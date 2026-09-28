# Commands, skills, and examples

## Choose how to run Vale

| Interface | Claude Code | Codex |
| --- | --- | --- |
| Automatic hooks | Enabled plugin hooks | Enabled and trusted plugin hooks |
| On-demand review | `/vale:check-prose` | `$vale:check-prose` or `/skills` |
| Writing guidance | `/vale:google-prose` | `$vale:google-prose` or `/skills` |
| Legacy prompt command | Use the checking skill | `/prompts:vale` on legacy clients only |

Claude Code exposes plugin skills as namespaced slash commands. Codex supports
skill mentions and a skill picker. Its optional custom prompt command requires
the [separate user installation](installation.html#legacy-slash-command-compatibility).
Codex 0.158.0 doesn't recognize custom prompt commands. Use `/skills` or a
skill mention on that version. The clients don't use identical command syntax.

## Review without editing

Claude Code:

```text
/vale:check-prose README.md docs/installation.md review only
```

Codex:

```text
$vale:check-prose Review README.md and docs/installation.md without editing.
```

The skill runs Vale and reports the file, line, rule, and suggested correction.
If you omit files, it uses relevant edits from the conversation or asks
for scope. It doesn't silently scan your entire repository.

## Fix findings

```text
/vale:check-prose docs/guide.md fix the findings and verify the result
```

In Codex:

```text
$vale:check-prose Fix the Vale findings in docs/guide.md, then check it again.
```

On older Codex clients that support the legacy prompt command:

```text
/prompts:vale docs/guide.md fix the findings and check again
```

The agent preserves technical meaning, code examples, identifiers, and URLs.
It checks the edited files again and reports any unresolved findings. The
checker itself doesn't rewrite files or weaken your policy.

## Write new documentation

```text
/vale:google-prose Write a setup guide for the existing server in docs/setup.md.
```

In Codex:

```text
$vale:google-prose Rewrite the installation section for a first-time contributor.
```

The writing skill applies Google documentation style and verifies the result
with the same checker. Clients can also select either skill automatically for relevant
natural-language requests, such as “check these docs with Vale.”

## Check edits from other tools

Ask either agent to update a document with a shell script, editor, patch, or Model Context Protocol
tool. The pre-tool hook records the initial file state. The post-tool hook checks
observed changes, regardless of the tool name. The Stop hook checks touched files
before the turn ends and can request one correction pass.

Tools that only change remote documents are outside this local-file workflow.
A failed Claude Code tool call can skip `PostToolUse`. The next successful post-tool event or Stop
checks its local changes.

## Run without an agent

From a source checkout, check selected files:

```sh
python3 plugins/vale/scripts/prose_lint.py --check ./README.md ./docs/usage.md
```

The script accepts file paths, not directories. For another workspace, run from
that workspace and use the absolute path to the checker. This preserves project
configuration discovery. Prefix filenames that start with a hyphen with `./`.

Exit code `0` means no findings under the selected configuration, `1` means
findings, and `2` means an incomplete check or invalid input. Configuration,
parser, and execution failures are incomplete checks, even when other files
produce findings. A warning from Vale is a finding even if Vale itself exits
with status `0`.

### Machine-readable results

```sh
python3 plugins/vale/scripts/prose_lint.py --format json --check ./README.md
```

Schema version `1` includes `status`, `config_path`, `requested_files`,
`submitted_files`, `skipped_files`, `findings`, `errors`, and `coverage`.
Findings retain rule, severity, message, source location, and available
suggestion metadata. The checker doesn't apply suggestions.

`submitted_files` records completed engine invocations. It doesn't prove that
every file matched a rule. An empty Vale result can mean either no findings or
no matching configuration. Coverage for a project configuration is therefore
reported as unknown. The checker doesn't silently add Google rules.

### Diagnose an installation

```sh
python3 plugins/vale/scripts/prose_lint.py --doctor
python3 plugins/vale/scripts/prose_lint.py --doctor --format json
```

Doctor reports the selected executable and version, configuration, workspace,
parser requirements, and visible project installation files. It doesn't
install dependencies, download rules, or edit settings. Missing optional parsers
produce format-specific warnings. An unusable engine or configuration returns
exit code `2`. Configuration files alone can't prove that a running client
loaded the hook. Inspect the client's hook settings for activation.

## Project policy

An existing `.vale.ini` takes precedence. Keep project vocabulary and deliberate
exceptions there. See [configuration](configuration.html). Neither skill turns
off rules just to make a check pass. A clean check covers the configured rules,
not every editorial recommendation in the Google style guide.

## Choose the audit scope

The bundled default `--scope changed-files` checks all findings in each selected file.
Project policy can change this default. See [selection and precedence](configuration.html#project-selection-policy).
It doesn't restrict findings to edited lines. Hooks select files from observed
changes. Manual `--check` selects the files you name.

For an explicit audit of every eligible workspace file:

```sh
python3 plugins/vale/scripts/prose_lint.py --all --format json
```

This includes tracked and eligible untracked files under the normal exclusions.
It ignores session baselines. `--all`, `--check`, and `--doctor` are mutually
exclusive. An empty selection returns status `skipped` and exit code `2`.

For findings introduced since a specific Git commit:

```sh
python3 plugins/vale/scripts/prose_lint.py --check ./docs/guide.md --scope new-findings --base-ref main --format json
```

Choose the reference explicitly. The checker resolves it to a commit and reads
old blobs without checking out that commit or modifying your files. New files
use an empty baseline. A missing reference or a workspace without Git produces
an incomplete check. Prefix a reference that starts with a hyphen using the
argument form `--base-ref=VALUE`.

Manual new-findings mode requires both `--check FILE...` and `--base-ref REV`.
It rejects `--all`. Doctor accepts a scope option to show its effective value
and origin without running comparison. The default scope rejects `--base-ref`.
A full audit remains available through `--all` or `--check FILE --scope changed-files`.
A project-selected `new-findings` scope also requires `--base-ref` for manual
file checks. `--all` always performs a full audit, and `--doctor` reports the
effective scope without comparing documents.

### Read a comparison result

The schema's optional `comparison` object contains:

| Field | Meaning |
| --- | --- |
| `mode` | `new-findings` |
| `baseline_source` | `session`, or `git:` followed by the resolved commit |
| `new` | Number of actionable findings, including conservative fallbacks |
| `existing` | Matched occurrences with unchanged context |
| `resolved` | Baseline occurrences with no safe match in the current result |
| `actionable_indexes` | Zero-based indexes into the complete `findings` array |
| `fallback_reason` | Reason for full-file feedback, or `null` |

The raw `findings` array retains existing findings. Text feedback, findings
status, and exit code `1` use the actionable subset. Errors still produce
status `incomplete` and exit code `2`. Zero actionable findings can therefore
coexist with raw findings and status `clean`. Report this as “no new actionable
findings,” not as a clean full-file audit.

The `resolved` count isn't proof that an author fixed each occurrence. Changed
context can make an old occurrence unmatched and the current occurrence
potentially new. A fallback counts all current findings as actionable.
See [comparison limits](behavior.html#comparison-limits) before relying on noise reduction.

### Ask a skill to compare

Claude Code:

```text
/vale:check-prose Check only new findings in docs/guide.md relative to main. Report any fallback.
```

Codex:

```text
$vale:check-prose Audit every eligible workspace file with --all. Review only.
```

The checking skill requires an explicit reference for manual comparisons.
It doesn't infer a session from the most recent state file.

## Inspect selection policy

Use `--doctor --format json` to inspect effective scope, include patterns,
exclude patterns, profile, and each setting's origin. The project policy applies
to marketplace hooks, manual installations, and direct checks in both clients.

```sh
python3 plugins/vale/scripts/prose_lint.py --doctor --format json
python3 plugins/vale/scripts/prose_lint.py --check docs/guide.md --scope changed-files
```

A policy-excluded file has a `skipped_files` entry with its reason. A request
containing only skipped files exits `2` with status `skipped`. Report those files
as unchecked. Don't remove exclusions or accept vocabulary terms merely to
obtain a clean result. See the [project recipes](configuration.html). For a deliberate one-command
reset, `--clear-include --clear-exclude` restores default selection without
enabling generated directories. These options leave the project file unchanged.
