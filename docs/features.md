# Feature guide

Choose features by the problem you need to solve. This inventory covers the
runtime, integrations, installers, and maintenance tools. Each row links to
usage and limits so the feature's value stays testable.

| Feature | When it helps | Verification and limits |
| --- | --- | --- |
| [Automatic lifecycle hooks](behavior.html#hook-lifecycle) | Catch local prose edits from editors, shell commands, and other tools | Shared event tests and real-client fixtures verify feedback. Remote-only edits remain outside coverage. |
| [One Stop correction pass](behavior.html#hook-lifecycle) | Request a correction before an agent finishes | Tests keep unresolved findings visible without an endless retry loop. It isn't an unconditional completion gate. |
| [Full-file checks](usage.html#run-without-an-agent) | Review named files without an agent | Real Vale tests preserve paths, rule details, and operational failures. This remains the default. |
| [Workspace audit](usage.html#choose-the-audit-scope) | Discover existing prose debt across eligible files | `--all` uses the documented exclusions and ignores session baselines. |
| [New-findings comparison](usage.html#choose-the-audit-scope) | Focus a change on new issues in an existing document | A duplicate fixture retains the new occurrence and suppresses the old one. Conservative fallbacks reduce this benefit for custom policies and some formats. |
| [Checking and writing skills](usage.html) | Request a review, a correction, or new documentation | Both hosts share the checker. Skills preserve technical meaning and require verification after edits. Model judgment still needs review. |
| [Dual marketplaces](marketplaces.html) | Discover and update the plugin in either client | Local marketplace smoke tests verify actual client loading. These catalogs aren't official curated listings. |
| [Project and user installers](installation.html#project-or-user-hooks-without-a-marketplace) | Share portable hooks or use them across projects | Tests verify both hosts, preserved settings, backups, updates, and removal. Hook-only installations don't add skills. |
| [Legacy Codex prompt](installation.html#legacy-slash-command-compatibility) | Support an older client with custom prompts | Installer tests cover ownership and removal. Current tested Codex rejects this command. Prefer skills for new installations. |
| [Project policy and offline rules](configuration.html) | Apply an organization's vocabulary and deliberate exceptions | Project configuration takes precedence. Bundled Google rules need no account or synchronization. Unknown rule coverage stays explicit. |
| [Explicit file selection](configuration.html#project-selection-policy) | Share scope and coverage across clients | Command options replace project values. Doctor shows origins, and tests preserve hard exclusions. |
| [Reviewed vocabulary](configuration.html#reviewed-vocabulary) | Enforce project terminology without broad rule suppression | Real Vale tests preserve Google findings while checking accepted casing and rejected terms. No automatic learning occurs. |
| [OpenAPI Views](configuration.html#select-openapi-descriptions) | Check API descriptions without checking identifiers | The Vale 3.23 YAML fixture preserves original source locations and ignores the same sentence in an identifier. |
| [Markup and source-comment checks](behavior.html#supported-files) | Review prose beside code and across documentation formats | Real parser fixtures cover representative formats and filename case. Parser dependencies and language coverage remain explicit. |
| [Structured results and reports](usage.html#machine-readable-results) | Integrate findings into scripts and inspect large hook results | Schema tests preserve raw findings, diagnostics, actionable indexes, and complete report entries. Reports can contain matched text. |
| [Installation diagnostics](usage.html#diagnose-an-installation) | Separate missing tools or configuration failures from style issues | `--doctor` inspects local readiness without installing or downloading anything. Client activation still needs a client check. |
| [Bounded execution and state](behavior.html#performance-and-state-lifecycle) | Keep hooks responsive and preserve unfinished checks | Tests cover deadlines, output caps, locks, process cleanup, and retries. Initial text capture occurs only in opt-in comparison mode. |
| [Native smoke tests and benchmarks](development.html) | Detect client integration regressions and measure hook cost | Disposable workspaces and local model fixtures avoid real model accounts. CI runs pinned clients in both feedback modes. Scripted replies don't evaluate editorial judgment. |
| [Documentation deployment](development.html#deployment-policy) | Publish tested guidance at the custom domain | Pull requests check code and strict Google style. Only pushes to `main` can deploy. |

## Keep the surface small

The legacy prompt is a compatibility feature with limited value for current
clients. New installations should use skills. Advanced policy profiles,
interactive baseline cleanup, automatic rewrites, and general lint-result
caching aren't part of this release. Add them only after evidence shows a
benefit that justifies their maintenance and failure modes.

The Google rules automate part of an editorial guide. They don't certify
Simplified Technical English, format Google Docs, or prove that a document is
accurate. Use a full audit for existing prose debt and a human review for
meaning, audience, and technical correctness.

## Writing evaluation

A source checkout includes a labeled corpus and an offline validator for paired
writing trials. The corpus checks selected rule counts and source lines. The
validator rejects incomplete pairs, changed literals, and stale reviews without
calling a model. See the [evaluation guide](evaluation.html) for the full schema,
examples, and review procedure. Editorial effectiveness remains unverified
until actual paired trials establish it.
