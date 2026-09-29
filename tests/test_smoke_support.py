"""Keep client fixture cleanup bounded without masking unrelated failures."""
import errno
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


class SmokeCleanupTests(unittest.TestCase):
    def helper(self):
        self.assertTrue((SCRIPTS / 'smoke_support.py').exists(), 'bounded fixture cleanup is missing')
        return importlib.import_module('smoke_support').temporary_workspace

    def test_transient_clone_cleanup_race_retries_owned_directory(self):
        temporary_workspace = self.helper()
        original = tempfile.TemporaryDirectory.cleanup
        attempts = []
        def transient(directory):
            attempts.append(directory.name)
            if len(attempts) == 1:
                raise OSError(errno.ENOTEMPTY, 'Background clone still writing')
            return original(directory)
        with patch.object(tempfile.TemporaryDirectory, 'cleanup', transient), patch('smoke_support.time.sleep'):
            with temporary_workspace(prefix='vale-cleanup-test-') as directory:
                path = Path(directory)
                (path / 'fixture.txt').write_text('test')
        self.assertFalse(path.exists())
        self.assertEqual(len(set(attempts)), 1)

    def test_cleanup_permission_error_is_not_hidden(self):
        temporary_workspace = self.helper()
        original = tempfile.TemporaryDirectory.cleanup
        def denied(directory):
            self.addCleanup(original, directory)
            raise PermissionError('denied')
        with patch.object(tempfile.TemporaryDirectory, 'cleanup', denied):
            with self.assertRaises(PermissionError):
                with temporary_workspace(prefix='vale-cleanup-test-'):
                    pass

    def test_continuous_clone_race_has_a_finite_retry_budget(self):
        temporary_workspace = self.helper()
        original = tempfile.TemporaryDirectory.cleanup
        def occupied(directory):
            self.addCleanup(original, directory)
            raise OSError(errno.ENOTEMPTY, 'still writing')
        with patch.object(tempfile.TemporaryDirectory, 'cleanup', occupied), patch('smoke_support.time.sleep'):
            with self.assertRaises(OSError):
                with temporary_workspace(prefix='vale-cleanup-test-'):
                    pass


