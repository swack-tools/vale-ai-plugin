"""Benchmark output describes its workload and source revisions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/benchmark_hooks.py'
sys.path.insert(0, str(SCRIPT.parent))
import benchmark_hooks


class BenchmarkMetadataTests(unittest.TestCase):
    def test_revision_and_engine_probes_are_bounded_and_optional(self):
        root = Path('/tmp/benchmark-root')
        with patch.object(benchmark_hooks, 'run_process', side_effect=[
            subprocess.CompletedProcess([], 0, 'a' * 40 + '\n', ''),
            subprocess.CompletedProcess([], 0, 'vale version 3.23.0\n', ''),
        ]) as run:
            metadata = benchmark_hooks.collect_metadata(root)

        self.assertEqual(metadata['plugin_commit'], 'a' * 40)
        self.assertEqual(metadata['vale_version'], 'vale version 3.23.0')
        self.assertEqual(run.call_count, 2)
        self.assertEqual([call.kwargs['max_output'] for call in run.call_args_list], [256, 4096])
        self.assertEqual(run.call_args_list[0].args[0],
                         ['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'])
        self.assertEqual(run.call_args_list[1].args[0], ['vale', '--version'])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['timeout'], 2)

    def test_one_unavailable_metadata_probe_does_not_hide_the_other(self):
        with patch.object(benchmark_hooks, 'run_process', side_effect=[
            FileNotFoundError('git is unavailable'),
            subprocess.CompletedProcess([], 0, 'vale version 3.23.0\n', ''),
        ]):
            metadata = benchmark_hooks.collect_metadata(Path('/tmp/benchmark-root'))
        self.assertIsNone(metadata['plugin_commit'])
        self.assertEqual(metadata['vale_version'], 'vale version 3.23.0')
        self.assertEqual(metadata['fixture']['bytes_per_file'], 6)

    def test_missing_metadata_does_not_prevent_benchmark_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'benchmark.json'
            result = dict(files=1, timings={'PreToolUse': {'median': 0.01},
                                           'PostToolUse': {'median': 0.02}}, state_bytes=100)
            with patch.object(sys, 'argv', [str(SCRIPT), '--files', '1', '--samples', '1',
                                            '--output', str(output)]), \
                patch.object(benchmark_hooks, 'collect_metadata', return_value={
                     'plugin_commit': None, 'vale_version': None,
                     'fixture': {'description': 'One Python comment per file; the hook receives Read tool events.',
                                 'extension': '.py', 'bytes_per_file': 6, 'tool_name': 'Read',
                                 'events': ['PreToolUse', 'PostToolUse'], 'warmup_runs_per_event': 1},
                 }), \
                 patch.object(benchmark_hooks, 'benchmark', return_value=result):
                benchmark_hooks.main()

            document = json.loads(output.read_text())
        self.assertIsNone(document['plugin_commit'])
        self.assertIsNone(document['vale_version'])
        self.assertEqual(document['fixture']['description'],
                         'One Python comment per file; the hook receives Read tool events.')
        self.assertEqual(document['fixture']['bytes_per_file'], 6)
        self.assertEqual(document['fixture']['events'], ['PreToolUse', 'PostToolUse'])
        self.assertEqual(document['results'], [result])
