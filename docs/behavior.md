# How the hook works

## Hook lifecycle

| Event | Action | Output |
| --- | --- | --- |
| `PreToolUse` | Initialize a session baseline if one does not exist | Empty JSON on success |
| `PostToolUse` | Compare file state and check changed files | Findings as additional model context |
| `Stop` | Check files touched during the session | Request a correction pass if findings remain |

Both clients load the same hook definitions and run the same checker.
All tool names match. Codex normalizes shell calls to `Bash`, and tools called
through code mode can also trigger hooks. A background shell command may deliver
its post-tool event when a later poll observes completion.

The post-tool response preserves the original tool output. In particular, a
style finding does not hide a shell command's exit status or make a completed
code-mode tool call reject its promise.

Vale returns JSON on standard output. Findings use `hookSpecificOutput` for
post-tool context and `decision: block` for a Stop continuation. If the client sets
`stop_hook_active`, Vale reports remaining findings without requesting another
continuation. This bounds automatic correction to one Stop retry; it is not an
unconditional completion gate.

## Which files are checked

The checker uses Git to list tracked and untracked files in a repository. Untracked
files excluded by Git ignore rules are omitted. Tracked files remain eligible
even if a later ignore rule matches them. Outside Git, Vale walks the session
directory and uses its built-in directory exclusions.

The snapshot compares modification time, change time, size, and inode. It does
not read every file's contents after every tool. A per-session lock serializes
state updates so overlapping tool calls do not reset the baseline. Findings
apply to changes observed in the workspace; Vale does not claim which concurrent
process caused an edit.

A read-only tool does not check unchanged prose unless an earlier check failed
and left files pending. Files already
changed before the first tool call form part of the baseline. The Stop check
covers files changed since that baseline, including changes missed by a post-tool
event. Deletions do not need linting.

Direct `Edit`, `Write`, and `apply_patch` payloads provide a fallback when a
post-tool event arrives without a baseline. Arbitrary shell edits require a
baseline; restart the session after installation.

## Supported files

Documentation extensions: `.md`, `.mdx`, `.txt`, `.rst`, `.adoc`, and `.html`.
Source extensions: `.rs`, `.py`, `.sh`, `.pl`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`,
`.c`, `.h`, `.cpp`, `.hpp`, `.java`, and `.css`.

The bundled configuration accepts uppercase and mixed-case extensions. The
checker uses a canonical logical filename for those checks and reports the
original path. It does not rename files. Project configurations remain
responsible for their own patterns and format mappings.

AsciiDoc requires `asciidoctor`, and reStructuredText requires `rst2html`.
Refer to [installation requirements](installation.html) for setup.

Vale controls syntax parsing. Comment and docstring coverage varies by language;
check a representative file when adding a language to your workflow. Vale does
not apply a code formatter or rewrite executable statements.

## Scope and limits

- The scope is the session's Git root, or its current directory outside Git.
- Edits outside that root, including a shell command's hidden external working
  directory, are outside coverage. Start an agent session in that workspace.
- Symlinked files and directories are excluded.
- Built-in exclusions include `.git`, `.codex`, `.claude`, `.agents`, `.vale`, `.venv`, `node_modules`,
  `target`, `dist`, `build`, `vendor`, and `__pycache__`.
- Each eligible file must be at most 1 MiB; a workspace can contain at most
  20,000 eligible files. Exceeding a limit reports an incomplete check.
- Vale receives batches of at most 50 files, with a 20-second timeout per batch.
  The plugin limits each hook to 60 seconds.
- The hook performs no network requests and never runs `vale sync` automatically.
- Tools that write to remote systems without changing local files cannot be checked.

A tool failure can still change files. Claude Code emits `PostToolUse` only for
successful tools, so failed-tool changes are caught at the next post-tool event
or at Stop. The checker examines observed changes
without assuming that a successful exit is required for an edit.

## State storage

Git workspaces store snapshots in their own Git directory under `vale-state`.
Linked worktrees have separate state. Non-Git workspaces use `.codex/vale-state`.
Snapshots contain relative file paths and stat metadata, not file contents or
shell commands. Session IDs are hashed for filenames. Locks and snapshots use
private file permissions.

To discard old state, close the relevant agent sessions and remove only the
`vale-state` directory. Restarting a session then establishes a new baseline.

## Coverage is explicit

Vale enforces the installed rules. The Google style guide also includes advice
that needs editorial judgment, such as audience, structure, and clarity. A clean
check does not certify full compliance. Read the
[Google developer documentation style guide](https://developers.google.com/style)
when reviewing prose beyond the automated rules.

## Reports and incomplete checks

Configuration and parser failures produce an incomplete-check diagnostic.
They do not ask the agent to rewrite prose. At Stop, a diagnostic can request
one continuation to resolve or report the problem. The active retry never
blocks again. The final warning uses `systemMessage`; clients control whether
that warning is visible to the user, the model, or both.

Hook feedback contains complete findings and a count of shown and omitted
findings within a 16,000-character budget. When a report is too large, the hook
saves its complete JSON beside the session state in `<session>.report.json`
and includes the path. This private file has mode `0600` and replaces the
previous report for that session. It contains matched snippets, paths, and
messages, not complete document bodies. Manual JSON checks write to standard
output and do not create session reports.

## Performance and state lifecycle

The first pre-tool event establishes the baseline. Later pre-tool events skip
the workspace scan. Unchanged events do not rewrite session state. Post-tool
and Stop events still scan metadata to detect shell and unknown-tool edits.

Each hook has a 50-second work budget covering discovery, lock waits, and
checks. Individual engine calls have a maximum of 20 seconds within that
budget. Subprocess output is limited to 8 MiB. Timeout cleanup terminates the
process group, including parser children. Report finalization has a separate
5-second subprocess allowance before the client's 60-second outer timeout.
Uninterruptible filesystem operations remain subject to operating-system
behavior; this is not a hard real-time guarantee.

Files whose checks did not complete remain pending. A later post-tool or Stop
event retries them even if their metadata has not changed. Deleted files leave
the pending set. Findings from completed batches survive a later batch failure.

State schema `1` preserves the session's touched files and pending checks.
Existing state migrates on access. An unknown or malformed schema produces an
incomplete check instead of silently discarding its baseline. No automatic
age-based cleanup removes another session's files. Stop sessions before
manually removing their state, lock, and report files from the documented state
directory; restarting establishes a new baseline.