class SmokeIsolationTests(unittest.TestCase):
    def test_isolated_environment_drops_credentials_and_provider_routing(self):
        helper = getattr(importlib.import_module('smoke_support'), 'isolated_environment', None)
        self.assertTrue(callable(helper), 'isolated client environment is missing')
        with tempfile.TemporaryDirectory(prefix='vale home ') as directory:
            inherited = {'PATH': '/bin', 'ANTHROPIC_API_KEY': 'secret', 'OPENAI_API_KEY': 'secret',
                         'AZURE_OPENAI_ENDPOINT': 'https://remote.invalid', 'AWS_PROFILE': 'private',
                         'CLAUDE_CONFIG_DIR': '/private', 'CODEX_HOME': '/private', 'HOME': '/private',
                         'HTTP_PROXY': 'https://private.invalid', 'GITHUB_TOKEN': 'secret',
                         'CUSTOM_PROVIDER_TOKEN': 'secret', 'GEM_HOME': '/gems'}
            env = helper(Path(directory), inherited)
            for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AWS_PROFILE',
                        'HTTP_PROXY', 'GITHUB_TOKEN', 'CUSTOM_PROVIDER_TOKEN'):
                self.assertNotIn(key, env)
            for key in ('HOME', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR'):
                self.assertTrue(Path(env[key]).is_relative_to(Path(directory)))
                self.assertTrue(Path(env[key]).is_dir())
            self.assertEqual(env['PATH'], '/bin')
            self.assertEqual(env['GEM_HOME'], '/gems')

    def test_evidence_directory_never_overwrites_existing_run(self):
        helper = getattr(importlib.import_module('smoke_support'), 'evidence_directory', None)
        self.assertTrue(callable(helper), 'isolated evidence directory is missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = helper(root / 'run', root, 'codex')
            (first / 'proof.json').write_text('{}')
            with self.assertRaises(FileExistsError):
                helper(root / 'run', root, 'codex')
            second = helper(None, root, 'codex')
            third = helper(None, root, 'codex')
            self.assertNotEqual(second, third)
            self.assertEqual((first / 'proof.json').read_text(), '{}')

    def test_native_evidence_requires_lifecycle_and_one_correction(self):
        helper = getattr(importlib.import_module('smoke_support'), 'assert_lifecycle', None)
        self.assertTrue(callable(helper), 'native lifecycle evidence validator is missing')
        trace = [{'input': {'hook_event_name': 'PreToolUse'}, 'output': {}},
                 {'input': {'hook_event_name': 'PostToolUse'}, 'output': {'hookSpecificOutput': {'additionalContext': 'Google.Latin'}}},
                 {'input': {'hook_event_name': 'Stop'}, 'output': {'decision': 'block', 'reason': 'Google.Latin'}},
                 {'input': {'hook_event_name': 'Stop', 'stop_hook_active': True}, 'output': {'systemMessage': 'Vale already requested a correction pass'}}]
        trace[3:3] = [{'input': {'hook_event_name': 'PreToolUse'}, 'output': {}},
                      {'input': {'hook_event_name': 'PostToolUse'}, 'output': {}}]
        requests = [{}, {'text': 'Google.Latin'}, {'text': 'Google.Latin Stop: Google.Latin'}, {}]
        for record in trace:
            record['exit_code'] = 0
        result = helper(trace, requests, True, '')
        self.assertFalse(result['active_stop_model_visible'])
        self.assertFalse(result['active_stop_stdout_visible'])
        for broken in (trace[1:], trace[:2], trace + [trace[2]]):
            with self.subTest(trace=broken), self.assertRaises(AssertionError):
                helper(broken, requests, True, '')
        with self.assertRaises(AssertionError):
            helper(trace, [{}, {}, {}, {}], True, '')

        with self.assertRaises(AssertionError):
            helper(trace, [{}, {'text':'Google.Latin'}, {'text':'Google.Latin'}, {}], True, '')

    def test_failed_hook_and_changed_delivery_cannot_pass(self):
        from copy import deepcopy
        from smoke_support import assert_lifecycle
        marker = 'Vale already requested a correction pass'
        trace = [
            {'input': {'hook_event_name': 'PreToolUse'}, 'output': {}, 'exit_code': 0},
            {'input': {'hook_event_name': 'PostToolUse'}, 'output': {}, 'exit_code': 0},
            {'input': {'hook_event_name': 'Stop'}, 'output': {'decision': 'block'}, 'exit_code': 0},
            {'input': {'hook_event_name': 'Stop', 'stop_hook_active': True},
             'output': {'systemMessage': marker}, 'exit_code': 0},
        ]
        trace[3:3] = [{'input': {'hook_event_name': 'PreToolUse'}, 'output': {}, 'exit_code': 0},
                      {'input': {'hook_event_name': 'PostToolUse'}, 'output': {}, 'exit_code': 0}]
        requests = [{}, {'text': 'Google.Latin'}, {'text': 'Google.Latin Google.Latin'}, {}]
        for broken in (trace[:3] + trace[4:], trace[:4] + trace[5:],
                       trace[:3] + [trace[4], trace[3]] + trace[5:]):
            with self.subTest(events=[r['input']['hook_event_name'] for r in broken]), self.assertRaises(AssertionError):
                assert_lifecycle(broken, requests, True, '')
        for index in range(len(trace)):
            broken = deepcopy(trace)
            broken[index]['exit_code'] = 1
            with self.subTest(event=index), self.assertRaises(AssertionError):
                assert_lifecycle(broken, requests, True, '')
        with self.subTest(channel='stdout'), self.assertRaises(AssertionError):
            assert_lifecycle(trace, requests, True, marker)
        assert_lifecycle(trace, requests, True, marker, host='claude')
        with self.subTest(channel='claude stdout'), self.assertRaises(AssertionError):
            assert_lifecycle(trace, requests, True, '', host='claude')
        missing = deepcopy(trace)
        del missing[0]['exit_code']
        with self.subTest(exit_code='missing'), self.assertRaises(AssertionError):
            assert_lifecycle(missing, requests, True, '')
        changed = deepcopy(requests)
        changed[-1]['text'] = marker
        with self.subTest(channel='model'), self.assertRaises(AssertionError):
            assert_lifecycle(trace, changed, True, '')

    def test_client_timeout_preserves_output_and_requests(self):
        import json
        import os
        import subprocess
        helper = getattr(importlib.import_module('smoke_support'), 'run_fixture_client', None)
        self.assertTrue(callable(helper), 'timeout evidence persistence is missing')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            requests = [{'synthetic': 'request received'}]
            code = 'import sys,time; print("ready",flush=True); print("diagnostic",file=sys.stderr,flush=True); time.sleep(5)'
            with self.assertRaises(subprocess.TimeoutExpired):
                helper([sys.executable, '-c', code], cwd=output, env=os.environ.copy(), timeout=1,
                       evidence=output, host='test', requests=requests)
            self.assertIn('ready', (output / 'test-smoke.jsonl').read_text())
            self.assertIn('diagnostic', (output / 'test-smoke.stderr').read_text())
            self.assertEqual(json.loads((output / 'test-smoke-requests.json').read_text()), requests)
