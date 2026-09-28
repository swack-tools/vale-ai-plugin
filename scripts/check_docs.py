#!/usr/bin/env python3
"""Require zero Google findings, including suggestions, in authored documentation."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/vale/scripts'))
from deadline import run_process
from lint_result import Issue, render_text
from vale_runner import PACKAGE, decode_findings, empty_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='*', type=Path, help='Optional specific documentation files to check.')
    args = parser.parse_args()
    paths = [p.resolve() for p in args.files] if args.files else [
        ROOT / 'README.md', ROOT / 'evals/README.md', *sorted((ROOT / 'docs').rglob('*.md')),
        *sorted((PACKAGE / 'skills').rglob('*.md')), *sorted((PACKAGE / 'prompts').rglob('*.md')),
    ]
    result = empty_result(ROOT, [str(p) for p in paths])
    result.config_path = str(PACKAGE / '.vale.ini')
    try:
        proc = run_process(['vale', '--no-global', '--config', result.config_path,
                            '--minAlertLevel=suggestion', '--output=JSON', '--', *map(str, paths)])
        result.findings, result.errors = decode_findings(proc.stdout, {str(p): str(p) for p in paths})
        if proc.stderr.strip() or proc.returncode not in (0, 1) or (proc.returncode and not result.findings):
            result.errors.append(Issue('engine_error', proc.stderr.strip() or f'Vale exited with status {proc.returncode}.'))
        if not result.errors:
            result.submitted_files = [str(p) for p in paths]
    except (OSError, ValueError, RuntimeError) as exc:
        result.errors.append(Issue('documentation_error', str(exc)))
    result.finish()
    print(render_text(result))
    return result.exit_code


if __name__ == '__main__':
    sys.exit(main())
