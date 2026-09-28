"""Project selection exercised through the public CLI and actual Vale."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/vale/scripts'
HOOK = SCRIPTS / 'prose_lint.py'
sys.path.insert(0, str(SCRIPTS))


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('guide.md')

    def write(self, name, content='Use this, e.g. for testing.\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def policy(self, text):
        self.write('.vale-plugin.toml', text)

    def cli(self, *args):
        run = subprocess.run([sys.executable, str(HOOK), '--format', 'json', *args],
                             cwd=self.root, capture_output=True, text=True)
        self.assertTrue(run.stdout.startswith('{'), run.stderr)
        return run.returncode, json.loads(run.stdout)

    def test_default_policy_preserves_behavior(self):
        code, result = self.cli('--check', 'guide.md')
        self.assertEqual(code, 1)
        self.assertEqual(result['submitted_files'], ['guide.md'])
        code, report = self.cli('--doctor')
        self.assertIn('policy', report)
        self.assertEqual(report['policy']['scope'], 'changed-files')
        self.assertEqual(report['policy']['origins']['scope'], 'default')

    def test_cli_replaces_project_list(self):
        self.write('other.md')
        self.policy('include = ["guide.md"]\nexclude = ["other.md"]\n')
        code, result = self.cli('--all', '--include', 'other.md', '--exclude', 'absent.md')
        self.assertEqual(result['submitted_files'], ['other.md'])
        _, report = self.cli('--doctor', '--include', 'other.md')
        self.assertEqual(report['policy']['origins']['include'], 'cli')
        self.assertEqual(report['policy']['origins']['exclude'], 'project')

    def test_unknown_key_is_error(self):
        self.policy('exlcude = ["guide.md"]\n')
        code, result = self.cli('--check', 'guide.md')
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('exlcude', str(result['errors']))

    def test_explicit_profile_conflicts_with_project_config(self):
        self.write('.vale.ini', '[*.md]\nBasedOnStyles = Vale\n')
        self.policy('profile = "google"\n')
        code, result = self.cli('--check', 'guide.md')
        self.assertEqual(code, 2)
        self.assertIn('auto', str(result['errors']))

    def test_soft_exclusion_can_be_included(self):
        self.write('build/guide.md')
        self.policy('include = ["build/*.md"]\n')
        _, result = self.cli('--all')
        self.assertEqual(result['submitted_files'], ['build/guide.md'])

    def test_hard_exclusion_cannot_be_included(self):
        for name in ('.codex/guide.md', '.claude/guide.md', '.agents/guide.md', '.git/guide.md'):
            self.write(name)
        self.policy('include = ["*"]\n')
        _, result = self.cli('--all')
        self.assertEqual(result['submitted_files'], ['guide.md'])
        _, result = self.cli('--check', '.claude/guide.md')
        self.assertEqual(result['status'], 'skipped')

    def test_validation_rejects_unsafe_or_mistyped_policy(self):
        for text in ('schema_version = true', 'schema_version = 2', 'scope = "future"',
                     'include = "*.md"', 'include = [1]', 'include = ["../*.md"]',
                     'include = ["/tmp/*"]', 'include = ["C:/docs/*"]',
                     'include = ["docs/../*.md"]', 'include = ["docs\\\\*.md"]',
                     'profile = "ste-inspired"'):
            with self.subTest(text=text):
                self.policy(text)
                code, result = self.cli('--doctor')
                self.assertEqual(code, 2)
                self.assertEqual(result['overall_status'], 'incomplete')

    def test_exclude_applies_last_and_star_crosses_slashes(self):
        self.write('docs/deep/guide.md')
        self.policy('include = ["docs/*.md"]\nexclude = ["docs/deep/*"]\n')
        _, result = self.cli('--check', 'docs/deep/guide.md', 'guide.md')
        self.assertEqual(result['status'], 'skipped')
        self.policy('include = ["docs/*.md"]\n')
        _, result = self.cli('--all')
        self.assertEqual(result['submitted_files'], ['docs/deep/guide.md'])

    def test_automatic_scan_respects_gitignore_with_include(self):
        self.write('.gitignore', 'build/\n')
        self.write('build/guide.md')
        self.policy('include = ["build/*"]\n')
        _, result = self.cli('--all')
        self.assertEqual(result['submitted_files'], [])
        _, result = self.cli('--check', 'build/guide.md')
        self.assertEqual(result['submitted_files'], ['build/guide.md'])

    def test_symlink_and_outside_root_cannot_be_included(self):
        (self.root / 'alias.md').symlink_to(self.root / 'guide.md')
        self.policy('include = ["*"]\n')
        _, result = self.cli('--check', 'alias.md', '../outside.md')
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['submitted_files'], [])

    def test_extra_extension_needs_explicit_format(self):
        self.write('guide.prose', 'Use this, e.g. for testing.\n\n```\ne.g.\n```\n')
        self.policy('include = ["*.prose"]\n')
        _, result = self.cli('--check', 'guide.prose')
        self.assertEqual(result['status'], 'incomplete')
        self.write('.vale.ini', f'StylesPath = {ROOT / "plugins/vale/styles"}\nMinAlertLevel = warning\n[formats]\nprose = md\n[*.prose]\nBasedOnStyles = Google\n')
        _, result = self.cli('--check', 'guide.prose')
        self.assertEqual(result['submitted_files'], ['guide.prose'])
        self.assertEqual([f['line'] for f in result['findings']], [1])

    def test_toml_scope_applies_to_hooks_and_manual_requires_reference(self):
        self.policy('scope = "new-findings"\n')
        payload = dict(hook_event_name='PreToolUse', session_id='policy', cwd=str(self.root))
        run = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), cwd=self.root, capture_output=True, text=True)
        self.assertEqual(json.loads(run.stdout), {})
        self.assertTrue(list((self.root / '.git/vale-state').glob('*.baseline')))
        code, result = self.cli('--check', 'guide.md')
        self.assertEqual(code, 2)
        self.assertIn('base-ref', str(result['errors']))
        _, result = self.cli('--all')
        self.assertIsNone(result['comparison'])
        _, result = self.cli('--check', 'guide.md', '--scope', 'changed-files')
        self.assertEqual(result['status'], 'findings')

    def test_loader_api_returns_deterministic_provenance(self):
        self.assertTrue((SCRIPTS / 'policy.py').exists(), 'wrapper policy loader is missing')
        self.policy('include = ["docs/*.md"]\n')
        loaded = importlib.import_module('policy').load_policy(self.root, {'include': []})
        self.assertEqual(loaded.include, ())
        self.assertEqual(loaded.origins['include'], 'cli')

    def test_non_git_include_can_select_generated_files(self):
        import shutil
        shutil.rmtree(self.root / '.git')
        self.write('build/guide.md')
        self.policy('include = ["build/*"]\n')
        _, result = self.cli('--all')
        self.assertEqual(result['submitted_files'], ['build/guide.md'])

    def test_policy_symlink_and_oversize_are_incomplete(self):
        (self.root / '.vale-plugin.toml').symlink_to(self.write('settings.toml', ''))
        code, result = self.cli('--doctor')
        self.assertEqual(code, 2)
        (self.root / '.vale-plugin.toml').unlink()
        self.policy('#' * 65537)
        code, result = self.cli('--doctor')
        self.assertEqual(code, 2)

    def test_configured_extra_format_appears_in_doctor(self):
        self.policy('include = ["*.prose"]\n')
        self.write('.vale.ini', '[formats]\nprose = rst\n[*.prose]\nBasedOnStyles = Vale\n')
        _, result = self.cli('--doctor')
        self.assertIn('prose', result['formats'])
        self.assertEqual(result['formats']['prose']['parser'], 'rst2html')

    def test_structured_data_alias_does_not_enable_all_tokens(self):
        self.policy('include = ["*.yaml"]\n')
        self.write('api.yaml')
        self.write('.vale.ini', '[formats]\nyaml = txt\n[*.yaml]\nBasedOnStyles = Vale\n')
        _, result = self.cli('--check', 'api.yaml')
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['submitted_files'], [])

    def test_wrapper_change_invalidates_session_comparison(self):
        self.policy('scope = "new-findings"\n')
        payload = dict(hook_event_name='PreToolUse', session_id='fingerprint', cwd=str(self.root))
        subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), cwd=self.root, capture_output=True, text=True, check=True)
        self.policy('scope = "new-findings"\nexclude = ["unrelated.md"]\n')
        self.write('guide.md', 'Use this, e.g. for testing.\n\nUse this, e.g. for another test.\n')
        payload['hook_event_name'] = 'Stop'
        run = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), cwd=self.root, capture_output=True, text=True, check=True)
        self.assertIn('fallback', run.stdout.lower())
        self.assertIn('2 new', run.stdout)

    def test_removed_wrapper_policy_invalidates_git_comparison(self):
        self.policy('include = ["guide.md"]\n')
        for args in [('add', '.'), ('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'base')]:
            subprocess.run(['git', *args], cwd=self.root, check=True)
        (self.root / '.vale-plugin.toml').unlink()
        _, result = self.cli('--check', 'guide.md', '--scope', 'new-findings', '--base-ref', 'HEAD')
        self.assertIn('Wrapper policy', result['comparison']['fallback_reason'])
        self.assertEqual(result['comparison']['existing'], 0)
