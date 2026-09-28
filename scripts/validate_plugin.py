#!/usr/bin/env python3
"""Validate this repository's local packages without executing their contents.

Checks documented Codex ingestion and Claude layout requirements, not a complete
upstream schema. Unknown optional fields remain the native client's responsibility.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
from urllib.parse import unquote, urlsplit

import yaml

NAME = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z')
VERSION = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z')


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    errors = []

    def fail(label, message):
        errors.append(f'{label}: {message}')

    def path(base, raw, allowed, label, directory=False):
        if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or '\\' in raw:
            fail(label, f'expected a relative contained path: {raw!r}')
            return None
        candidate = base / raw
        try:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(allowed):
                raise ValueError('path escapes package or repository')
            if not (resolved.is_dir() if directory else resolved.is_file()):
                raise ValueError('missing directory' if directory else 'missing file')
            for part in (candidate, *candidate.parents):
                if part == allowed:
                    break
                if part.is_symlink():
                    raise ValueError('symlink resource is not distributable')
            return resolved
        except (OSError, RuntimeError, ValueError) as exc:
            fail(label, f'{raw}: {exc}')
            return None

    def document(file, label, kind='json'):
        checked = path(root, str(file.relative_to(root)), root, label)
        if checked is None:
            return {}
        try:
            if checked.stat().st_size > 1024 * 1024:
                raise ValueError('metadata exceeds 1 MiB')
            value = json.loads(checked.read_text()) if kind == 'json' else yaml.safe_load(checked.read_text())
            if not isinstance(value, dict):
                raise ValueError('expected an object')
            return value
        except (OSError, UnicodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
            fail(label, str(exc))
            return {}

    def nonempty(data, key, label):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(label, f'{key} must be a nonempty string')
            return ''
        return value

    packages = {}
    versions = {}
    for host, marketplace in (('codex', '.agents/plugins/marketplace.json'), ('claude', '.claude-plugin/marketplace.json')):
        market = document(root / marketplace, marketplace)
        if not NAME.fullmatch(nonempty(market, 'name', marketplace)):
            fail(marketplace, 'invalid marketplace name')
        if host == 'claude':
            owner = market.get('owner')
            if not isinstance(owner, dict) or not isinstance(owner.get('name'), str) or not owner['name'].strip():
                fail(marketplace, 'owner.name is required')
        entries = market.get('plugins')
        if not isinstance(entries, list) or not entries:
            fail(marketplace, 'plugins must be a nonempty array')
            continue
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                fail(marketplace, 'plugin entry must be an object')
                continue
            name = nonempty(entry, 'name', marketplace)
            if not NAME.fullmatch(name) or name in seen:
                fail(marketplace, 'invalid or duplicate plugin name')
            seen.add(name)
            source = entry.get('source')
            if host == 'codex':
                if not isinstance(source, dict) or source.get('source') != 'local':
                    fail(marketplace, 'this repository requires a Codex local source object')
                    continue
                source = source.get('path')
                policy = entry.get('policy', {})
                if not isinstance(policy, dict) or policy.get('installation') not in ('NOT_AVAILABLE', 'AVAILABLE', 'INSTALLED_BY_DEFAULT') or policy.get('authentication') not in ('ON_INSTALL', 'ON_USE'):
                    fail(marketplace, 'invalid Codex installation/authentication policy')
                nonempty(entry, 'category', marketplace)
            package = path(root, source, root, marketplace, directory=True)
            if package is None:
                continue
            packages.setdefault(package, set()).add(host)
            label = str((package / f'.{host}-plugin/plugin.json').relative_to(root))
            manifest = document(root / label, label)
            if nonempty(manifest, 'name', label) != name:
                fail(label, 'name differs from marketplace entry')
            version = nonempty(manifest, 'version', label)
            if not VERSION.fullmatch(version):
                fail(label, 'version must be semantic versioning')
            versions.setdefault(package, set()).add(version)
            if 'version' in entry and entry['version'] != version:
                fail(marketplace, 'entry version differs from package')
            if host == 'codex':
                nonempty(manifest, 'description', label)
                for key in ('author', 'interface'):
                    if not isinstance(manifest.get(key), dict):
                        fail(label, f'{key} must be an object')
                interface = manifest.get('interface', {})
                if isinstance(interface, dict):
                    for key in ('displayName', 'shortDescription', 'longDescription', 'developerName', 'category'):
                        nonempty(interface, key, label)
                if 'skills' in manifest:
                    path(package, manifest['skills'], package, label, directory=True)
            # This package uses standard directories. Validate explicit local overrides.
            for field in ('skills', 'commands', 'hooks'):
                value = manifest.get(field)
                if isinstance(value, str):
                    path(package, value, package, label, directory=field != 'hooks')
                elif isinstance(value, list):
                    for item in value:
                        path(package, item, package, label, directory=field != 'hooks')

    for package, hosts in packages.items():
        label = str(package.relative_to(root))
        if hosts != {'codex', 'claude'}:
            fail(label, 'both marketplaces must reference the same package')
        if len(versions[package]) != 1:
            fail(label, 'host manifest versions disagree')
        for item in package.rglob('*'):
            if item.is_symlink():
                fail(str(item.relative_to(root)), 'symlink is not allowed in the distributable package')
            if item.name in ('.git', '.env', 'auth.json', 'credentials.json', '.DS_Store'):
                fail(str(item.relative_to(root)), 'private or workspace file in distributable package')
        hook_label = label + '/hooks/hooks.json'
        hooks = document(root / hook_label, hook_label).get('hooks', {})
        if not isinstance(hooks, dict):
            fail(hook_label, 'hooks must be an object')
            hooks = {}
        for event in ('PreToolUse', 'PostToolUse', 'Stop'):
            groups = hooks.get(event)
            if not isinstance(groups, list) or not groups:
                fail(hook_label, f'{event} is missing')
                continue
            for group in groups:
                commands = group.get('hooks') if isinstance(group, dict) else None
                if not isinstance(commands, list) or not commands:
                    fail(hook_label, f'{event} needs hook commands')
                    continue
                for command in commands:
                    if not isinstance(command, dict) or command.get('type') != 'command':
                        fail(hook_label, f'{event} requires command hooks')
                        continue
                    try:
                        words = shlex.split(command.get('command', ''))
                    except (ValueError, TypeError):
                        words = []
                    scripts = [w.split('}/', 1)[1] for w in words if w.startswith(('${CLAUDE_PLUGIN_ROOT}/', '${CODEX_PLUGIN_ROOT}/'))]
                    if not scripts:
                        fail(hook_label, f'{event} has no package-relative entry point')
                    for script in scripts:
                        path(package, script, package, hook_label)
        skills = package / 'skills'
        if not skills.is_dir():
            fail(label, 'skills directory is missing')
            continue
        for skill in skills.iterdir():
            if not skill.is_dir():
                continue
            skill_label = str((skill / 'SKILL.md').relative_to(root))
            source = path(skill, 'SKILL.md', package, skill_label)
            if source is None:
                continue
            try:
                text = source.read_text()
                pieces = text.split('---', 2)
                metadata = yaml.safe_load(pieces[1]) if text.startswith('---\n') and len(pieces) == 3 else None
                if not isinstance(metadata, dict):
                    raise ValueError('skill needs YAML frontmatter')
                if nonempty(metadata, 'name', skill_label) != skill.name:
                    fail(skill_label, 'skill name differs from directory')
                nonempty(metadata, 'description', skill_label)
                for link in re.findall(r'\]\(([^)]+)\)', text):
                    url = urlsplit(link)
                    if not url.scheme and url.path:
                        path(skill, unquote(url.path), package, skill_label)
                for resource in re.findall(r'`(\.\./[^`\s]+)`', text):
                    path(skill, resource, package, skill_label)
            except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                fail(skill_label, str(exc))
            agent_label = str((skill / 'agents/openai.yaml').relative_to(root))
            agent = document(root / agent_label, agent_label, 'yaml')
            interface = agent.get('interface')
            if not isinstance(interface, dict):
                fail(agent_label, 'interface must be an object')
            else:
                for field in ('display_name', 'short_description', 'default_prompt'):
                    nonempty(interface, field, agent_label)
                for field in ('icon_small', 'icon_large'):
                    if field in interface:
                        path(skill, interface[field], package, agent_label)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    errors = validate_repository(parser.parse_args().root)
    for error in errors:
        print(error)
    if not errors:
        print('Repository package validation passed.')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
