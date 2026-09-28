"""Select safe file operands and normalize Vale's machine-readable results."""
import json
from pathlib import Path
import shutil
import subprocess

from deadline import Deadline, DeadlineExceeded, run_process
from lint_result import CheckResult, Coverage, Finding, Issue

PACKAGE = Path(__file__).resolve().parents[1]
EXTENSIONS = set('.md .mdx .txt .rst .adoc .html .rs .py .sh .pl .js .jsx .ts .tsx .go .c .h .cpp .hpp .java .css'.split())
EXCLUDED = {'.git', '.codex', '.claude', '.agents', '.venv', 'node_modules', 'target', 'dist', 'build', '.vale', 'vendor', '__pycache__'}
MAX_FILES = 20000
MAX_BYTES = 1024 * 1024


def eligible(root, name):
    path = root / name
    if path.suffix.lower() not in EXTENSIONS or set(Path(name).parts) & EXCLUDED:
        return False
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        return False
    return path.is_file() and path.resolve().is_relative_to(root)


def configuration(root):
    override = root / '.vale.ini'
    return override if override.is_file() else PACKAGE / '.vale.ini'


def empty_result(root, names=()):
    config = configuration(root)
    source = 'bundled' if config == PACKAGE / '.vale.ini' else 'project'
    coverage = Coverage(source, 'configured_invocation' if source == 'bundled' else 'unknown',
                        'Submitted operands are not proof of matched rules; an empty Vale result can also mean no matching configuration.')
    return CheckResult(1, 'skipped', str(config), list(names), [], [], [], [], coverage)


def decode_findings(stdout, known_paths):
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError('Vale JSON must be a path-to-alerts object.')
    findings = []
    for path, alerts in data.items():
        if path not in known_paths or not isinstance(alerts, list):
            raise ValueError('Vale returned an unexpected path or malformed alert list.')
        for alert in alerts:
            if not isinstance(alert, dict):
                raise ValueError('Vale returned a malformed alert.')
            for key in ('Check', 'Message', 'Match', 'Severity'):
                if not isinstance(alert.get(key), str):
                    raise ValueError(f'Vale alert has an invalid {key}.')
            span = alert.get('Span')
            line = alert.get('Line')
            if (type(line) is not int or line < 1 or not isinstance(span, list) or len(span) != 2 or
                    any(type(x) is not int or x < 1 for x in span) or span[1] < span[0]):
                raise ValueError('Vale returned an invalid source location.')
            suggestions = alert.get('Suggestions') or []
            action = alert.get('Action') or None
            link = alert.get('Link') or None
            if (not isinstance(suggestions, list) or any(not isinstance(x, str) for x in suggestions) or
                    (action is not None and not isinstance(action, dict)) or
                    (link is not None and not isinstance(link, str))):
                raise ValueError('Vale returned malformed suggestion metadata.')
            findings.append(Finding(known_paths[path], line, span[0], span[1], alert['Check'],
                                    alert['Severity'], alert['Message'], alert['Match'], link, suggestions, action))
    return findings


def run_check(root, names, *, deadline=None):
    deadline = deadline or Deadline(50)
    result = empty_result(root, names)
    if not names:
        return result
    vale = shutil.which('vale')
    if not vale:
        result.errors.append(Issue('missing_vale', 'Vale is missing from PATH. Install Vale 3.23 or later, then restart your coding agent.'))
        return result.finish()
    paths, aliases = [], []
    for name in sorted(set(names)):
        try:
            deadline.check()
            if not eligible(root, name):
                result.errors.append(Issue('unsupported_path', f'Unsupported file or path outside the workspace: {name}', name))
                continue
            path = (root / name).resolve()
            if path.stat().st_size > MAX_BYTES:
                result.errors.append(Issue('file_limit', f'{name} exceeds the 1 MiB file limit; exclude or split it before checking.', name))
                continue
            if result.coverage.source == 'bundled' and path.suffix != path.suffix.lower():
                aliases.append((name, path))
            else:
                paths.append((name, path))
        except OSError as exc:
            result.errors.append(Issue('file_error', str(exc), name))
    jobs = [(paths[i:i+50], None) for i in range(0, len(paths), 50)]
    jobs += [([pair], str(pair[1].with_suffix(pair[1].suffix.lower()))) for pair in aliases]
    for batch, logical in jobs:
        command = [vale, '--no-global', '--config', result.config_path, '--output=JSON']
        mapping = {str(path): str(path) for name, path in batch}
        try:
            deadline.check()
            content = None
            if logical:
                path = batch[0][1]
                command += ['--ext=' + path.suffix.lower(), '--path=' + logical]
                content = path.read_text(encoding='utf-8')
                mapping = {logical: str(path)}
            else:
                command += ['--', *(str(path) for name, path in batch)]
            proc = run_process(command, input=content, cwd=root, deadline=deadline, timeout=20)
            try:
                found = decode_findings(proc.stdout, mapping)
            except (ValueError, TypeError) as exc:
                raise RuntimeError((proc.stderr or proc.stdout).strip() or str(exc)) from exc
            result.findings.extend(found)
            if proc.stderr.strip() or proc.returncode not in (0, 1) or (proc.returncode and not found):
                raise RuntimeError(proc.stderr.strip() or f'Vale exited with status {proc.returncode}.')
            result.submitted_files.extend(name for name, path in batch)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            for name, path in batch:
                result.errors.append(Issue('engine_error', str(exc), name))
    return result.finish()
