#!/usr/bin/env python3
"""Check prose changed during an AI editing session using local Vale rules."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys
import tempfile
import time

from deadline import Deadline, DeadlineExceeded, OutputLimitExceeded, run_process

from lint_result import Issue, render_text
import vale_runner
import policy as selection_policy

# Preserve helper names used by existing callers of the original single module.
PACKAGE = vale_runner.PACKAGE
EXTENSIONS = selection_policy.EXTENSIONS
EXCLUDED = selection_policy.EXCLUDED
MAX_FILES = vale_runner.MAX_FILES
MAX_BYTES = vale_runner.MAX_BYTES
eligible = vale_runner.eligible
configuration = vale_runner.configuration
empty_result = vale_runner.empty_result
run_check = vale_runner.run_check

EVENTS = {'PreToolUse', 'PostToolUse', 'Stop'}


def git(cwd, *args, deadline=None):
    result = run_process(['git', '-C', str(cwd), *args], cwd=cwd, deadline=deadline, timeout=10, text=False)
    if result.returncode:
        raise RuntimeError(os.fsdecode(result.stderr).strip())
    # Git's NUL-separated filenames are filesystem bytes, not necessarily UTF-8.
    return os.fsdecode(result.stdout)


def workspace(cwd, *, deadline=None):
    try:
        return Path(git(cwd, 'rev-parse', '--show-toplevel', deadline=deadline).strip()).resolve()
    except OutputLimitExceeded:
        # A bounded Git failure is not evidence that this is a non-Git workspace.
        raise
    except (RuntimeError, FileNotFoundError):
        return cwd


def snapshot(root, *, deadline=None, policy=None):
    deadline = deadline or Deadline(50)
    deadline.check()
    policy = policy or selection_policy.load_policy(root)
    try:
        names = sorted(set(os.fsdecode(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', deadline=deadline)).split('\0')) - {''})
    except OutputLimitExceeded:
        # A bounded Git failure is not evidence that this is a non-Git workspace.
        raise
    except (RuntimeError, FileNotFoundError):
        names = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            deadline.check()
            dirs[:] = [d for d in dirs if d not in (selection_policy.HARD_EXCLUDED if policy.include else EXCLUDED) and not (Path(directory) / d).is_symlink()]
            for filename in files:
                deadline.check()
                name = str((Path(directory) / filename).relative_to(root))
                if policy.supports(name) and policy.selected(name):
                    names.append(name)
            if len(names) > MAX_FILES:
                raise RuntimeError('More than 20,000 prose files; narrow the workspace or exclude generated files.')
    result = {}
    for name in names:
        deadline.check()
        if not eligible(root, name, policy):
            continue
        try:
            stat = (root / name).stat()
        except FileNotFoundError:
            continue
        result[name] = [stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino]
        if len(result) > MAX_FILES:
            raise RuntimeError('More than 20,000 prose files; narrow the workspace or exclude generated files.')
    return result


def direct_paths(payload, root, cwd, policy=None):
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
        if eligible(root, relative, policy):
            selected.add(str(path.resolve().relative_to(root)))
    return selected


def state_directory(root, *, deadline=None):
    try:
        base = Path(os.fsdecode(git(root, 'rev-parse', '--absolute-git-dir', deadline=deadline)).strip())
    except OutputLimitExceeded:
        # A bounded Git failure is not evidence that this is a non-Git workspace.
        raise
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
    if 'files' not in data:
        raise RuntimeError('Invalid Vale state: missing snapshot; stop the session before removing its state file.')
    files = data['files']
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


def run_hook(payload, *, deadline=None, scope=None, cli_overrides=None):
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
    policy = None
    try:
        deadline.check()
        root = workspace(root.resolve(strict=True), deadline=deadline)
        policy = selection_policy.load_policy(root, {**(cli_overrides or {}), **({'scope': scope} if scope is not None else {})})
        scope = policy.scope
        with locked_state(root, session, deadline=deadline) as data:
            if event == 'PreToolUse' and data['files'] is not None:
                return {}
            current = snapshot(root, deadline=deadline, policy=policy)
            changed = ({name for name, signature in current.items() if data['files'].get(name) != signature}
                       if data['files'] is not None else set())
            if event == 'PreToolUse':
                data['files'] = current
                if scope == 'new-findings':
                    import baseline
                    directory = baseline.session_directory(state_directory(root, deadline=deadline), session)
                    baseline.capture(directory, root, current, deadline, wrapper_policy=policy)
                return {}
            if event == 'PostToolUse':
                changed |= direct_paths(payload, root, Path(cwd_value).resolve(), policy) & current.keys()
            touched = (set(data['touched']) | changed) & current.keys()
            pending = (set(data['pending']) | changed) & current.keys()
            selected = touched if event == 'Stop' else pending
            data['files'] = current
            data['touched'] = sorted(touched)
            data['pending'] = sorted(pending | selected)
            directory = None
            if scope == 'new-findings':
                import baseline
                directory = baseline.session_directory(state_directory(root, deadline=deadline), session)
            result = scoped_check(root, sorted(selected), deadline=deadline, scope=scope, directory=directory, policy=policy)
            data['pending'] = sorted((pending | selected) - set(result.submitted_files))
            if result.status in {'findings', 'incomplete'}:
                return feedback(event, result, active, root=root, session=session)
            if result.comparison and result.comparison['fallback_reason']:
                return {'systemMessage': render_text(result, 16000)}
            return {}
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result = empty_result(root, policy=policy)
        result.errors.append(Issue('hook_error', str(error)))
        return feedback(event, result.finish(), active, root=root, session=session)



def scoped_check(root, names, *, deadline, scope='changed-files', directory=None, revision=None, policy=None):
    if scope == 'changed-files' or (not names and revision is None):
        return run_check(root, names, deadline=deadline, **({"policy": policy} if policy is not None else {}))
    import baseline
    try:
        identity = baseline.policy_identity(root, deadline, wrapper_policy=policy)
    except (OSError, ValueError, RuntimeError):
        identity = None
    documents = {}
    result = run_check(root, names, deadline=deadline, documents=documents if identity is not None else None, policy=policy)
    return baseline.compare(root, result, documents, identity, directory=directory, revision=revision, deadline=deadline, wrapper_policy=policy)

class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Draft argument failures use the same machine-readable contract as input failures.
        raw = sys.argv[1:]
        if '--stdin' in raw:
            result = empty_result(Path.cwd())
            result.errors.append(Issue('argument_error', message))
            result.finish()
            as_json = '--format=json' in raw or any(
                a == '--format' and b == 'json' for a, b in zip(raw, raw[1:]))
            print(result.to_json() if as_json else render_text(result))
            raise SystemExit(2)
        super().error(message)


def check_stdin(root, args, policy, deadline):
    """Check bounded UTF-8 prose; the logical identity is never a file operand."""
    name = args.path if args.path is not None else 'draft.' + args.ext
    identity = '<stdin:' + name + '>'
    result = empty_result(root, [identity], policy)
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or PureWindowsPath(name).drive or
            '\\' in name or '..' in path.parts or path.suffix != '.' + args.ext or
            any(ord(c) < 32 for c in name)):
        result.errors.append(Issue('input_path', 'Use a root-relative logical path with the declared extension and no parent traversal.', identity))
        return result.finish()
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            result.errors.append(Issue('input_limit', 'Draft exceeds the 1 MiB byte limit.', identity))
            return result.finish()
        try:
            text = raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            result.errors.append(Issue('input_encoding', 'Draft must be valid UTF-8.', identity))
            return result.finish()
        result = vale_runner.check_document(root, text, name, deadline=deadline, policy=policy, relative_identity=True)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result.errors.append(Issue('check_error', str(exc), identity))
        result.finish()
    result.requested_files = [identity]
    result.submitted_files = [identity for _ in result.submitted_files]
    for item in [*result.findings, *result.skipped_files, *result.errors]:
        if item.path is not None:
            item.path = identity
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', nargs='+', metavar='FILE', help='Check named files without a hook event.')
    mode.add_argument('--all', action='store_true', help='Check all eligible workspace files.')
    mode.add_argument('--doctor', action='store_true', help='Inspect the engine, configuration, and parser readiness.')
    mode.add_argument('--stdin', action='store_true', help='Check UTF-8 draft prose from standard input.')
    parser.add_argument('--ext', choices=('md', 'txt', 'rst', 'adoc', 'html'))
    parser.add_argument('--path', help='Root-relative logical draft path; never read or written.')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    parser.add_argument('--scope', choices=('changed-files', 'new-findings'))
    parser.add_argument('--base-ref', help='Git commit or ref for manual new-findings checks.')
    for name in ('include', 'exclude'):
        patterns = parser.add_mutually_exclusive_group()
        patterns.add_argument('--' + name, action='append', help=f'Replace project {name} patterns; repeat for more patterns.')
        patterns.add_argument('--clear-' + name, dest=name, action='store_const', const=[],
                              help=f'Override the project {name} list with an empty list.')
    parser.add_argument('--profile', choices=selection_policy.PROFILES)
    args = parser.parse_args()
    if args.stdin and not args.ext:
        parser.error('--stdin requires --ext.')
    if not args.stdin and (args.ext is not None or args.path is not None):
        parser.error('--ext and --path require --stdin.')
    if args.stdin and args.scope == 'new-findings':
        parser.error('--stdin checks the complete draft and cannot compare new findings.')
    overrides = {key: getattr(args, key) for key in ('scope', 'include', 'exclude', 'profile')}
    if args.base_ref is not None and (not args.check or args.scope == 'changed-files'):
        parser.error('--base-ref requires --check and --scope new-findings.')
    if args.scope == 'new-findings' and (args.all or (args.check and args.base_ref is None)):
        parser.error('Manual new-findings requires --check FILE... --base-ref REV; --all does not compare.')
    if args.check or args.all or args.doctor or args.stdin:
        deadline = Deadline(20) if args.doctor else None
        root = Path.cwd()
        try:
            root = workspace(root.resolve(), deadline=deadline)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, DeadlineExceeded) as exc:
            note = 'Workspace discovery failed: ' + str(exc)
            if args.doctor:
                from diagnostics import empty_diagnostics, render_diagnostics
                report = empty_diagnostics(root)
                report['overall_status'] = 'incomplete'
                report['config']['config_path'] = None
                report['coverage']['verification'] = 'unknown'
                report['coverage']['note'] = note
                report['errors'].append(note)
                print(json.dumps(report) if args.format == 'json' else render_diagnostics(report))
            else:
                result = empty_result(root, args.check or [])
                result.config_path = ''
                result.coverage.verification = 'unknown'
                result.coverage.note = note
                result.errors.append(Issue('workspace_error', note))
                result.finish()
                print(result.to_json() if args.format == 'json' else render_text(result))
            return 2
        if args.doctor:
            from diagnostics import inspect_environment, render_diagnostics
            report = inspect_environment(root, cli_overrides=overrides, deadline=deadline)
            print(json.dumps(report) if args.format == 'json' else render_diagnostics(report))
            return 2 if report['overall_status'] == 'incomplete' else 0
        names = []
        for name in args.check or []:
            path = Path(name).absolute()
            names.append(str(path.relative_to(root)) if path.is_relative_to(root) else str(path))
        deadline = Deadline(50)
        policy = None
        try:
            policy = selection_policy.load_policy(root, overrides)
            if args.stdin:
                result = check_stdin(root, args, policy, deadline)
                print(result.to_json() if args.format == 'json' else render_text(result))
                return result.exit_code
            scope = 'changed-files' if args.all else policy.scope
            if args.base_ref and scope != 'new-findings':
                raise ValueError('--base-ref requires --scope new-findings or the same project scope.')
            if scope == 'new-findings' and args.base_ref is None:
                raise ValueError('Manual new-findings requires --base-ref REV; use --all for a full audit.')
            if args.all:
                names = sorted(snapshot(root, deadline=deadline, policy=policy))
            result = scoped_check(root, names, deadline=deadline, scope=scope, revision=args.base_ref, policy=policy)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            result = empty_result(root, names, policy)
            result.errors.append(Issue('check_error', str(exc)))
            result.finish()
        print(result.to_json() if args.format == 'json' else render_text(result))
        return result.exit_code
    try:
        result = run_hook(json.load(sys.stdin), cli_overrides=overrides)
    except (ValueError, OSError) as error:
        print(f'Vale: invalid hook input: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
