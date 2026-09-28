# Configure style checks

## Defaults

If a project has no `.vale.ini`, the checker uses the bundled configuration and
Google rules. The bundle uses Google v0.7.1. Spelling is off,
and the minimum alert level is `warning`.

The checker runs with `--no-global`, so another global Vale configuration can't
silently change the result.

## Project configuration

A `.vale.ini` at the workspace root replaces the bundled configuration. This
preserves a project's existing policy, including any rules turned off. A custom
configuration can weaken or remove Google checks. Include Google explicitly if
that's your project's requirement.

For a manual Codex project installation, this configuration uses the installed rules:

```ini
StylesPath = .codex/vale/styles
MinAlertLevel = warning

[*.{md,rs,py,sh,pl}]
BasedOnStyles = Vale, Google
Vale.Spelling = NO
```

For a manual Claude Code installation, use `.claude/vale/styles` instead.
For marketplace or user installations, use project-managed rules:

```ini
StylesPath = .vale/styles
MinAlertLevel = warning
Packages = Google

[*.{md,rs,py,sh,pl}]
BasedOnStyles = Vale, Google
Vale.Spelling = NO
```

Run `vale sync` from the project root to download that configuration's packages.
Commit the configuration and add downloaded package directories to `.gitignore`.
Vale doesn't run package synchronization during a hook.

The configuration filename is `.vale.ini`.

## Tune the policy

Set `MinAlertLevel = error` if the project intentionally reports only errors.
The original OxiDex setup used this threshold, which omits warning-level rules.
Use `warning` for the default Vale policy.

Turn off a rule only when it conflicts with the project's writing requirements:

```ini
[*.md]
BasedOnStyles = Vale, Google
Vale.Spelling = NO
Google.We = NO
```

For a local exception in Markdown, use a Vale comment around the smallest
necessary passage:

```markdown
<!-- vale Google.Latin = NO -->
A verbatim quotation containing Latin abbreviations.
<!-- vale Google.Latin = YES -->
```

Prefer fixing the prose to suppressing a finding. Keep quotations, URLs,
identifiers, and technical meaning intact.

## Generated files

Keep generated output in an excluded directory or use Vale's file-specific
configuration to turn off checks for the generated files. Vale doesn't guess
whether a generator created a file from arbitrary text in its header.

For example, a project configuration can turn off checks for a generated
Markdown file:

```ini
[generated.md]
BasedOnStyles =
```

