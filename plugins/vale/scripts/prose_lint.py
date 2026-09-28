#!/usr/bin/env python3
"""Check prose changed during an AI editing session using local Vale rules."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
EXTENSIONS = set('.md .mdx .txt .rst .adoc .html .rs .py .sh .pl .js .jsx .ts .tsx .go .c .h .cpp .hpp .java .css'.split())
EXCLUDED = {'.git', '.codex', '.claude', '.agents', '.venv', 'node_modules', 'target', 'dist', 'build', '.vale', 'vendor', '__pycache__'}
MAX_FILES = 20000
MAX_BYTES = 1024 * 1024
EVENTS = {'PreToolUse', 'PostToolUse', 'Stop'}


def git(cwd, *args):
    result = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip())
    return result.stdout


def workspace(cwd):
    try:
        return Path(os.fsdecode(git(cwd, 'rev-parse', '--show-toplevel')).strip()).resolve()
    except (RuntimeError, FileNotFoundError):
        return cwd


def eligible(root, name):
    path = root / name
    if path.suffix.lower() not in EXTENSIONS or set(Path(name).parts) & EXCLUDED:
        return False
    # Neither file nor directory symlinks can escape the workspace or alias files.
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        return False
    return path.is_file() and path.resolve().is_relative_to(root)


def snapshot(root):
    try:
        names = sorted(set(os.fsdecode(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')).split('\0')) - {''})
    except (RuntimeError, FileNotFoundError):
        names = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink()]
            names.extend(str((Path(directory) / f).relative_to(root)) for f in files if Path(f).suffix.lower() in EXTENSIONS)
            if len(names) > MAX_FILES:
                raise RuntimeError('More than 20,000 prose files; narrow the workspace or exclude generated files.')
    result = {}
    for name in names:
        if not eligible(root, name):
            continue
        try:
            stat = (root / name).stat()
        except FileNotFoundError:
            continue
        result[name] = [stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino]
        if len(result) > MAX_FILES:
            raise RuntimeError('More than 20,000 prose files; narrow the workspace or exclude generated files.')
    return result


def direct_paths(payload, root, cwd):
    if payload.get('tool_name') not in {'apply_patch', 'Edit', 'Write'}:
        return set()
    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        return set()
    names = [inputs[k] for k in ('file_path', 'path') if isinstance(inputs.get(k), str)]
    patch = inputs.get('command', inputs.get('patch', ''))
    if isinstance(patch, str) and payload.get('tool_name') in {'apply_patch', 'Edit', 'Write'}:
        for line in patch.splitlines():
            for prefix in ('*** Add File: ', '*** Update File: ', '*** Move to: '):
                if line.startswith(prefix):
                    names.append(line[len(prefix):])
    selected = set()
    for name in names:
        path = Path(name) if Path(name).is_absolute() else cwd / name
        # Preserve symlink components until eligible() checks them.
        try:
            relative = str(path.absolute().relative_to(root))
        except ValueError:
            continue
        if eligible(root, relative):
            selected.add(relative)
    return selected


def state_directory(root):
    try:
        base = Path(os.fsdecode(git(root, 'rev-parse', '--absolute-git-dir')).strip())
    except (RuntimeError, FileNotFoundError):
        base = root / '.codex'
    directory = base / 'vale-state'
    if directory.is_symlink():
        raise RuntimeError('Refusing a symlink for Vale state.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


@contextmanager
def locked_state(root, session):
    directory = state_directory(root)
    key = hashlib.sha256(session.encode()).hexdigest()
    state = directory / (key + '.json')
    lock = directory / (key + '.lock')
    # Refuse symlinks even if changed between the check and open.
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if state.is_symlink():
            raise RuntimeError('Refusing a symlink for Vale state.')
        if state.exists():
            data = json.loads(state.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('files'), dict):
                raise RuntimeError('Invalid Vale state; remove the session state file and restart.')
        else:
            data = {'files': None, 'touched': []}
        yield data
        fd, temporary = tempfile.mkstemp(dir=directory, prefix=key, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out)
            os.replace(temporary, state)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def configuration(root):
    override = root / '.vale.ini'
    return override if override.is_file() else PACKAGE / '.vale.ini'


def lint(root, names):
    if not names:
        return ''
    vale = shutil.which('vale')
    if not vale:
        raise RuntimeError('Vale is missing from PATH. Install Vale 3.23 or later, then restart your coding agent.')
    paths = []
    for name in sorted(names):
        if not eligible(root, name):
            continue
        path = root / name
        if path.stat().st_size > MAX_BYTES:
            raise RuntimeError(f'{name} exceeds the 1 MiB file limit; exclude or split it before checking.')
        paths.append(str(path.resolve()))
    messages = []
    # Keep argument sizes bounded. Never pass an untrusted path as a CLI option.
    for start in range(0, len(paths), 50):
        result = subprocess.run([vale, '--no-global', '--config', str(configuration(root)),
                                 '--output=line', '--no-wrap', '--', *paths[start:start + 50]],
                                cwd=root, capture_output=True, text=True, timeout=20)
        output = (result.stdout + result.stderr).strip()
        if result.returncode or output:
            messages.append(output or f'Vale exited with status {result.returncode}.')
    return '\n'.join(messages)


def feedback(event, message, active=False, error=False):
    prefix = 'Vale could not complete the check: ' if error else 'Fix the Google documentation style findings in the changed files:\n'
    text = (prefix + message)[:16000]
    if event == 'PostToolUse':
        # Context preserves the original tool result, including shell exit status.
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}
    if event == 'Stop' and not active:
        return {'decision': 'block', 'reason': text}
    return {'systemMessage': text + ('\nVale already requested a correction pass; report unresolved findings to the user.' if active else '')}


def run_hook(payload):
    if not isinstance(payload, dict):
        raise ValueError('Hook input must be a JSON object.')
    event = payload.get('hook_event_name')
    if event not in EVENTS:
        return {}
    session = payload.get('session_id')
    cwd_value = payload.get('cwd')
    if not isinstance(session, str) or not session or not isinstance(cwd_value, str):
        raise ValueError('Hook input requires session_id and cwd.')
    cwd = Path(cwd_value).resolve(strict=True)
    root = workspace(cwd)
    active = payload.get('stop_hook_active') is True
    try:
        with locked_state(root, session) as data:
            current = snapshot(root)
            if data['files'] is None:
                changed = set()
            else:
                changed = {name for name, signature in current.items() if data['files'].get(name) != signature}
            if event == 'PreToolUse':
                # Only initialize: repeated pre-events must not hide concurrent edits.
                if data['files'] is None:
                    data['files'] = current
                return {}
            if event == 'PostToolUse':
                changed |= direct_paths(payload, root, cwd) & current.keys()
            touched = (set(data['touched']) | changed) & current.keys()
            data['files'] = current
            data['touched'] = sorted(touched)
            findings = lint(root, touched if event == 'Stop' else changed)
            if findings:
                return feedback(event, findings, active)
            return {}
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        return feedback(event, str(error), active, error=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', nargs='+', metavar='FILE', help='Check named files without a hook event.')
    args = parser.parse_args()
    if args.check:
        root = workspace(Path.cwd())
        try:
            names = []
            for name in args.check:
                path = Path(name).resolve(strict=True)
                if not path.is_relative_to(root) or not eligible(root, str(path.relative_to(root))):
                    raise RuntimeError(f'Unsupported file or path outside the workspace: {name}')
                names.append(str(path.relative_to(root)))
            findings = lint(root, names)
            if findings:
                print(findings)
                return 1
            return 0
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(f'Vale: {error}', file=sys.stderr)
            return 2
    try:
        result = run_hook(json.load(sys.stdin))
    except (ValueError, OSError) as error:
        print(f'Vale: invalid hook input: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
