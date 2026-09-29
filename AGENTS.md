# Repository guidance

## Canonical package and catalog metadata

The canonical distributable package is `plugins/vale`. Root `catalog-info.json` holds curated marketplace metadata outside the package archives. Native manifests, skills, and hook declarations define the inventory. Don't count compatibility copies.

Review the catalog whenever someone adds, removes, or renames a skill, or changes its frontmatter description or behavior. Also review it when someone changes a command, hook action, Model Context Protocol (MCP) server, or MCP tool. Update examples, prerequisites, expected results, platform invocations, or source selectors when their supporting documentation changes. Review platform support, installation guidance, runtime requirements, and changelog status. Use repository-relative evidence paths. Keep curated prose human-reviewed. CI validates the sidecar but never writes or rewrites it. Use `not_documented` without evidence. Leave `changelog` null when no changelog exists, so GitHub Release notes remain available.

Install the pinned checker dependencies with `python3 -m pip install -r requirements-catalog.txt`. Run `python3 scripts/check_catalog_info.py` to validate the schema, selectors, paths, and capability references. The approved marketplace schema lives at `.github/schemas/upstream-info.schema.json`. The checker pins the digest and marketplace commit for this exact approved schema. Refresh the schema only after marketplace approval. Copy that exact schema, update both pins, revise this file, and validate the result in a reviewed PR. CI must not follow a moving branch.

When a source change affects the catalog, update it in a reviewed, signed PR. Run the validator and repository checks, merge the PR, then tag the matching release commit. Pull request and tag workflows validate the checked-out commit before packaging or publishing. A validation failure blocks the release. CI never pushes metadata changes. GitHub Release notes provide the fallback while `changelog` is null.

## Change quality

- Preserve Vale's documented behavior and hook boundaries. Keep hook declarations, descriptions, and examples consistent.
- Never commit credentials, environment values, local user paths, private logs, or session data.
- Keep Claude and Codex manifests and release packages aligned with the canonical package.
- Update user documentation and catalog metadata when behavior, interfaces, prerequisites, or platform support changes.
- Keep diffs focused and preserve unrelated work. Run relevant unit, package, documentation, native, and catalog checks. Report exactly what passed and what remains unverified.
- Author commits as `swackhamer` and verify every signature before requesting review.
