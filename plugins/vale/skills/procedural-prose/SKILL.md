---
name: procedural-prose
description: Use when writing or revising runbooks, setup procedures, troubleshooting steps, or instructions with conditions and warnings. Don't apply procedural structure to marketing copy or descriptive passages.
---

# Revise procedures

This experimental skill provides editorial guidance inspired by selected
Simplified Technical English (STE) principles. It doesn't certify compliance with `ASD-STE100`. Writing improvement remains unverified in isolated client trials.

## Preserve the contract

Classify each passage first. For a procedure, identify the conditions, ordered
actions, prerequisites, warnings, and consequences. Leave marketing copy and
quoted source text unchanged. If a procedure is already clear, retain it.

Before editing, list its protected commands, identifiers, quoted errors,
quantities, negation, requirement strength, and uncertainty. Preserve them in
the revision. Keep `should` as a recommendation, `may` as permission or
possibility in its original sense, and `must` as a requirement. Turning a
recommendation into an unconditional command changes its strength.

## Revise the steps

- Put the complete condition before the instruction. Preserve each `and`,
  `or`, negation, and `only if` restriction. If scope is ambiguous, explain the
  ambiguity instead of choosing a new meaning.
- Give each step one action. When splitting a step, keep the original order
  and prerequisite scope. A condition on the whole sequence still applies to
  the whole sequence. Don't recheck an initial condition after an action
  changes it unless the source requires that check.
- Keep a warning and its stated consequence before the affected action.
  Retain required actions in the steps as well. Don't invent a consequence
  or detach a warning when splitting a sentence.
- Use one project-approved term per concept. Give each pronoun a clear
  reference. Preserve justified qualifications and uncertainty.

For example, a condition that permits two actions can introduce a numbered
list. The list contains one action per step, in the original order. Each
command remains byte-for-byte identical to the source.

## Verify and report

Resolve `../../scripts/prose_lint.py` relative to this skill's directory and
invoke its absolute path with Python from the user's workspace:

```sh
python3 /path/to/vale/scripts/prose_lint.py --check docs/runbook.md
```

Use the actual selected policy. Invoking this skill doesn't select a profile
or change configuration. An existing project `.vale.ini` remains authoritative
with `profile = "auto"`. Select `ste-inspired` only on an explicit request.
It runs the same Google checks as the bundled default. Don't combine or
silently replace project rules. Follow the companion `check-prose` skill when
comparison scope requires a user-supplied Git revision.

Inspect meaning after linting: conditions, warning placement, action order,
protected text, and requirement strength. Report configured findings separately
from editorial advice. Report unchecked files or an unavailable checker.
A clean lint result doesn't prove meaning preservation. Don't invent official
STE rule numbers, add a dictionary, or enforce a sentence-length limit.

See the [profile guide](https://vale.swacktech.com/profiles.html) for activation,
coverage, examples, and evaluation limits. The
[official tool guidance](https://www.asd-ste100.org/STEsoftware.html) explains the
writer's responsibility. The [Coder proposal](https://github.com/coder/coder/pull/27852)
provides an example of editorial guidance kept separate from Vale rules.
