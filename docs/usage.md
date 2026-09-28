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
Codex 0.158.0 does not recognize custom prompt commands; use `/skills` or a
skill mention on that version. The clients do not use identical command syntax.

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
If no files are specified, it uses relevant edits from the conversation or asks
for scope. It does not silently scan your entire repository.

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
checker itself does not rewrite files or weaken your policy.

## Write new documentation

```text
/vale:google-prose Write a setup guide for the existing server in docs/setup.md.
```

In Codex:

```text
$vale:google-prose Rewrite the installation section for a first-time contributor.
```

The writing skill applies Google documentation style and verifies the result
with the same checker. Both skills can also be selected automatically for
relevant natural-language requests, such as “check these docs with Vale.”

## Check edits from other tools

Ask either agent to update a document with a shell script, editor, patch, or MCP
tool. The pre-tool hook records the initial file state. The post-tool hook checks
observed changes, regardless of the tool name. The Stop hook checks touched files
before the turn ends and can request one correction pass.

Tools that only change remote documents are outside this local-file workflow.
A failed Claude Code tool call can skip `PostToolUse`; its local changes are
checked by the next successful post-tool event or the Stop event.

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
suggestion metadata. The checker does not apply suggestions.

`submitted_files` records completed engine invocations. It does not prove that
every file matched a rule. An empty Vale result can mean either no findings or
no matching configuration. Coverage for a project configuration is therefore
reported as unknown; the checker does not silently add Google rules.

### Diagnose an installation

```sh
python3 plugins/vale/scripts/prose_lint.py --doctor
python3 plugins/vale/scripts/prose_lint.py --doctor --format json
```

Doctor reports the selected executable and version, configuration, workspace,
parser requirements, and visible project installation files. It does not
install dependencies, download rules, or edit settings. Missing optional parsers
produce format-specific warnings. An unusable engine or configuration returns
exit code `2`. Configuration files alone cannot prove that a running client
loaded the hook; inspect the client's hook settings for activation.

## Project policy

An existing `.vale.ini` takes precedence. Keep project vocabulary and deliberate
exceptions there; see [configuration](configuration.html). Neither skill turns
off rules just to make a check pass. A clean check covers the configured rules,
not every editorial recommendation in the Google style guide.
