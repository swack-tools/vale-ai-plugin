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
import time

from deadline import Deadline, DeadlineExceeded, run_process

from lint_result import Issue, render_text
from vale_runner import (PACKAGE, EXTENSIONS, EXCLUDED, MAX_FILES, MAX_BYTES,
                         eligible, configuration, empty_result, run_check)

EVENTS = {'PreToolUse', 'PostToolUse', 'Stop'}


def git(cwd, *args, deadline=None):
    result = run_process(['git', '-C', str(cwd), *args], cwd=cwd, deadline=deadline, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def workspace(cwd, *, deadline=None):
    try:
        return Path(git(cwd, 'rev-parse', '--show-toplevel', deadline=deadline).strip()).resolve()
    except (RuntimeError, FileNotFoundError):
        return cwd


def snapshot(root, *, deadline=None):
    deadline = deadline or Deadline(50)
    deadline.check()
    try:
        names = sorted(set(os.fsdecode(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', deadline=deadline)).split('\0')) - {''})
    except (RuntimeError, FileNotFoundError):
        names = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            deadline.check()
            dirs[:] = [d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink()]
            names.extend(str((Path(directory) / f).relative_to(root)) for f in files if Path(f).suffix.lower() in EXTENSIONS)
            if len(names) > MAX_FILES:
                raise RuntimeError('More than 20,000 prose files; narrow the workspace or exclude generated files.')
    result = {}
    for name in names:
        deadline.check()
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


def state_directory(root, *, deadline=None):
    try:
        base = Path(os.fsdecode(git(root, 'rev-parse', '--absolute-git-dir', deadline=deadline)).strip())
    except (RuntimeError, FileNotFoundError):
        base = root / '.codex'
    directory = base / 'vale-state'
    if directory.is_symlink():
        raise RuntimeError('Refusing a symlink for Vale state.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def validate_state(data):
    if not isinstance(data, dict):
        raise RuntimeError('Invalid Vale state; stop the session before removing its state file.')
    version = data.get('schema_version', 0)
    if type(version) is not int or version not in (0, 1):
        raise RuntimeError('Unknown Vale state schema; use a compatible plugin or restart with new state.')
    files = data.get('files')
    if files is not None and not isinstance(files, dict):
        raise RuntimeError('Invalid Vale snapshot.')
    for collection in (data.get('touched'), data.get('pending', [])):
        if not isinstance(collection, list) or any(not isinstance(name, str) for name in collection):
            raise RuntimeError('Invalid Vale file list in session state.')
    if files is not None:
        for name, signature in files.items():
            if not isinstance(name, str) or not isinstance(signature, list) or len(signature) != 4 or any(type(x) is not int for x in signature):
                raise RuntimeError('Invalid Vale file signature in session state.')
    all_names = [*(files or {}), *data['touched'], *data.get('pending', [])]
    if any(Path(name).is_absolute() or '..' in Path(name).parts for name in all_names):
        raise RuntimeError('Invalid path in Vale session state.')
    data['schema_version'] = 1
    data.setdefault('pending', [])
    return data


@contextmanager
def locked_state(root, session, *, deadline=None):
    deadline = deadline or Deadline(50)
    directory = state_directory(root, deadline=deadline)
    key = hashlib.sha256(session.encode()).hexdigest()
    state = directory / (key + '.json')
    lock = directory / (key + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        while True:
            deadline.check()
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(min(.02, deadline.remaining()))
        if state.is_symlink():
            raise RuntimeError('Refusing a symlink for Vale state.')
        if state.exists():
            with os.fdopen(os.open(state, os.O_RDONLY | os.O_NOFOLLOW)) as saved:
                if os.fstat(saved.fileno()).st_size > 16 * 1024 * 1024:
                    raise RuntimeError('Vale session state exceeds the 16 MiB limit.')
                data = json.load(saved)
            original = json.dumps(data, sort_keys=True)
            data = validate_state(data)
        else:
            original = None
            data = {'schema_version': 1, 'files': None, 'touched': [], 'pending': []}
        yield data
        serialized = json.dumps(data, sort_keys=True)
        if serialized == original:
            return
        fd, temporary = tempfile.mkstemp(dir=directory, prefix=key, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as out:
                out.write(serialized)
            os.replace(temporary, state)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def save_report(root, session, result):
    directory = state_directory(root, deadline=Deadline(5))
    key = hashlib.sha256(session.encode()).hexdigest()
    destination = directory / (key + '.report.json')
    if destination.is_symlink():
        raise RuntimeError('Refusing a symlink for the full report.')
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=key, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(result.to_json())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def feedback(event, result, active=False, *, root=None, session=None):
    suffix = ('Vale already requested a correction pass; report unresolved findings or incomplete checks to the user.'
              if active else '')
    report_path = None
    if len(render_text(result)) + len(suffix) + 256 > 16000 and root is not None:
        try:
            report_path = save_report(root, session, result)
        except (OSError, RuntimeError) as exc:
            result.errors.append(Issue('report_error', 'Could not save the full report: ' + str(exc)))
            result.finish()
    prefix = ('Vale could not complete the check. Resolve the diagnostic before claiming a clean check.'
              if result.errors else 'Fix the Vale style findings in the changed files:')
    text = render_text(result, 16000, prefix=prefix, suffix=suffix, report_path=report_path)
    if event == 'PostToolUse':
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}
    if event == 'Stop' and not active:
        return {'decision': 'block', 'reason': text}
    return {'systemMessage': text}


def run_hook(payload, *, deadline=None):
    deadline = deadline or Deadline(50)
    if not isinstance(payload, dict):
        raise ValueError('Hook input must be a JSON object.')
    event = payload.get('hook_event_name')
    if event not in EVENTS:
        return {}
    session = payload.get('session_id')
    cwd_value = payload.get('cwd')
    if not isinstance(session, str) or not session or not isinstance(cwd_value, str):
        raise ValueError('Hook input requires session_id and cwd.')
    active = payload.get('stop_hook_active') is True
    root = Path(cwd_value).absolute()
    try:
        deadline.check()
        root = workspace(root.resolve(strict=True), deadline=deadline)
        with locked_state(root, session, deadline=deadline) as data:
            if event == 'PreToolUse' and data['files'] is not None:
                return {}
            current = snapshot(root, deadline=deadline)
            changed = ({name for name, signature in current.items() if data['files'].get(name) != signature}
                       if data['files'] is not None else set())
            if event == 'PreToolUse':
                data['files'] = current
                return {}
            if event == 'PostToolUse':
                changed |= direct_paths(payload, root, Path(cwd_value).resolve()) & current.keys()
            touched = (set(data['touched']) | changed) & current.keys()
            pending = (set(data['pending']) | changed) & current.keys()
            selected = touched if event == 'Stop' else pending
            data['files'] = current
            data['touched'] = sorted(touched)
            data['pending'] = sorted(pending | selected)
            result = run_check(root, sorted(selected), deadline=deadline)
            data['pending'] = sorted((pending | selected) - set(result.submitted_files))
            if result.status in {'findings', 'incomplete'}:
                return feedback(event, result, active, root=root, session=session)
            return {}
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result = empty_result(root)
        result.errors.append(Issue('hook_error', str(error)))
        return feedback(event, result.finish(), active, root=root, session=session)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', nargs='+', metavar='FILE', help='Check named files without a hook event.')
    mode.add_argument('--doctor', action='store_true', help='Inspect the engine, configuration, and parser readiness.')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args()
    if args.check or args.doctor:
        root = workspace(Path.cwd().resolve())
        if args.doctor:
            from diagnostics import inspect_environment, render_diagnostics
            report = inspect_environment(root)
            print(json.dumps(report) if args.format == 'json' else render_diagnostics(report))
            return 2 if report['overall_status'] == 'incomplete' else 0
        names = []
        for name in args.check:
            path = Path(name).absolute()
            names.append(str(path.relative_to(root)) if path.is_relative_to(root) else str(path))
        result = run_check(root, names)
        print(result.to_json() if args.format == 'json' else render_text(result))
        return result.exit_code
    try:
        result = run_hook(json.load(sys.stdin))
    except (ValueError, OSError) as error:
        print(f'Vale: invalid hook input: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
