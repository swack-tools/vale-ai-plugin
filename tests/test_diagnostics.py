"""Doctor inspects capabilities without changing the project or client settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
