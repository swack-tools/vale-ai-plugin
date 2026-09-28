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
