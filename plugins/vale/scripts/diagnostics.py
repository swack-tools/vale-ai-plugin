"""Read-only environment diagnostics; installation files do not prove activation."""
from dataclasses import asdict
import json
import re
import shutil
import subprocess

from deadline import Deadline, DeadlineExceeded, run_process
from vale_runner import empty_result
from policy import EXTENSIONS, load_policy


def empty_diagnostics(root):
    initial = empty_result(root)
    vale = shutil.which('vale')
    report = dict(schema_version=1, overall_status='ready',
                  executable={'path': vale, 'version': None},
                  config={'config_path': initial.config_path, 'status': 'unverified'},
                  formats={}, errors=[], coverage=asdict(initial.coverage),
                  installation={'activation': 'unknown', 'project_files': []},
                  workspace=str(root))
    return report


def inspect_environment(root, *, cli_overrides=None, deadline=None):
    deadline = deadline or Deadline(20)
    report = empty_diagnostics(root)
    try:
        deadline.check()
        policy = load_policy(root, cli_overrides)
        deadline.check()
        report['policy'] = asdict(policy)
        selected = empty_result(root, policy=policy)
        report['config']['config_path'] = selected.config_path
        report['coverage'] = asdict(selected.coverage)
    except (OSError, ValueError, DeadlineExceeded, subprocess.TimeoutExpired) as exc:
        report['overall_status'] = 'incomplete'
        report['errors'].append(str(exc))
        return report
    vale = report['executable']['path']
    try:
        for name in ('.codex/hooks.json', '.claude/settings.json'):
            deadline.check()
            if (root / name).is_file():
                report['installation']['project_files'].append(name)
        extensions = {ext[1:]: ext[1:] for ext in EXTENSIONS}
        extensions.update(policy.formats)
        for extension, format_name in sorted(extensions.items()):
            deadline.check()
            parser = {'rst': 'rst2html', 'adoc': 'asciidoctor'}.get(format_name)
            found = shutil.which(parser) if parser else None
            report['formats'][extension] = dict(status='missing_parser' if parser and not found else 'available',
                                                    parser=parser, executable=found)
        for extension, view in policy.views.items():
            deadline.check()
            report['formats'][extension] = dict(status='configured_view', parser=None, executable=None, view=view)
    except (OSError, DeadlineExceeded, subprocess.TimeoutExpired) as exc:
        report['overall_status'] = 'incomplete'
        report['errors'].append(str(exc))
        return report
    try:
        deadline.check()
        if not vale:
            raise RuntimeError('Vale is missing from PATH. Install Vale 3.23 or later.')
        version = run_process([vale, '--version'], deadline=deadline, timeout=5, max_output=1024 * 1024)
        match = re.fullmatch(r'vale version (\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?', version.stdout.strip())
        if version.returncode or not match:
            raise RuntimeError('The selected executable did not report a recognized Vale version.')
        report['executable']['version'] = '.'.join(match.groups())
        if tuple(map(int, match.groups())) < (3, 23, 0):
            raise RuntimeError('Vale 3.23 or later is required.')
        config = run_process([vale, '--no-global', '--config', report['config']['config_path'], 'ls-config'],
                             cwd=root, deadline=deadline, timeout=5, max_output=1024 * 1024)
        if config.returncode or config.stderr.strip():
            raise RuntimeError((config.stderr or config.stdout).strip() or 'Vale could not load the selected configuration.')
        parsed = json.loads(config.stdout)
        if not isinstance(parsed, dict):
            raise ValueError('Vale returned an invalid configuration description.')
        report['config']['status'] = 'loaded'
    except (OSError, ValueError, RuntimeError, DeadlineExceeded, subprocess.TimeoutExpired) as exc:
        report['overall_status'] = 'incomplete'
        report['errors'].append(str(exc))
    return report


def render_diagnostics(report):
    lines = [f"Vale readiness: {report['overall_status']}",
             f"Executable: {report['executable']['path'] or 'not found'}",
             f"Version: {report['executable']['version'] or 'unknown'}",
             f"Configuration: {report['config']['config_path']} ({report['config']['status']})",
             f"Workspace: {report['workspace']}",
             'Running client activation: unknown; inspect the client hook settings.',
             report['coverage']['note']]
    if 'policy' in report:
        for key in ('schema_version', 'scope', 'include', 'exclude', 'profile'):
            lines.append(f"Policy {key}: {report['policy'][key]} ({report['policy']['origins'][key]})")
    for ext, data in report['formats'].items():
        if data['status'] == 'missing_parser':
            lines.append(f".{ext}: missing {data['parser']}; install the optional parser and expose it on PATH.")
    lines.extend('Incomplete: ' + error for error in report['errors'])
    return '\n'.join(lines)
