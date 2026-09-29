#!/usr/bin/env python3
"""Present shared prose-checker results as read-only GitHub annotations."""
import json
from pathlib import Path

LIMIT = 50


def validate_result(result):
    """Reject incompatible or contradictory results instead of reporting clean."""
    if not isinstance(result, dict) or type(result.get('schema_version')) is not int or result['schema_version'] != 1:
        raise ValueError('Expected checker schema version 1.')
    if result.get('comparison') is not None:
        raise ValueError('CI annotations require full-file results.')
    for name in ('requested_files', 'submitted_files', 'skipped_files', 'findings', 'errors'):
        if not isinstance(result.get(name), list):
            raise ValueError(f'Invalid {name} array.')
    for name in ('requested_files', 'submitted_files'):
        if any(not isinstance(value, str) for value in result[name]):
            raise ValueError(f'Invalid {name} path.')
    if not isinstance(result.get('config_path'), str) or not isinstance(result.get('coverage'), dict):
        raise ValueError('Missing configuration or coverage metadata.')
    for issue in result['errors'] + result['skipped_files']:
        if (not isinstance(issue, dict) or not isinstance(issue.get('code'), str)
                or not isinstance(issue.get('message'), str)
                or not (issue.get('path') is None or isinstance(issue['path'], str))):
            raise ValueError('Invalid checker diagnostic.')
    for finding in result['findings']:
        if not isinstance(finding, dict):
            raise ValueError('Invalid finding.')
        if any(not isinstance(finding.get(key), str) for key in ('path', 'rule', 'message', 'match')):
            raise ValueError('Invalid finding text.')
        if finding.get('severity') not in ('error', 'warning', 'suggestion'):
            raise ValueError('Invalid finding severity.')
        for key in ('line', 'column'):
            if type(finding.get(key)) is not int or finding[key] < 1:
                raise ValueError('Invalid finding position.')
        end = finding.get('end_column')
        if end is not None and (type(end) is not int or end < finding['column']):
            raise ValueError('Invalid finding end column.')
    expected = ('incomplete' if result['errors'] else 'findings' if result['findings'] else
                'clean' if result['submitted_files'] else 'skipped')
    if result.get('status') != expected:
        raise ValueError('Checker status contradicts its result.')


def escape(value, *, property=False):
    # Match actions/toolkit packages/core/src/command.ts; escape % first.
    value = str(value).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    return value.replace(':', '%3A').replace(',', '%2C') if property else value


def command(level, message, properties):
    props = ','.join(f'{key}={escape(value, property=True)}' for key, value in properties.items())
    return f'::{level}' + (f' {props}' if props else '') + f'::{escape(message)}'


def location(finding):
    """Keep virtual, missing, symlinked, or stale locations out of file annotations."""
    path = Path(finding['path'])
    root = Path.cwd().resolve()
    try:
        candidate = path if path.is_absolute() else root / path
        relative = candidate.relative_to(root)
        if '..' in relative.parts or any(part.startswith('<stdin:') for part in relative.parts):
            return {}
        if any(parent.is_symlink() for parent in [candidate, *candidate.parents] if parent != root):
            return {}
        candidate.resolve(strict=True).relative_to(root)
        if not candidate.is_file() or candidate.stat().st_size > 1024 * 1024:
            return {}
        lines = candidate.read_text(encoding='utf-8').splitlines()
        if finding['line'] > len(lines):
            return {}
    except (OSError, ValueError, UnicodeError):
        return {}
    props = dict(file=relative.as_posix(), line=finding['line'], col=finding['column'])
    if finding.get('end_column') is not None:
        props['endColumn'] = finding['end_column']
    return props


def render_annotations(result: dict) -> list[str]:
    validate_result(result)
    annotations = [command('error', issue['message'], {'title': issue['code']}) for issue in result['errors'][:LIMIT]]
    for finding in result['findings'][:LIMIT - len(annotations)]:
        props = location(finding)
        props['title'] = finding['rule']
        level = {'suggestion': 'notice', 'warning': 'warning', 'error': 'error'}[finding['severity']]
        annotations.append(command(level, finding['message'], props))
    if not annotations and result['status'] == 'skipped':
        annotations.append(command('error', 'No selected files were submitted by the checker; inspect the JSON report.', {}))
    return annotations


def publish(result, output, summary=None):
    annotations = render_annotations(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + '\n')
    for annotation in annotations:
        print(annotation)
    shown_errors = min(LIMIT, len(result['errors']))
    shown_findings = min(LIMIT - shown_errors, len(result['findings']))
    if summary:
        with summary.open('a', encoding='utf-8') as stream:
            stream.write(f"## Prose check\n\nStatus: {result['status']}. "
                         f"{len(result['findings'])} findings: {shown_findings} shown, "
                         f"{len(result['findings']) - shown_findings} omitted. "
                         f"{len(result['errors'])} errors: {shown_errors} shown, "
                         f"{len(result['errors']) - shown_errors} omitted.\n\n"
                         f"Files: {len(result['requested_files'])} requested, "
                         f"{len(result['submitted_files'])} submitted, {len(result['skipped_files'])} skipped. "
                         'The JSON artifact retains the complete checker result and coverage metadata.\n')
    return {'clean': 0, 'findings': 1, 'incomplete': 2, 'skipped': 2}[result['status']]
