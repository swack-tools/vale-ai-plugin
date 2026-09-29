#!/usr/bin/env python3
"""Validate curated catalog metadata against the pinned schema and this checkout."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator
from markdown_it import MarkdownIt

SCHEMA_SHA256 = "d115d44f2d32c653f97c08e889587a04353c871db55821d11e126d2e14707e13"
SCHEMA_MARKETPLACE_COMMIT = "437c642bdac19d744dbb26b79bc2e673bebf0691"
SCHEMA_PATH = Path(".github/schemas/upstream-info.schema.json")
CANONICAL_PLUGIN_ID = "vale"
SOURCE_MODES = {"markdown": {"lead", "section"}, "html": {"section"}}


def _native(root: Path, plugin_id: str) -> tuple[set[str], set[str]]:
    package = root / "plugins" / plugin_id
    capabilities: set[str] = set()
    hook_targets: set[str] = set()
    if not package.is_dir():
        return capabilities, hook_targets
    for skill in package.rglob("SKILL.md"):
        text = skill.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^---\s*\n(.*?)\n---", text)
        name = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+)", match.group(1)) if match else None
        if name:
            capabilities.add(f"skill:{name.group(1).strip()}")
    for command in package.rglob("commands/*.md"):
        capabilities.add(f"command:{command.stem}")
    for manifest in package.rglob("*.json"):
        if manifest.name.lower() not in {"hooks.json", "mcp.json", ".mcp.json"}:
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rel = manifest.relative_to(root).as_posix()
        hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
        if isinstance(hooks, dict):
            for event, groups in hooks.items():
                for i, group in enumerate(groups if isinstance(groups, list) else []):
                    for j, _ in enumerate(group.get("hooks", []) if isinstance(group, dict) else []):
                        hook_targets.add(f"{rel}#/hooks/{event}/{i}/hooks/{j}")
        servers = data.get("mcpServers", data if manifest.name.lower() == ".mcp.json" else {}) if isinstance(data, dict) else {}
        if isinstance(servers, dict):
            capabilities.update(f"mcp_server:{name}" for name in servers)
    for source in (root / "src").rglob("*.rs") if (root / "src").exists() else []:
        text = source.read_text(encoding="utf-8", errors="replace")
        capabilities.update(f"mcp_tool:{name}" for name in re.findall(r'\btool\(\s*"([a-zA-Z0-9_-]+)"', text))
    return capabilities, hook_targets


def _heading_matches(text: str, path: list[str]) -> int:
    tokens = MarkdownIt("commonmark").enable("table").parse(text)
    stack: list[tuple[int, str]] = []
    matches = 0
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = int(token.tag[1:])
        inline = tokens[i + 1].content.strip() if i + 1 < len(tokens) else ""
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, inline))
        if path and [part.casefold() for _, part in stack[-len(path):]] == [part.casefold() for part in path]:
            matches += 1
    return matches


def _source_entries(data):
    found = []
    def walk(value, *, in_target=False, in_source=False):
        if isinstance(value, dict):
            if not in_target and (in_source or "path" in value):
                found.append(value)
            for key, item in value.items():
                walk(
                    item,
                    in_target=in_target or key == "target",
                    in_source=not in_target and key in {"source", "sources"},
                )
        elif isinstance(value, list):
            for item in value:
                walk(item, in_target=in_target, in_source=in_source)
    walk(data)
    return found


def _validate_source(root: Path, source: dict, errors: list[str]) -> bool:
    rel = source.get("path")
    if not isinstance(rel, str):
        errors.append("catalog source path must be a string")
        return False
    required = source.get("required", True)
    format_name = source.get("format")
    mode = source.get("mode")
    if not isinstance(format_name, str) or format_name not in SOURCE_MODES:
        errors.append(f"unsupported source format {format_name!r}: {rel}")
        return False
    if not isinstance(mode, str) or mode not in SOURCE_MODES[format_name]:
        errors.append(f"unsupported source mode {mode!r} for {format_name}: {rel}")
        return False

    posix = PurePosixPath(rel)
    if posix.is_absolute() or ".." in posix.parts or "\\" in rel:
        errors.append(f"unsafe source path: {rel}")
        return False
    path = (root / Path(*posix.parts)).resolve()
    if root not in path.parents or not path.is_file():
        if source.get("required", True):
            errors.append(f"source path missing or outside repository: {rel}")
        return False

    if format_name == "markdown" and mode == "section":
        heading_path = source.get("heading_path")
        if not isinstance(heading_path, list) or not heading_path or any(
            not isinstance(part, str) or not part.strip() for part in heading_path
        ):
            if required:
                errors.append(f"Markdown section is missing a valid heading selector: {rel}")
            return False
        try:
            matches = _heading_matches(path.read_text(encoding="utf-8"), heading_path)
            if matches != 1:
                if required:
                    errors.append(f"Markdown heading selector must match exactly once: {rel}")
                return False
        except (OSError, UnicodeError):
            errors.append(f"cannot resolve Markdown source: {rel}")
            return False

    if format_name == "html" and mode == "section":
        selector = source.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            if required:
                errors.append(f"HTML section is missing a valid CSS selector: {rel}")
            return False
        try:
            count = len(BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").select(selector))
            if count != 1:
                if required:
                    errors.append(f"HTML selector must match exactly once: {rel}")
                return False
        except Exception:
            errors.append(f"HTML selector invalid: {rel}")
            return False
    return True


def validate(root: Path, data: dict | None = None) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    schema_file = root / SCHEMA_PATH
    try:
        schema_bytes = schema_file.read_bytes()
        schema = json.loads(schema_bytes)
        if hashlib.sha256(schema_bytes).hexdigest() != SCHEMA_SHA256:
            errors.append(
                f"pinned schema digest mismatch for marketplace commit {SCHEMA_MARKETPLACE_COMMIT}; "
                "refresh only to an approved marketplace schema"
            )
        if data is None:
            data = json.loads((root / "catalog-info.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return errors + ["catalog metadata or pinned schema is missing or invalid JSON"]
    for issue in Draft202012Validator(schema).iter_errors(data):
        errors.append("schema violation at " + "/".join(map(str, issue.absolute_path)))
    if errors:
        return errors
    if not isinstance(data, dict) or not isinstance(data.get("pluginId"), str):
        return errors
    if data["pluginId"] != CANONICAL_PLUGIN_ID:
        errors.append(f"pluginId must identify the canonical package {CANONICAL_PLUGIN_ID!r}")
        return errors
    if not (root / "plugins" / CANONICAL_PLUGIN_ID).is_dir():
        errors.append(f"canonical package directory is missing: plugins/{CANONICAL_PLUGIN_ID}")
        return errors

    capabilities, hook_targets = _native(root, CANONICAL_PLUGIN_ID)
    valid_sources = {
        id(source)
        for source in _source_entries(data)
        if _validate_source(root, source, errors)
    }
    examples = data.get("examples", [])
    if not isinstance(examples, list):
        examples = []
    platforms = data.get("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
    for example in examples:
        if not isinstance(example, dict):
            continue
        if example.get("platform") not in platforms:
            errors.append(f"example references undeclared platform: {example.get('platform')}")
        refs = example.get("capability_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if ref not in capabilities:
                errors.append(f"example references unknown native capability: {ref}")
    cited = {
        ref
        for example in examples
        if isinstance(example, dict) and isinstance(example.get("capability_refs", []), list)
        for ref in example.get("capability_refs", [])
    }
    for cap in capabilities:
        if cap.startswith("hook:"):
            continue
        if cap not in cited:
            errors.append(f"native capability missing from examples: {cap}")
    mcp_servers = data.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
    native_servers = {cap.removeprefix("mcp_server:") for cap in capabilities if cap.startswith("mcp_server:")}
    declared_servers = set(mcp_servers)
    for server in sorted(native_servers - declared_servers):
        errors.append(f"native MCP server is missing from metadata: {server}")
    for server in sorted(declared_servers - native_servers):
        errors.append(f"metadata declares unknown MCP server: {server}")
    hooks = data.get("hooks", {})
    declared = set()
    if isinstance(hooks, list):
        for item in hooks:
            if not isinstance(item, dict):
                continue
            target = item.get("target", {})
            if not isinstance(target, dict):
                continue
            declared.add(f"{target.get('path', '')}#{target.get('pointer', target.get('jsonPointer', ''))}")
    elif isinstance(hooks, dict):
        for item in hooks.values():
            if isinstance(item, list):
                for note in item:
                    if not isinstance(note, dict):
                        continue
                    target = note.get("target", {})
                    if not isinstance(target, dict):
                        continue
                    declared.add(f"{target.get('path', '')}#{target.get('pointer', target.get('jsonPointer', ''))}")
    for _target in declared - hook_targets:
        errors.append("metadata declares unknown native hook target")
    for _target in hook_targets - declared:
        errors.append("native hook is missing a catalog note")
    if isinstance(platforms, dict):
        for name, platform in platforms.items():
            if not isinstance(platform, dict) or platform.get("status") not in {"documented", "unsupported"}:
                continue
            sources = platform.get("sources", [])
            if not isinstance(sources, list) or not any(
                isinstance(source, dict) and id(source) in valid_sources for source in sources
            ):
                errors.append(f"platform {name!r} claim requires at least one resolved source")
    return errors


def main() -> int:
    errors = validate(Path(__file__).resolve().parents[1])
    if errors:
        for error in errors:
            print(f"catalog-info: {error}", file=sys.stderr)
        return 1
    print("catalog-info.json is valid against the pinned marketplace schema and repository sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
