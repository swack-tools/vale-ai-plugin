# Writing profiles

Use the experimental `procedural-prose` skill for runbooks, setup instructions,
and troubleshooting procedures. It gives editorial guidance based on selected
Simplified Technical English (STE) principles. It doesn't certify `ASD-STE100`
compliance. Google remains the default mechanical style.

## Coverage

| Selection | Mechanical checks | Editorial guidance |
| --- | --- | --- |
| `auto` | Project `.vale.ini`, or bundled Google when absent | Choose a writing skill separately |
| `google` | Bundled Google | Choose a writing skill separately |
| `ste-inspired` | The same bundled Google rules and severity | Choose `procedural-prose` separately |
| `procedural-prose` skill | Runs the selected checker | Conditions, steps, warnings, terminology, and meaning review |

The named profile adds no grammar rules, sentence-length limit, or official
STE dictionary. Selecting it doesn't invoke a model or activate a skill.
The skill doesn't change your configuration. Existing Google rules still have
the [coverage limits](evaluation.html#run-the-corpus) of the shared corpus.

## Activate the workflow

Install the plugin through either [marketplace](marketplaces.html), then invoke
the skill in your client:

```text
/vale:procedural-prose Revise docs/recovery.md and preserve its prerequisites.
```

In Codex, use:

```text
$vale:procedural-prose Revise docs/recovery.md and preserve its prerequisites.
```

A hook-only installation doesn't install skills. The skill resolves the checker
relative to its installed directory and runs it from your workspace. It needs
no hard-coded checkout path. It separates editorial advice from Vale findings.

To select the optional profile for a single check, run this from a source checkout:

```sh
python3 plugins/vale/scripts/prose_lint.py --profile ste-inspired --check docs/recovery.md
```

To share that selection, add it to `.vale-plugin.toml`:

```toml
schema_version = 1
profile = "ste-inspired"
```

A root `.vale.ini` conflicts with either explicit bundled profile. Keep
`profile = "auto"` to retain your project's rules and vocabulary. You can still
invoke `procedural-prose` under those rules. The plugin never silently replaces
or merges the project configuration. See [policy precedence](configuration.html#project-selection-policy).

To return to the default selection, set `profile = "auto"` or remove the
profile setting. Without a project configuration, `profile = "google"` also
selects bundled Google. Use `google-prose` for general technical writing.
Changing profiles doesn't undo edits that an agent has already made.

## Revise a procedure

Before:

```text
Run `service restart --wait 30` if the health check passes.
The restart may take 30 seconds.
```

After:

```text
If the health check passes:

1. Run `service restart --wait 30`.

The restart may take 30 seconds.
```

The command, condition, quantity, and uncertainty remain intact. A condition
that governs several steps must still govern the whole sequence. Don't turn an
initial condition into a requirement to check it again after an action changes
system state. Preserve compound conditions, negation, and prerequisites.

For a destructive action, state its known consequence before the action:

```text
Warning: Clearing the cache deletes unsaved entries. You can't recover them.

1. Save pending work.
2. Run `cache clear`.
```

Don't invent a consequence or add an unsupported prerequisite. Keep one action
per step when splitting improves clarity, while preserving the required order.
Keep the same term for the same thing and clarify ambiguous pronouns only when
the source establishes their referent.

A recommendation expressed with "should" must remain a recommendation. Preserve
"may" as permission or possibility according to its original meaning. Don't
strengthen either word to "must." Preserve quoted errors, commands, identifiers,
quantities, and justified qualifications. Leave marketing copy, quoted source
text, and already-clear procedures unchanged unless the user requests edits.

## Evidence and limitations

The skill is experimental. Its seven evaluation cases cover a condition before
a command, compound negation, warning consequences, two actions in one step,
quoted commands, marketing copy, and an already-clear procedure.

Prepare fourteen unrun records for seven matched pairs:

```sh
python3 scripts/evaluate_prose.py --suite procedural-prose --prepare evals/results/procedural-pilot
python3 scripts/evaluate_prose.py --suite procedural-prose --results evals/results/procedural-pilot --format json
```

The second command returns `2` until evidence is complete. Use the
[evaluation protocol](evaluation.html) for isolated runs, protected literals,
and identified semantic review. The real-model pilot remains unrun. Local
client fixtures verify discovery and invocation, not editorial effectiveness.

The literal validator deliberately preserves surrounding command context.
It can flag a harmless condition reordering, including the preceding example.
Retain the raw output and report that result separately from the semantic
review. Don't edit evidence merely to make it pass. A clean Vale result alone
doesn't establish clearer writing or preserved meaning.

This release adds no heuristic rules. A future rule proposal needs positive
examples, non-finding examples, false-positive evidence, and documented limits.
Don't cite official rule numbers without a verified source.

## Sources

The [official guidance on STE software](https://www.asd-ste100.org/STEsoftware.html)
places responsibility on writers and doesn't endorse or certify checking tools.
The [Coder documentation change](https://github.com/coder/coder/pull/27852)
provides an example of adopting selected editorial principles. This plugin uses
original guidance inspired by those sources, without copying the official
dictionary or claiming full standard compliance.
