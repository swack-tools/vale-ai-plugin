#!/usr/bin/env python3
"""Require both client manifests to match a release tag."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    Path("plugins/vale/.claude-plugin/plugin.json"),
    Path("plugins/vale/.codex-plugin/plugin.json"),
)


def mismatches(tag: str, root: Path = ROOT) -> list[str]:
    errors = []
    for relative in MANIFESTS:
        manifest = root / relative
        try:
            version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            errors.append(f"{relative}: cannot read a version ({exc})")
            continue
        if tag != f"v{version}":
            errors.append(f"{relative}: version {version!r} does not match tag {tag!r}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} TAG", file=sys.stderr)
        return 2
    errors = mismatches(sys.argv[1])
    if errors:
        print("Release version validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Both client manifests match release tag {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
