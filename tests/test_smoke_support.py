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
