# Plugin evals

These cases run with `claude plugin eval`. They check that each Vale skill
triggers for the right requests and preserves technical meaning. Every case
that checks, writes, or revises prose also requires a bundled checker run. The
`marketing-unchanged` and `no-trigger` cases don't. Every install channel
ships this directory with the package. The suite runs only when invoked.

Run the suite from the repository root:

```sh
claude plugin eval plugins/vale --scaffold --allow-tools Bash Edit Write --judge-model sonnet
```

The `--judge-model sonnet` flag uses a Sonnet-tier judge for the LLM graders,
which assess meaning preservation and complete finding lists. Most cases need
`Bash` to run the checker. The rewrite cases also need `Edit`
and `Write`. The `--scaffold` flag runs each case's `setup.sh`, which writes
sample files into the case's empty workspace.

Before you run the suite, install these prerequisites:

- Claude Code 2.1.269 or later, which `claude plugin eval` requires
- Git 2.32 or later, because the scaffolds set `GIT_CONFIG_GLOBAL`
- Python 3.11 or later
- Vale 3.23 or later
- On Linux, `bubblewrap` and `socat` for the Bash sandbox. On Windows, run the
  suite under WSL2. Without a sandbox, Claude Code refuses every Bash-granting
  run.

The default ablation adds a no-plugin baseline arm. Skill-trigger graders
report whether the plugin fired and don't count toward either score.
Checker-run graders and negative tool assertions use `arm: both`, so they count
in both arms. The baseline arm has no bundled checker, so it fails the
checker-run graders by design.

An LLM judge sees only the first and last 12 trace messages. Read-only cases
also use `no-shell-writes.md`, a regular expression over every Bash call that
rejects file writes, moves, and Git state changes. Its command names match only
at shell command boundaries, so draft prose in a heredoc doesn't trigger it.
The rewrite cases add a trace pattern that requires a checker run after the
last Edit or Write call. Results go to the ignored `evals/results/` directory.

| Case | Skill | Checks |
| --- | --- | --- |
| `check-draft` | `check-prose` | Checks an unsaved draft through stdin without creating files. |
| `review-file` | `check-prose` | Reports file, line, rule, and correction without editing. |
| `markdown-scope` | `check-prose` | Checks only Markdown files, including uppercase extensions, without editing them, passing other files, or using `--all`. |
| `new-findings-baseline` | `check-prose` | Asks for a Git revision instead of choosing a baseline, without editing files. |
| `rewrite-file` | `rewrite-prose` | Applies findings, preserves commands and code, rechecks after the last edit, and reports what changed. |
| `no-rule-weakening` | `check-prose`, `rewrite-prose` | Fixes prose and confirms a clean check after the last edit, without policy overrides, rules turned off, or added vocabulary. |
| `google-write` | `google-prose` | Writes new content in Google style and runs the checker. |
| `procedural-condition` | `procedural-prose` | Preserves a compound negated condition and its prohibition, then runs the checker. |
| `marketing-unchanged` | `procedural-prose` | Leaves marketing copy out of procedural structure. |
| `no-trigger` | None | Loads no Vale skill and returns a working iterative function for an unrelated coding request. |

The repository-level `evals/` directory holds a separate offline prose corpus.
