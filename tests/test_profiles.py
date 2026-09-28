"""Named profiles exercised through actual Vale and installed entrypoints."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'plugins/vale/scripts/prose_lint.py'


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vale profile ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'guide.md').write_text('We will use this, e.g. for testing.\n\n`We will retry, e.g. later.`\n')

    def cli(self, *args, script=HOOK):
        run = subprocess.run([sys.executable, str(script), '--format', 'json', *args],
                             cwd=self.root, capture_output=True, text=True)
        self.assertTrue(run.stdout.startswith('{'), run.stderr)
        return run.returncode, json.loads(run.stdout)

    def test_default_google_unchanged(self):
        code, result = self.cli('--check', 'guide.md')
        explicit_code, explicit = self.cli('--profile', 'google', '--check', 'guide.md')
        self.assertEqual(code, 1)
        self.assertEqual(explicit_code, code)
        self.assertEqual(result, explicit)
        self.assertEqual({f['rule'] for f in result['findings']}, {'Google.We', 'Google.Will', 'Google.Latin'})
        self.assertEqual({f['line'] for f in result['findings']}, {1})

    def test_named_profile_finds_same_mechanical_rules(self):
        code, google = self.cli('--check', 'guide.md')
        selected_code, selected = self.cli('--profile', 'ste-inspired', '--check', 'guide.md')
        self.assertEqual(selected_code, code)
        self.assertEqual(selected['findings'], google['findings'])
        self.assertEqual(selected['coverage']['source'], 'bundled')
        self.assertTrue(selected['config_path'].endswith('/profiles/ste-inspired.ini'))
        (self.root / 'clean.MD').write_text('Use this file.\n\n```sh\nWe will retry, e.g. later.\n```\n')
        self.assertEqual(self.cli('--profile', 'ste-inspired', '--check', 'clean.MD')[0], 0)

    def test_project_config_conflict_is_actionable(self):
        (self.root / '.vale.ini').write_text('[*.md]\nBasedOnStyles = Vale\nVale.Spelling = NO\n')
        code, result = self.cli('--profile', 'ste-inspired', '--check', 'guide.md')
        self.assertEqual(code, 2)
        self.assertIn('conflicts', str(result['errors']))
        self.assertIn('auto', str(result['errors']))
        self.assertEqual(self.cli('--profile', 'auto', '--check', 'guide.md')[0], 0)

    def test_project_profile_and_doctor_use_selected_config(self):
        (self.root / '.vale-plugin.toml').write_text('profile = "ste-inspired"\n')
        code, result = self.cli('--check', 'guide.md')
        self.assertEqual(code, 1)
        doctor_code, doctor = self.cli('--doctor')
        self.assertEqual(doctor_code, 0)
        self.assertEqual(doctor['config']['config_path'], result['config_path'])
        self.assertEqual(doctor['coverage']['source'], 'bundled')
        self.assertEqual(doctor['policy']['origins']['profile'], 'project')
        _, override = self.cli('--profile', 'google', '--doctor')
        self.assertTrue(override['config']['config_path'].endswith('/vale/.vale.ini'))
        self.assertEqual(override['policy']['origins']['profile'], 'cli')

    def test_profile_works_from_installed_path_with_spaces(self):
        for host in ('codex', 'claude'):
            for location in ('project', 'user'):
                with self.subTest(host=host, location=location):
                    home = self.root / ('home ' + host)
                    home.mkdir(exist_ok=True)
                    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(home / '.codex'), CLAUDE_CONFIG_DIR=str(home / '.claude'))
                    args = ['--project', str(self.root)] if location == 'project' else ['--user']
                    run = subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--host', host, *args], env=env, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    config = (self.root if location == 'project' else home) / ('.' + host)
                    script = config / 'vale/scripts/prose_lint.py'
                    code, result = self.cli('--profile', 'ste-inspired', '--check', 'guide.md', script=script)
                    self.assertEqual(code, 1)
                    self.assertEqual({f['rule'] for f in result['findings']}, {'Google.We', 'Google.Will', 'Google.Latin'})
                    self.assertEqual(Path(result['config_path']), config / 'vale/profiles/ste-inspired.ini')

    def test_profile_comparison_checks_current_and_baseline_with_same_config(self):
        subprocess.run(['git', '-C', str(self.root), 'add', 'guide.md'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'baseline'], check=True)
        code, result = self.cli('--profile', 'ste-inspired', '--scope', 'new-findings', '--base-ref', 'HEAD', '--check', 'guide.md')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['comparison']['existing'], 3)
        self.assertFalse(result['comparison']['fallback_reason'])

    def test_incomplete_check_retains_selected_profile(self):
        (self.root / '.vale-plugin.toml').write_text('scope = "new-findings"\n')
        code, result = self.cli('--profile', 'ste-inspired', '--check', 'guide.md')
        self.assertEqual(code, 2)
        self.assertIn('base-ref', str(result['errors']))
        self.assertTrue(result['config_path'].endswith('/profiles/ste-inspired.ini'))
