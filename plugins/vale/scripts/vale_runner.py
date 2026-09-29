"""Select safe file operands and normalize Vale's machine-readable results."""
import json
from pathlib import Path
import shutil
import subprocess

from deadline import Deadline, DeadlineExceeded, run_process
from lint_result import CheckResult, Coverage, Finding, Issue
from policy import EffectivePolicy, load_policy

PACKAGE = Path(__file__).resolve().parents[1]
MAX_FILES = 20000
MAX_BYTES = 1024 * 1024
MAX_DOCUMENT_BYTES = 16 * 1024 * 1024


def path_issue(root, name, policy=None):
    policy = policy or EffectivePolicy()
    path = root / name
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        return Issue('unsupported_path', 'Symbolic links are not checked.', name)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        return Issue('unsupported_path', 'File is missing, is not a regular file, or is outside the workspace.', name)
    if not policy.selected(name):
        return Issue('excluded_path', 'File is excluded by the wrapper policy.', name)
    if not policy.supports(name):
        return Issue('unsupported_path', 'File extension is not supported.', name)
    return None


def eligible(root, name, policy=None):
    policy = policy or EffectivePolicy()
    # Filter snapshot candidates before filesystem calls. Explicit operands use
    # path_issue directly so invalid requests stay distinct from policy skips.
    if not policy.supports(name) or not policy.selected(name):
        return False
    return path_issue(root, name, policy) is None


def configuration(root, policy=None):
    override = root / '.vale.ini'
    if override.is_file():
        return override
    if policy is not None and policy.profile == 'ste-inspired':
        return PACKAGE / 'profiles/ste-inspired.ini'
    return PACKAGE / '.vale.ini'


def _vale_path(root, path):
    """Return a safe workspace-relative identity for Vale's project globs."""
    relative = path.relative_to(root).as_posix()
    # The caller also supplies `--`, but keep option-looking names unambiguous
    # across Vale versions and operating systems.
    if relative.startswith('-'):
        relative = './' + relative
    return relative


def _map_vale_path(mapping, operand, result_path):
    mapping[operand] = result_path
    # Vale accepts the guarded ./ form for an option-looking basename but may
    # omit that prefix in its JSON key.
    if operand.startswith('./-'):
        mapping[operand[2:]] = result_path


def empty_result(root, names=(), policy=None):
    config = configuration(root, policy)
    source = 'project' if config == root / '.vale.ini' else 'bundled'
    coverage = Coverage(source, 'configured_invocation' if source == 'bundled' else 'unknown',
                        'Submitted operands are not proof of matched rules; an empty Vale result can also mean no matching configuration.')
    return CheckResult(1, 'skipped', str(config), list(names), [], [], [], [], coverage)


def decode_findings(stdout, known_paths):
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError('Vale JSON must be a path-to-alerts object.')
    findings, issues = [], []
    for path, alerts in data.items():
        if path not in known_paths or not isinstance(alerts, list):
            issues.append(Issue('invalid_alert', 'Vale returned an unexpected path or malformed alert list.'))
            continue
        for alert in alerts:
            try:
                findings.append(decode_alert(alert, known_paths[path]))
            except ValueError as exc:
                issues.append(Issue('invalid_alert', str(exc), known_paths[path]))
    return findings, issues


def decode_alert(alert, path):
    if not isinstance(alert, dict):
        raise ValueError('Vale returned a malformed alert.')
    for key in ('Check', 'Message', 'Match', 'Severity'):
        if not isinstance(alert.get(key), str):
            raise ValueError(f'Vale alert has an invalid {key}.')
    span = alert.get('Span')
    line = alert.get('Line')
    if line is not None and (type(line) is not int or line < 1):
        raise ValueError('Vale returned an invalid source location.')
    if span is not None:
        if (not isinstance(span, list) or len(span) != 2 or
                any(type(x) is not int or x < 1 for x in span) or span[1] < span[0] or line is None):
            raise ValueError('Vale returned an invalid source location.')
    start_column, end_column = span if span is not None else (None, None)
    suggestions = alert.get('Suggestions') or []
    action = alert.get('Action') or None
    link = alert.get('Link') or None
    if (not isinstance(suggestions, list) or any(not isinstance(x, str) for x in suggestions) or
            (action is not None and not isinstance(action, dict)) or
            (link is not None and not isinstance(link, str))):
        raise ValueError('Vale returned malformed suggestion metadata.')
    return Finding(path, line, start_column, end_column, alert['Check'],
                   alert['Severity'], alert['Message'], alert['Match'], link, suggestions, action)


