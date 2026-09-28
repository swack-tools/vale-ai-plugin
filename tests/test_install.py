import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'scripts/install.py'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vale install ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / '.codex'
        self.config.mkdir()
        self.hooks = self.config / 'hooks.json'
        self.original = {'description': 'Keep this', 'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo existing'}]}]}}
        self.hooks.write_text(json.dumps(self.original))

    def install(self, *args, env=None):
        return subprocess.run([sys.executable, str(INSTALLER), *args], capture_output=True, text=True, env=env)

    def test_project_merge_repeat_uninstall(self):
        for _ in range(2):
            result = self.install('--project', str(self.root))
            self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.hooks.read_text())
        self.assertEqual(data['description'], 'Keep this')
        self.assertEqual(len(data['hooks']['Stop']), 2)
        self.assertTrue((self.config / 'vale/scripts/prose_lint.py').is_file())
        self.assertEqual(data['hooks']['Stop'][0], self.original['hooks']['Stop'][0])
        self.assertNotIn(str(self.root), data['hooks']['Stop'][1]['hooks'][0]['command'])
        self.assertEqual(self.install('--project', str(self.root), '--uninstall').returncode, 0)
        self.assertEqual(json.loads(self.hooks.read_text()), self.original)

    def test_user_respects_codex_home(self):
        env = dict(os.environ, CODEX_HOME=str(self.config))
        result = self.install('--user', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.config / 'vale/styles/Google/Latin.yml').exists())
        command = json.loads(self.hooks.read_text())['hooks']['PreToolUse'][0]['hooks'][0]['command']
        self.assertIn('CODEX_HOME', command)

    def test_invalid_json_preserved(self):
        self.hooks.write_text('{invalid')
        result = self.install('--project', str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.hooks.read_text(), '{invalid')

    def test_unowned_directory_preserved(self):
        (self.config / 'vale').mkdir()
        (self.config / 'vale/user-data').write_text('preserve')
        result = self.install('--project', str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.config / 'vale/user-data').read_text(), 'preserve')
