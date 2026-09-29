#!/usr/bin/env python3
"""Measure complete hook processes in disposable Git workspaces."""
import argparse
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

HOOK = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts/prose_lint.py'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/vale/scripts'))
from deadline import run_process

FIXTURE_CONTENT = b'# Doc\n'
FIXTURE = dict(description='One Python comment per file; the hook receives Read tool events.',
               extension='.py', bytes_per_file=len(FIXTURE_CONTENT),
               tool_name='Read', events=['PreToolUse', 'PostToolUse'], warmup_runs_per_event=1)


def create_fixture_files(root, count):
    """Write benchmark fixtures with stable, platform-independent bytes."""
    for number in range(count):
        (root / f'f{number}.py').write_bytes(FIXTURE_CONTENT)


def bounded_count(value):
    count = int(value)
    if not 1 <= count <= 20000:
        raise argparse.ArgumentTypeError('Choose a file count from 1 to 20000.')
    return count


def probe_metadata(command, *, cwd=None, max_output=4096):
    """Return short command output, or None when optional metadata is unavailable."""
    try:
        result = run_process(command, cwd=cwd, timeout=2, max_output=max_output)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def collect_metadata(root=ROOT):
    return dict(plugin_commit=probe_metadata(
                    ['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'],
                    cwd=root, max_output=256),
                vale_version=probe_metadata(['vale', '--version'], cwd=root),
                fixture=FIXTURE)


def benchmark(count, samples):
    with tempfile.TemporaryDirectory(prefix='vale-benchmark-') as tmp:
        root = Path(tmp).resolve()
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        create_fixture_files(root, count)
        timings = {}
        for event in ('PreToolUse', 'PostToolUse'):
            measurements = []
            writes = 0
            for trial in range(samples + 1):
                state = next((root / '.git/vale-state').glob('*.json'), None)
                before = state.stat().st_mtime_ns if state else None
                payload = dict(hook_event_name=event, cwd=str(root), session_id='benchmark', tool_name='Read')
                start = time.perf_counter()
                run = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                     cwd=root, capture_output=True, text=True, timeout=60)
                elapsed = time.perf_counter() - start
                if run.returncode or json.loads(run.stdout) != {}:
                    raise RuntimeError(run.stdout + run.stderr)
                state = next((root / '.git/vale-state').glob('*.json'))
                if trial:
                    measurements.append(elapsed)
                    writes += int(before != state.stat().st_mtime_ns)
            timings[event] = dict(median=statistics.median(measurements), samples=measurements,
                                  state_writes=writes)
        return dict(files=count, timings=timings, state_bytes=state.stat().st_size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', nargs='+', type=bounded_count, default=[1000, 4000, 20000])
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error('--samples must be between 1 and 100')
    result = dict(platform=platform.platform(), python=sys.version, **collect_metadata(ROOT),
                  results=[benchmark(count, args.samples) for count in args.files])
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for row in result['results']:
        print(f"{row['files']} files: " + ', '.join(f'{event} {data["median"]:.3f}s' for event, data in row['timings'].items()))


if __name__ == '__main__':
    main()
