# How the hook works

## Hook lifecycle

| Event | Action | Output |
| --- | --- | --- |
| `PreToolUse` | Initialize a session baseline if one doesn't exist | Empty JSON on success |
| `PostToolUse` | Compare file state and check changed files | Findings as additional model context |
| `Stop` | Check files touched during the session | Request a correction pass if findings remain |

Both clients load the same hook definitions and run the same checker.
All tool names match. Codex normalizes shell calls to `Bash`, and tools called
through code mode can also trigger hooks. A background shell command may deliver
its post-tool event when a later poll observes completion.

The post-tool response preserves the original tool output. In particular, a
style finding doesn't hide a shell command's exit status or make a completed
code-mode tool call reject its promise.

Vale returns JSON on standard output. Findings use `hookSpecificOutput` for
post-tool context and `decision: block` for a Stop continuation. If the client sets
`stop_hook_active`, Vale reports remaining findings without requesting another
continuation. This bounds automatic correction to one Stop retry. It isn't an
unconditional completion gate.

## File selection

The checker uses Git to list tracked and untracked files in a repository. The checker
omits untracked files that match Git ignore rules. Tracked files remain eligible
even if a later ignore rule matches them. Outside Git, Vale walks the session
directory and uses its built-in directory exclusions.

The snapshot compares modification time, change time, size, and inode. It doesn't
read every file's contents after every tool. A per-session lock serializes
state updates so overlapping tool calls don't reset the baseline. Findings
apply to changes observed in the workspace. Vale doesn't claim which concurrent
process caused an edit.

A read-only tool doesn't check unchanged prose unless an earlier check failed
and left files pending. Files already
changed before the first tool call form part of the baseline. The Stop check
covers files changed since that baseline, including changes missed by a post-tool
event. Deletions don't need linting.

Direct `Edit`, `Write`, and `apply_patch` payloads provide a fallback when a
post-tool event arrives without a baseline. Arbitrary shell edits require a
baseline. Restart the session after installation.

## Supported files

