# Pull request annotations

Contributors can see prose findings in GitHub without installing an agent.
The CI adapter runs the shared checker and emits native workflow annotations.
It doesn't rewrite documents, post review comments, or request write access.

## Check changed documents

From a clean repository root, provide full commit IDs:

```sh
python3 scripts/ci_prose.py --base "$BASE_SHA" --head "$HEAD_SHA"
```

Check out the head commit first. Fetch both commits and their history. The
adapter rejects branch names, missing commits, a different checked-out head,
and modified tracked files. On an initial push with an all-zero base ID, it
selects files from the head tree.

The candidate roots are `README.md`, `docs/`, `plugins/vale/skills/`, and
`plugins/vale/prompts/`. Added, copied, modified, and renamed destinations are
candidates. Deleted files and test fixtures outside these roots aren't checked.
Git's null-delimited output preserves spaces and newlines in names.

The checker reviews **entire changed files**, including existing issues on
unchanged lines. This isn't the opt-in `new-findings` comparison used by local
hooks. The adapter explicitly passes `--scope changed-files`. Other project
settings still apply. To reproduce a finding locally:

```sh
python3 plugins/vale/scripts/prose_lint.py --check docs/example.md \
  --scope changed-files --format json
```

The root `.vale.ini` remains authoritative. The adapter reuses the shared
checker, selected profile, and `.vale-plugin.toml` policy. It doesn't synchronize
styles or resolve a second configuration. Project coverage remains unknown:
a successful invocation doesn't prove that every filename pattern matched.
See [configuration](configuration.html) and the
[path-pattern guidance](usage.html#check-an-unsaved-draft).

This repository installs verified Vale 3.23.0 and uses the bundled Google rules.
Its existing source and generated-page style gates remain in place. Those gates
require zero Google findings, including suggestions. The annotation job adds
locations and structured results.

## Read the result

| Exit | Meaning |
| --- | --- |
| `0` | The checker completed without configured findings, or no candidate files existed. The summary distinguishes these outcomes. |
| `1` | The checker completed with findings, including suggestions. |
| `2` | Invalid input, an operational failure, an incomplete check, or no submitted files after policy selection. |

No candidates produces `status: no-applicable-files` in the adapter report.
It doesn't claim a repository-wide check. A checker result retains
schema version 1, requested and submitted files, skips, coverage, and errors.
Unsupported candidate files fail visibly. If policy excludes every candidate,
the result remains skipped and exits with status `2`.

The adapter emits at most 50 complete annotations, with operational errors
first. The step summary reports total, shown, and omitted counts. Download the
`prose-check` artifact from the workflow run to inspect the complete
`ci-prose.json` result. The workflow retains artifacts for seven days. Locally,
the file defaults to `.research/ci-prose.json`. Use `--output PATH` to change it.
Use `--summary PATH` outside Actions to save the summary.

Errors appear as errors, warnings as warnings, and suggestions as notices.
Located findings include the rule title, file, line, and engine-reported columns.
Only real files inside the current repository receive file annotations.
Virtual, missing, symlinked, and stale-line locations remain unlocated messages.
GitHub can show findings outside the changed lines in the check summary even
when it doesn't attach them to the pull request diff.

The renderer escapes percent signs and line endings in messages. It also
escapes colons and commas in properties, following the
[official Actions toolkit](https://github.com/actions/toolkit/blob/main/packages/core/src/command.ts).
See GitHub's [workflow command reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
for annotation fields. Document text can't introduce another workflow command.
Reports can contain matched prose. Choose artifact access and retention to suit
the repository.

## Reuse in another repository

Use a reviewed, immutable plugin revision. Keep `scripts/ci_prose.py`,
`scripts/install_vale_ci.py`, and `plugins/vale/` together in a tool checkout.
Preserve the bundled licenses. Run the adapter with the target repository as
the working directory. An agent installation isn't required.

Start from the `prose` job in the
[repository workflow](https://github.com/swack-tools/vale-ai-plugin/blob/main/.github/workflows/ci-pages.yml).
It uses pinned actions, read-only contents access, checkout credential
persistence turned off, and environment variables for event commit IDs. A separate tool
checkout can use this step after the target checkout:

```yaml
- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
  with:
    repository: swack-tools/vale-ai-plugin
    ref: REPLACE_WITH_REVIEWED_COMMIT_SHA
    path: .vale-ci
    persist-credentials: false
```

Replace the revision placeholder with a full reviewed commit ID. Prefix tool
paths with `.vale-ci/` in the install and check steps. Keep the target checkout
at the event head with `fetch-depth: 0`. For example:

```yaml
permissions:
  contents: read

# In the prose job's steps, after checkout and runtime installation:
- name: Annotate prose
  env:
    BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}
    HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}
  run: python .vale-ci/scripts/ci_prose.py --base "$BASE_SHA" --head "$HEAD_SHA"
```

Use `pull_request` and the intended branch's `push` events. Don't run an
untrusted checkout under `pull_request_target`, pass secrets, or grant
`pull-requests: write`. Install the documented markup parsers for selected
reStructuredText and AsciiDoc files. Keep the always-run artifact upload so a
failed check retains its diagnostics.

To change candidate roots, maintain a reviewed copy of `DOCUMENT_ROOTS` in
`scripts/ci_prose.py`. Entries ending in `/` select a directory prefix. Other
entries select one exact path. Configure rule selection and vocabulary in the
target repository's `.vale.ini` and `.vale-plugin.toml`. Changing candidate
roots doesn't override the checker's safety exclusions or format support.
Keep a full documentation gate for policy changes and files outside the diff.

## Publication boundary

Annotations require no additional write permissions and work with the read-only
permissions available to fork checks. GitHub's approval policy can still delay
a first-time contributor's workflow. Only successful pushes to `main` can
upload and deploy this repository's Pages site. Deployment also requires the
annotation job, existing tests, native fixtures, and documentation build.
Pull request and scheduled events can't deploy the site.

Review suggestions and reviewdog integration remain deferred. They need
verified rule actions, fresh source spans, and a separate permissions decision.
This release doesn't offer automatic edits or claim that zero findings prove
editorial correctness.
