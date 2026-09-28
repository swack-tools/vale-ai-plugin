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

    def test_claude_settings_preserved_and_uninstalled(self):
        config = self.root / '.claude'
        config.mkdir()
        settings = config / 'settings.json'
        original = dict(self.original, permissions={'allow': ['Read']})
        settings.write_text(json.dumps(original))
        for _ in range(2):
            result = self.install('--host', 'claude', '--project', str(self.root))
            self.assertEqual(result.returncode, 0, result.stderr)
        current = json.loads(settings.read_text())
        self.assertEqual(current['permissions'], original['permissions'])
        self.assertEqual(len(current['hooks']['Stop']), 2)
        self.assertFalse((config / 'config.toml').exists())
        sub = self.root / 'docs'
        sub.mkdir()
        command = current['hooks']['PreToolUse'][0]['hooks'][0]['command']
        payload = dict(hook_event_name='PreToolUse', session_id='claude-project', cwd=str(sub))
        run = subprocess.run(command, shell=True, cwd=sub, input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), {})
        result = self.install('--host', 'claude', '--project', str(self.root), '--uninstall')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(settings.read_text()), original)

    def test_claude_user_config_directory(self):
        config = self.root / 'claude config'
        result = self.install('--host', 'claude', '--user', env=dict(os.environ, CLAUDE_CONFIG_DIR=str(config)))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((config / 'settings.json').read_text())
        self.assertIn('CLAUDE_CONFIG_DIR', data['hooks']['Stop'][0]['hooks'][0]['command'])
        self.assertTrue((config / 'vale/styles/Google/Latin.yml').is_file())


class CommandTests(unittest.TestCase):
    def test_install_update_remove_and_preserve_existing_command(self):
        script = INSTALLER.with_name('install_codex_command.py')
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CODEX_HOME=tmp)
            target = Path(tmp) / 'prompts/vale.md'
            def run(*args):
                return subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True)
            self.assertEqual(run().returncode, 0)
            self.assertIn('check-prose', target.read_text())
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run('--uninstall').returncode, 0)
            self.assertFalse(target.exists())
            target.write_text('User command')
            self.assertNotEqual(run().returncode, 0)
            self.assertNotEqual(run('--uninstall').returncode, 0)
            self.assertEqual(target.read_text(), 'User command')