Documentation extensions: `.md`, `.mdx`, `.txt`, `.rst`, `.adoc`, and `.html`.
Source extensions: `.rs`, `.py`, `.sh`, `.pl`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`,
`.c`, `.h`, `.cpp`, `.hpp`, `.java`, and `.css`.

The bundled configuration accepts uppercase and mixed-case extensions. The
checker uses a canonical logical filename for those checks and reports the
original path. It doesn't rename files. Project configurations remain
responsible for their own patterns and format mappings. See the
[format and OpenAPI recipes](configuration.html#additional-filename-extensions).

AsciiDoc requires `asciidoctor`, and reStructuredText requires `rst2html`.
Refer to [installation requirements](installation.html) for setup.

Vale controls syntax parsing. Comment and docstring coverage varies by language.
Check a representative file when adding a language to your workflow. Vale doesn't
apply a code formatter or rewrite executable statements.

## Scope and limits

- The scope is the session's Git root, or its current directory outside Git.
- Edits outside that root, including a shell command's hidden external working
  directory, are outside coverage. Start an agent session in that workspace.
- The checker excludes symlinked files and directories.
- Default exclusions include `.git`, `.codex`, `.claude`, `.agents`, `.vale`, `.venv`, `node_modules`,
  `target`, `dist`, `build`, `vendor`, and `__pycache__`.
- Each eligible file must be at most 1 MiB. A workspace can contain at most
  20,000 eligible files. Exceeding a limit reports an incomplete check.
- Vale receives batches of at most 50 files, with a 20-second timeout per batch.
  The plugin limits each hook to 60 seconds.
- The hook performs no network requests and never runs `vale sync` automatically.
- The checker covers local file changes only, including changes from remote tools.

A tool failure can still change files. Claude Code emits `PostToolUse` only for
successful tools. The next post-tool event or Stop catches failed-tool changes.
A failed command can still edit files.

## State storage

Git workspaces store snapshots in their own Git directory under `vale-state`.
Linked worktrees have separate state. Non-Git workspaces use `.codex/vale-state`.
Default snapshots contain relative file paths and stat metadata, not file
contents or shell commands. Opt-in comparison also stores initial source text
in separate baseline directories. The checker hashes session IDs for filenames. Locks and snapshots use
private file permissions.

To discard old state, close the relevant agent sessions and remove only the
`vale-state` directory. Restarting a session then establishes a new baseline.

## Coverage is explicit

Vale enforces the installed rules. The Google style guide also includes advice
that needs editorial judgment, such as audience, structure, and clarity. A clean
check doesn't certify full compliance. Read the
[Google developer documentation style guide](https://developers.google.com/style)
when reviewing prose beyond the automated rules.

## Reports and incomplete checks

Configuration and parser failures produce an incomplete-check diagnostic.
They don't ask the agent to rewrite prose. At Stop, a diagnostic can request
one continuation to resolve or report the problem. The active retry never
blocks again. The final warning uses `systemMessage`. Clients control whether
that warning is visible to the user, the model, or both.

Hook feedback contains complete findings and a count of shown and omitted
findings within a 16,000-character budget. When a report is too large, the hook
saves its complete JSON beside the session state in `<session>.report.json`
and includes the path. This private file has mode `0600` and replaces the
previous report for that session. It contains matched snippets, paths, and
messages, not complete document bodies. Manual JSON checks write to standard
output and don't create session reports.

## Performance and state lifecycle

The first pre-tool event establishes the baseline. Later pre-tool events skip
the workspace scan. Unchanged events don't rewrite session state. Post-tool
and Stop events still scan metadata to detect shell and unknown-tool edits.

Each hook has a 50-second work budget covering discovery, lock waits, and
checks. Individual engine calls have a maximum of 20 seconds within that
budget. The runtime limits subprocess output to 8 MiB. Timeout cleanup terminates the
process group, including parser children. Report finalization has a separate
5-second subprocess allowance before the client's 60-second outer timeout.
Uninterruptible filesystem operations remain subject to operating-system
behavior. Filesystem operations can exceed the work budget.

Files whose checks didn't complete remain pending. A later post-tool or Stop
event retries them even if their metadata hasn't changed. Deleted files leave
the pending set. Findings from completed batches survive a later batch failure.

State schema `1` preserves the session's touched files and pending checks.
Existing state migrates on access. An unknown or malformed schema produces an
incomplete check instead of silently discarding its baseline. No automatic
age-based cleanup removes another session's files. Stop sessions before
manually removing their state, lock, and report files from the documented state
directory. Restarting establishes a new baseline.

## Initial document baselines

Automatic new-findings mode is opt-in. The default hooks store metadata only
and report all findings in changed files. An opt-in hook copies eligible source
text at the first `PreToolUse` event. Later events compare against those initial
bytes, including after a process restart. They don't redefine the baseline
after each bad edit. Stop continues to check all touched files in the session.

Capture adds one initial read of eligible files, up to 1 MiB per file and 16 MiB
of source text per session. The manifest records omissions. An oversized,
unreadable, or omitted baseline produces full-file feedback. A partial capture
never becomes a new baseline after edits. Files created after a complete
snapshot use an empty baseline. Starting the mode without a pre-tool snapshot
also produces full-file feedback.

The state directory contains `<session-hash>.baseline/`, with a separate
manifest and hashed filenames for captured documents. Directories use mode
`0700`, and files use `0600`. The reader refuses symbolic links and verifies
stored document hashes. These files contain source text, which can include
secrets already present in eligible files. They remain local and persist until
you remove them. The default mode never creates these document copies.

Close the corresponding sessions before removing their baseline directories,
metadata, locks, and reports. Removing all of `vale-state` removes every saved
session in that workspace. There is no automatic expiry or eviction. Starting
a new session establishes a new initial baseline. An update or a policy change
can invalidate an old baseline without deleting it.

## Comparison limits

Both sides use complete-document linting. The matcher aligns unchanged lines
and complete paragraphs, then matches rule, location, severity, message, and
matched text. It preserves occurrence counts. A newly added duplicate can't
consume the same old occurrence twice. Reordered unique paragraphs trigger
full-file feedback. Changed paragraph context remains actionable.

The bounded alignment accepts at most 5,000 lines in either document and a
line-count product of 1,000,000. Exceeding either limit produces a fallback.
These limits bound comparison work independently of the file-size limit.
Current comparison text also has a 16 MiB memory cap. Files beyond that cap
retain full-file feedback.

For changed documents, suppression supports six bundled local rules:
`Google.Latin`, `Google.We`, `Google.FirstPerson`, `Google.Will`,
`Google.WordList`, and `Google.WordListCase`. Other rules remain actionable
because their context may extend beyond a paragraph. For identical complete
documents under the same verified policy, matching can include other rules.
This is conservative occurrence matching, not a semantic equivalence test.

Comparison fingerprints the sealed bundled configuration, local style and
vocabulary bytes, and Vale's executable path and version. A reviewed policy digest verifies the complete bundled style tree. A rule
locality allowlist also verifies the six rule files. Changed inputs invalidate
suppression. Project configurations always produce full-file feedback because
the checker can't prove their include and parser dependencies. AsciiDoc and
reStructuredText also fall back because they use external parsers. This
restriction affects comparison only: full-file checks still use your policy
and installed parsers.

Manual comparisons reject an earlier project policy or a changed tracked
bundled policy. Untracked and ignored policy inputs inside the checked Git
workspace also cause fallback because they have no verified historical identity. For an installed package outside the checked repository, the
current verified package checks both Git text and current text. It doesn't
reconstruct historical plugin installations. Changes to the reviewed bundled
style tree require a locality review and updated trusted digest before comparison
can resume. This includes added rules and vocabulary files.

A missing or corrupt baseline, uncertain alignment, or failed baseline lint
keeps current findings actionable and reports the reason. Current lint errors
remain incomplete checks. A fallback with no current findings reports its
limitation without blocking Stop. There is no successful-result cache. An
opt-in comparison can run Vale once per current document and once per baseline
document, within the shared work budget.

## Policy changes during a session

Hooks reload `.vale-plugin.toml` on each event. Invalid policy produces an
incomplete-check diagnostic, including during an initialized pre-tool event.
An include list can opt into generated directories, but it can't override
Git internals, agent configuration trees, containment, or symlink protection.
See [selection rules](configuration.html#project-selection-policy).

Changing policy doesn't reconstruct a session's original source text. Wrapper
policy changes invalidate comparison against the initial policy. Start a new
session after changing scope or coverage. Project `.vale.ini` files and their
vocabularies keep full-file feedback because their dependencies remain
unverified for comparison.
