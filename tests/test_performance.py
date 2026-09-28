"""Operation-count, deadline, retry, and simultaneous-process contracts."""
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts'
sys.path.insert(0, str(SCRIPTS))
import prose_lint as hook


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.file = self.root / 'guide.md'
        self.file.write_text('Use this file.\n')
        self.payload = dict(hook_event_name='PreToolUse', session_id='perf', cwd=str(self.root), tool_name='Read')
        self.directory = self.root / '.git/vale-state'
        self.state = self.directory / (hashlib.sha256(b'perf').hexdigest() + '.json')

    def event(self, event, **extra):
        return hook.run_hook(dict(self.payload, hook_event_name=event, **extra))

    def deadline_module(self):
        self.assertTrue((SCRIPTS / 'deadline.py').exists(), 'deadline implementation is missing')
        return importlib.import_module('deadline')

    def test_initialized_pre_does_not_snapshot(self):
        self.event('PreToolUse')
        with patch.object(hook, 'snapshot', side_effect=AssertionError('redundant scan')):
            self.assertEqual(self.event('PreToolUse'), {})

    def test_unchanged_event_does_not_replace_state(self):
        self.event('PreToolUse')
        stat = self.state.stat()
        self.event('PreToolUse')
        self.event('PostToolUse')
        self.assertEqual((stat.st_ino, stat.st_mtime_ns),
                         (self.state.stat().st_ino, self.state.stat().st_mtime_ns))

    def test_partial_batch_remains_pending(self):
        module = self.deadline_module()
        self.event('PreToolUse')
        self.file.write_text('We will use this, e.g. for testing.\n')
        from vale_runner import empty_result
        from lint_result import Issue
        def fail(root, names, **kw):
            result = empty_result(root, names)
            result.errors.append(Issue('timeout', 'Controlled timeout', names[0]))
            return result.finish()
        with patch.object(hook, 'run_check', side_effect=fail):
            self.assertIn('hookSpecificOutput', self.event('PostToolUse'))
        self.assertEqual(json.loads(self.state.read_text())['pending'], ['guide.md'])
        # No further file change: the next read still retries the failed file.
        self.assertIn('hookSpecificOutput', self.event('PostToolUse'))
        self.assertEqual(json.loads(self.state.read_text())['pending'], [])

    def test_legacy_state_migration(self):
        self.directory.mkdir()
        self.state.write_text(json.dumps(dict(files={}, touched=['guide.md'])))
        self.event('PreToolUse')
        data = json.loads(self.state.read_text())
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['touched'], ['guide.md'])

    def test_unknown_state_schema_is_incomplete(self):
        self.directory.mkdir()
        self.state.write_text(json.dumps(dict(schema_version=999, files={}, touched=[], pending=[])))
        before = self.state.read_bytes()
        response = self.event('PostToolUse')
        self.assertIn('could not complete', response['hookSpecificOutput']['additionalContext'])
        self.assertEqual(before, self.state.read_bytes())

    def test_lock_timeout_retains_state(self):
        module = self.deadline_module()
        self.event('PreToolUse')
        before = self.state.read_bytes()
        lock = self.state.with_suffix('.lock')
        with lock.open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            start = time.monotonic()
            result = hook.run_hook(dict(self.payload, hook_event_name='PostToolUse'),
                                   deadline=module.Deadline(0.08))
            self.assertLess(time.monotonic() - start, 1.08)
            self.assertIn('could not complete', result['hookSpecificOutput']['additionalContext'])
        self.assertEqual(before, self.state.read_bytes())

    def test_deadline_covers_workspace_discovery(self):
        module = self.deadline_module()
        with patch.object(hook, 'workspace', side_effect=module.DeadlineExceeded('discovery timed out')):
            result = hook.run_hook(self.payload, deadline=module.Deadline(0.01))
        self.assertIn('could not complete', result['systemMessage'])

    def test_directory_walk_checks_deadline(self):
        module = self.deadline_module()
        # Missing Git executable forces the non-Git directory walk.
        with patch.object(hook, 'git', side_effect=FileNotFoundError()):
            with self.assertRaises(module.DeadlineExceeded):
                hook.snapshot(self.root, deadline=module.Deadline(0))

    def test_timed_out_child_is_reaped(self):
        module = self.deadline_module()
        marker = self.root / 'late-write'
        child = ('import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'
                 + repr(f'import time;from pathlib import Path;time.sleep(.35);Path({str(marker)!r}).touch()')
                 + ']);time.sleep(10)')
        start = time.monotonic()
        with self.assertRaises(module.DeadlineExceeded):
            module.run_process([sys.executable, '-c', child], deadline=module.Deadline(.1))
        self.assertLess(time.monotonic() - start, 1.1)
        time.sleep(.4)
        self.assertFalse(marker.exists())

    def test_output_limit_is_enforced(self):
        module = self.deadline_module()
        with self.assertRaises(RuntimeError):
            module.run_process([sys.executable, '-c', 'print("x" * 10000)'], max_output=100,
                               deadline=module.Deadline(2))

    def test_same_session_writers_preserve_union(self):
        self.event('PreToolUse')
        barrier = self.root / 'go'
        processes = []
        code = '''import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import prose_lint
root=Path(sys.argv[2]); name=sys.argv[3]
(root/(name+'.ready')).touch()
while not (root/'go').exists(): time.sleep(.01)
(root/(name+'.md')).write_text('Use this file.\\n')
print(json.dumps(prose_lint.run_hook(dict(hook_event_name='PostToolUse',session_id='perf',cwd=str(root),tool_name='Write',tool_input={'file_path':str(root/(name+'.md'))}))))
'''
        for name in ('a', 'b'):
            processes.append(subprocess.Popen([sys.executable, '-c', code, str(SCRIPTS), str(self.root), name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        try:
            end = time.monotonic() + 3
            while len(list(self.root.glob('*.ready'))) < 2 and time.monotonic() < end:
                time.sleep(.01)
            self.assertEqual(len(list(self.root.glob('*.ready'))), 2)
            barrier.touch()
            for proc in processes:
                stdout, stderr = proc.communicate(timeout=5)
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertEqual(json.loads(stdout), {})
        finally:
            for proc in processes:
                if proc.poll() is None: proc.kill(); proc.wait()
        self.assertEqual(set(json.loads(self.state.read_text())['touched']), {'a.md', 'b.md'})

    def test_separate_sessions_do_not_block_each_other(self):
        module = self.deadline_module()
        self.event('PreToolUse')
        with self.state.with_suffix('.lock').open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            result = hook.run_hook(dict(self.payload, session_id='independent'), deadline=module.Deadline(1))
            self.assertEqual(result, {})
