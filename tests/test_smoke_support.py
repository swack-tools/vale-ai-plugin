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
        requests = [{}, {'text': 'Google.Latin'}, {'text': 'Google.Latin Stop: Google.Latin'}, {}]
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