def run_check(root, names, *, deadline=None, documents=None, policy=None):
    deadline = deadline or Deadline(50)
    result = empty_result(root, names)
    try:
        policy = policy or load_policy(root)
    except (OSError, ValueError) as exc:
        result.errors.append(Issue("policy_error", str(exc)))
        return result.finish()
    result = empty_result(root, names, policy)
    if not names:
        return result
    paths, aliases = [], []
    for name in sorted(set(names)):
        try:
            deadline.check()
            problem = path_issue(root, name, policy)
            if problem:
                (result.skipped_files if problem.code == 'excluded_path' else result.errors).append(problem)
                continue
            path = (root / name).resolve()
            if path.stat().st_size > MAX_BYTES:
                result.errors.append(Issue('file_limit', f'{name} exceeds the 1 MiB file limit; exclude or split it before checking.', name))
                continue
            if documents is not None or (result.coverage.source == 'bundled' and path.suffix != path.suffix.lower()):
                aliases.append((name, path))
            else:
                paths.append((name, path))
        except DeadlineExceeded as exc:
            result.errors.append(Issue('timeout', str(exc)))
            return result.finish()
        except OSError as exc:
            result.errors.append(Issue('file_error', str(exc), name))
    if not paths and not aliases:
        return result.finish()
    vale = shutil.which('vale')
    if not vale:
        result.errors.append(Issue('missing_vale', 'Vale is missing from PATH. Install Vale 3.23 or later, then restart your coding agent.'))
        return result.finish()
    jobs = [(paths[i:i+50], None) for i in range(0, len(paths), 50)]
    jobs += [([pair], str(pair[1].with_suffix(pair[1].suffix.lower())) if result.coverage.source == 'bundled'
              else _vale_path(root, pair[1])) for pair in aliases]
    return _execute(root, result, jobs, deadline, vale, captured=documents)


def check_document(root, text, logical_path, *, deadline=None, policy=None, relative_identity=False):
    """Lint complete in-memory text with the same decoder and configuration."""
    deadline = deadline or Deadline(50)
    policy = policy or load_policy(root)
    name = str(logical_path)
    result = empty_result(root, [name], policy)
    path = root / name
    if (not path.is_absolute() or not path.is_relative_to(root) or '..' in path.parts or
            not policy.supports(name) or
            (not relative_identity and (path.is_symlink() or any(p.is_symlink() for p in path.parents)))):
        result.errors.append(Issue('unsupported_path', 'Invalid logical document path.', name))
    elif not policy.selected(name):
        result.skipped_files.append(Issue('excluded_path', 'File is excluded by the wrapper policy.', name))
        return result.finish()
    elif len(text.encode('utf-8')) > MAX_BYTES:
        result.errors.append(Issue('file_limit', 'Document exceeds the 1 MiB file limit.', name))
    vale = shutil.which('vale')
    if not vale:
        result.errors.append(Issue('missing_vale', 'Vale is missing from PATH.'))
    if result.errors:
        return result.finish()
    identity = Path(name) if relative_identity else path
    if not relative_identity and result.coverage.source == 'project':
        identity = Path(_vale_path(root, path))
    logical = str(identity.with_suffix(identity.suffix.lower())) if result.coverage.source == 'bundled' else str(identity)
    result_path = str(path)
    return _execute(root, result, [([(name, path)], logical)], deadline, vale, document=text,
                    result_paths={name: result_path})


def _execute(root, result, jobs, deadline, vale, *, document=None, captured=None, result_paths=None):
    captured_bytes = 0
    for batch, logical in jobs:
        command = [vale, '--no-global', '--config', result.config_path, '--output=JSON']
        if logical:
            mapping = {}
            _map_vale_path(mapping, logical, (result_paths or {}).get(batch[0][0], str(batch[0][1])))
        else:
            mapping = {}
            for name, path in batch:
                _map_vale_path(mapping, _vale_path(root, path), str(path))
        try:
            deadline.check()
            content = None
            if logical:
                path = batch[0][1]
                command += ['--ext=' + Path(logical).suffix, '--path=' + logical]
                if document is None:
                    with path.open('rb') as source:
                        raw = source.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise ValueError('Document exceeds the 1 MiB file limit.')
                    content = raw.decode('utf-8')
                else:
                    content = document
                if captured is not None:
                    size = len(content.encode('utf-8'))
                    retained = captured_bytes + size <= MAX_DOCUMENT_BYTES
                    captured[batch[0][0]] = content if retained else None
                    if retained:
                        captured_bytes += size
            else:
                command += ['--', *(_vale_path(root, path) for name, path in batch)]
            proc = run_process(command, input=content, cwd=root, deadline=deadline, timeout=20)
            try:
                found, issues = decode_findings(proc.stdout, mapping)
            except (ValueError, TypeError) as exc:
                raise RuntimeError((proc.stderr or proc.stdout).strip() or str(exc)) from exc
            result.findings.extend(found)
            result.errors.extend(issues)
            if proc.stderr.strip() or proc.returncode not in (0, 1) or (proc.returncode and not found):
                raise RuntimeError(proc.stderr.strip() or f'Vale exited with status {proc.returncode}.')
            if not issues:
                result.submitted_files.extend(name for name, path in batch)
        except DeadlineExceeded as exc:
            # Keep completed findings/submissions so orchestration can retry only
            # unfinished files, without processing further batches after expiry.
            result.errors.append(Issue('timeout', str(exc)))
            return result.finish()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            for name, path in batch:
                result.errors.append(Issue('engine_error', str(exc), name))
    return result.finish()
