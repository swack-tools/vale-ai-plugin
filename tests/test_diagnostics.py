"""Doctor inspects capabilities without changing the project or client settings."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts/prose_lint.py'


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = os.environ.copy()

    def doctor(self):
        result = subprocess.run([sys.executable, str(HOOK), '--doctor', '--format', 'json'],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertTrue(result.stdout.startswith('{'), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def fake(self, body):
        binpath = self.root / 'bin'; binpath.mkdir()
        command = binpath / 'vale'
        command.write_text('#!' + sys.executable + '\nimport sys\n' + body)
        command.chmod(0o755)
        self.env['PATH'] = str(binpath)

    def test_doctor_missing_vale(self):
        self.env['PATH'] = str(self.root)
        code, result = self.doctor()
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')

    def test_doctor_optional_parser_warning(self):
        self.fake("print('vale version 3.23.0' if '--version' in sys.argv else '{}')\n")
        code, result = self.doctor()
        self.assertEqual(code, 0)
        self.assertEqual(result['formats']['rst']['status'], 'missing_parser')
        self.assertEqual(result['formats']['md']['status'], 'available')

    def test_doctor_wrong_binary(self):
        self.fake("print('a different tool 7.0')\n")
        code, result = self.doctor()
        self.assertEqual(code, 2)
        self.assertTrue(result['errors'])

    def test_doctor_invalid_config(self):
        (self.root / '.vale.ini').write_text('StylesPath = not-here\n[*.md]\nBasedOnStyles = NoSuchStyle\n')
        before = (self.root / '.vale.ini').read_bytes()
        code, result = self.doctor()
        self.assertEqual(code, 2)
        self.assertTrue(result['errors'])
        self.assertEqual(before, (self.root / '.vale.ini').read_bytes())
        self.assertFalse((self.root / '.codex').exists())

    def test_doctor_does_not_claim_host_activation(self):
        (self.root / '.codex').mkdir()
        (self.root / '.codex/hooks.json').write_text('{"hooks":{}}')
        code, result = self.doctor()
        self.assertEqual(code, 0)
        self.assertEqual(result['installation']['activation'], 'unknown')
        self.assertEqual(result['coverage']['verification'], 'configured_invocation')
        self.assertIn('config_path', result['config'])

    def run_with_deadline(self, *, fake_git=None, fake_vale=None, seconds=0.08):
        scripts = self.root / 'bin'
        scripts.mkdir(exist_ok=True)
        if fake_git:
            command = scripts / 'git'
            command.write_text('#!' + sys.executable + '\n' + fake_git)
            command.chmod(0o755)
        if fake_vale:
            command = scripts / 'vale'
            command.write_text('#!' + sys.executable + '\n' + fake_vale)
            command.chmod(0o755)
        self.env['PATH'] = str(scripts) + os.pathsep + os.defpath
        import importlib
        sys.path.insert(0, str(HOOK.parent))
        self.addCleanup(lambda: sys.path.remove(str(HOOK.parent)))
        prose_lint = importlib.import_module('prose_lint')
        from deadline import Deadline
        with patch.object(prose_lint, 'Deadline', lambda _seconds: Deadline(seconds)), \
             patch.dict(os.environ, {'PATH': self.env['PATH']}), \
             patch.object(sys, 'argv', [str(HOOK), '--doctor', '--format', 'json']), \
             patch('pathlib.Path.cwd', return_value=self.root), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            code = prose_lint.main()
        return code, json.loads(output.getvalue())

    def test_doctor_deadline_includes_workspace_discovery(self):
        started = time.monotonic()
        code, result = self.run_with_deadline(fake_git='import time\ntime.sleep(2)\n')
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')
        self.assertTrue(any('deadline' in error.lower() or 'timed out' in error.lower()
                            for error in result['errors']))
        self.assertEqual(list(self.root.iterdir()), [self.root / 'bin'])

    def test_doctor_probe_uses_shared_deadline(self):
        code, result = self.run_with_deadline(
            fake_vale='import sys, time\n'
                      "time.sleep(2) if '--version' in sys.argv else print('{}')\n")
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')
        self.assertTrue(result['errors'])
        self.assertFalse((self.root / '.codex').exists())

    def test_doctor_second_probe_uses_remaining_shared_deadline(self):
        started = time.monotonic()
        code, result = self.run_with_deadline(
            fake_vale='import sys, time\n'
                      "if '--version' in sys.argv:\n"
                      "    time.sleep(.05)\n"
                      "    print('vale version 3.23.0')\n"
                      'else:\n'
                      '    time.sleep(2)\n')
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')
        self.assertTrue(result['errors'])

    def test_doctor_probe_output_is_bounded(self):
        code, result = self.run_with_deadline(
            fake_vale='import sys\n'
                      "if '--version' in sys.argv:\n"
                      "    print('x' * 2_000_000)\n", seconds=2)
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')
        self.assertTrue(any('output exceeded' in error for error in result['errors']))

    def test_doctor_timeout_stops_probe_descendants(self):
        marker = self.root / 'late-child-write'
        child = "import time; time.sleep(.3); open(" + repr(str(marker)) + ", 'w').write('late')"
        body = ('import subprocess, sys, time\n'
                "if '--version' in sys.argv:\n"
                f'    subprocess.Popen([sys.executable, "-c", {child!r}])\n'
                '    time.sleep(2)\n')
        code, result = self.run_with_deadline(fake_vale=body)
        self.assertEqual(code, 2)
        self.assertEqual(result['overall_status'], 'incomplete')
        time.sleep(.4)
        self.assertFalse(marker.exists())
