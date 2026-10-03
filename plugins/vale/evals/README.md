# Plugin evals

These cases run with `claude plugin eval`. They check that each Vale skill
triggers for the right requests, runs the bundled checker, and preserves
technical meaning. Release archives exclude this directory.

Run the suite from the repository root:

```sh
claude plugin eval plugins/vale --scaffold --allow-tools Bash Edit Write
```

Most cases need `Bash` to run the checker. The rewrite cases also need `Edit`
and `Write`. The `--scaffold` flag runs each case's `setup.sh`, which writes
sample files into the case's empty workspace. Install Vale and Python 3 first.

The default ablation adds a no-plugin baseline arm. Graders marked
`arm: with-only` report whether the plugin fired and don't count toward the
baseline score. Results go to the ignored `evals/results/` directory.

| Case | Skill | Checks |
| --- | --- | --- |
| `check-draft` | `check-prose` | Checks an unsaved draft through stdin without creating files. |
| `review-file` | `check-prose` | Reports file, line, rule, and correction without editing. |
| `markdown-scope` | `check-prose` | Checks only Markdown files, including uppercase extensions, and never uses `--all`. |
| `new-findings-baseline` | `check-prose` | Asks for a Git revision instead of choosing a baseline. |
| `rewrite-file` | `rewrite-prose` | Applies findings, preserves commands and code, and verifies the result. |
| `no-rule-weakening` | `check-prose`, `rewrite-prose` | Fixes prose without disabling rules or adding vocabulary. |
| `google-write` | `google-prose` | Writes new content in Google style and runs the checker. |
| `procedural-condition` | `procedural-prose` | Preserves a compound negated condition and its prohibition. |
| `marketing-unchanged` | `procedural-prose` | Leaves marketing copy out of procedural structure. |
| `no-trigger` | None | Loads no Vale skill for an unrelated coding request. |

The repository-level `evals/` directory holds a separate offline prose corpus.