Review [Vale configuration](https://vale.sh/docs/vale-ini) for pattern precedence
and more detailed syntax settings.

## Project selection policy

Create `.vale-plugin.toml` at the workspace root to share wrapper settings across
Claude Code and Codex. Both project and user installations read this file.
The wrapper doesn't merge per-user policy files.

```toml
schema_version = 1
scope = "changed-files"
include = []
exclude = []
profile = "auto"
```

These are the defaults. Omit any setting to keep its default. Explicit command
options take precedence over project settings, which take precedence over
bundled defaults. Unknown keys, invalid types, and unsupported values produce
an incomplete check. The policy file must be a regular file of at most 64 KiB.

| Setting | Effect |
| --- | --- |
| `schema_version` | Must be the integer `1`. |
| `scope` | `changed-files` checks selected files in full. `new-findings` enables conservative comparison. |
| `include` | An empty list preserves default selection. A nonempty list replaces it. |
| `exclude` | Removes matching paths after inclusion. |
| `profile` | `auto` uses root `.vale.ini` when present, otherwise bundled Google. `google` requires the bundled configuration. |

Selecting `google` while a root `.vale.ini` exists produces a conflict. Use
`auto` to keep the project configuration, or remove that configuration when
switching to bundled rules. The wrapper never merges the two configurations.

Patterns use Python's `fnmatchcase` on paths relative to the root, with `/` as
the separator. Matching is case-sensitive. `*` can cross `/`, so `docs/*.md`
also matches `docs/api/guide.md`. Patterns don't expand in a shell or use Git's
ignore syntax. Quote patterns on the command line. Each list accepts up to
64 patterns of at most 512 characters each. Absolute paths, backslashes, and
`..` traversal components are invalid.

For example, select only documentation and exclude archived guides:

```toml
include = ["README.md", "docs/*.md"]
exclude = ["docs/archive/*"]
```

The entire `.git`, `.codex`, `.claude`, and `.agents` directory trees remain
excluded. Includes can't enable symlinks or paths outside the workspace.
A nonempty include list can select files under `.vale`, `.venv`, `node_modules`,
`target`, `dist`, `build`, `vendor`, and `__pycache__`. File size and execution
limits still apply. Automatic scans omit untracked Git-ignored files.
An explicit `--check` can name an ignored file, subject to the wrapper policy.
The wrapper reports policy-excluded operands as skipped.

Use `--include`, `--exclude`, `--profile`, or `--scope` for a command-specific
override. Repeat list options to supply multiple patterns. Each supplied list
replaces the corresponding project list. It doesn't append to it.

```sh
python3 plugins/vale/scripts/prose_lint.py --all \
  --include 'README.md' --include 'docs/*.md' --exclude 'docs/archive/*'
python3 plugins/vale/scripts/prose_lint.py --doctor --format json
```

Doctor reports effective values and an origin of `default`, `project`, or `cli`
for each setting. It also lists declared format aliases and parser readiness.

## Reviewed vocabulary

Use [Vale vocabularies](https://vale.sh/docs/keys/vocab) to maintain reviewed
terminology. Vocabulary files contain one regular expression per line. Keep
entries narrow and review changes as policy changes. The plugin doesn't learn
terms from agent output.

The integration tests verify this recipe with Vale 3.23.0. Start with the project-managed Google
package preceding configuration, run `vale sync`, and create these files:

```text
.vale/styles/config/vocabularies/Project/accept.txt
.vale/styles/config/vocabularies/Project/reject.txt
```

Put `OxiDex` in `accept.txt` and `Oxidexx` in `reject.txt`. Use this root
`.vale.ini`:

```ini
StylesPath = .vale/styles
MinAlertLevel = suggestion
Packages = Google
Vocab = Project

[*.md]
BasedOnStyles = Vale, Google
Vale.Spelling = YES
```

Commit the vocabulary files and configuration. If your ignore rules exclude `.vale`, adjust
your ignore rules to retain the reviewed vocabulary while excluding downloaded
Google rules. Don't store the vocabulary inside a generated package directory.

| Input | Verified result |
| --- | --- |
| `Use OxiDex.` | No terminology or spelling finding. |
| `Use Oxidex.` | `Vale.Terms` requests the accepted casing. |
| `Use Oxidexx.` | `Vale.Avoid` rejects the term. Spelling can also flag it. |
| `Use OxiDex, e.g. for testing.` | `Google.Latin` still reports the abbreviation. |

Accepted entries also become exceptions in other styles, so avoid broad
patterns. The bundled configuration disables `Vale.Spelling`. Enabling a
vocabulary doesn't imply that Vale runs spelling checks: the recipe explicitly
sets `Vale.Spelling = YES`. With spelling turned off, rejected terms still use
`Vale.Avoid`. Reviewed vocabulary doesn't establish factual accuracy.

Project configurations cause new-findings comparison to fall back
to full-file feedback because their dependencies aren't verified. Vocabulary
changes therefore can't silently suppress findings. Wrapper policy changes
also invalidate session comparison. Git comparisons require matching policy
bytes at the base revision.

## Additional filename extensions

An include pattern alone doesn't enable an unsupported extension. Declare a
Vale format mapping and matching rule section as well. For example, Markdown
stored as `.prose` can use this project configuration:

```ini
StylesPath = .vale/styles
MinAlertLevel = warning

[formats]
prose = md
MD = md

[*.{prose,MD}]
BasedOnStyles = Google
```

```toml
include = ["*.prose", "*.MD"]
```

The `.prose` fixture reports prose findings at their original locations and
skips fenced code. `MD = md` provides the same parser behavior for uppercase
Markdown names. Add an alias for each additional case spelling you use.
a filename glob alone doesn't select the correct parser. The wrapper accepts
aliases only to its supported formats and retains project coverage as unknown.
It doesn't modify project `.vale.ini` files.

## Select OpenAPI descriptions

[Vale Views](https://vale.sh/features/views) can extract prose from structured
data. The verified recipe uses Vale 3.23.0, its built-in `dasel` engine, and
Markdown parsing for description strings. It needs no separate parser service.

Create `.vale/styles/config/views/OpenAPI.yml`:

```yaml
engine: dasel
scopes:
  - name: description
    expr: search(has("description")).map(description)
    type: md
```

Declare the View in root `.vale.ini`, with your installed Google package:

```ini
StylesPath = .vale/styles
MinAlertLevel = warning

[*.yaml]
BasedOnStyles = Google
View = OpenAPI
```

Select the files in `.vale-plugin.toml`:

```toml
include = ["api/*.yaml"]
```

The wrapper recognizes explicit `*.yaml`, `*.yml`, and `*.json` sections with a
nonempty `View`. Use a separate section for each extension. Combined brace
sections don't enable additional data extensions in this wrapper. Don't combine
a data View with a format alias to plain text. That combination produces an
incomplete check.

The YAML integration fixture places the same Latin abbreviation in a
`description` and an `operationId`. The View returns exactly one `Google.Latin`
finding at the description's original line 5, columns 26–29. It ignores the
identifier. The wrapper passes paths and finding locations through unchanged.
Review selectors before adopting a View, and test representative source files.
Other extractors and data formats remain outside this verified recipe.
