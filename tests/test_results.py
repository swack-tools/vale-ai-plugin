"""Exercise the public JSON boundary with real files and controlled engine failures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'plugins/vale/scripts/prose_lint.py'
ALERT = {'Check': 'House.Example', 'Line': 1, 'Span': [1, 2], 'Severity': 'warning',
         'Message': 'Use another word.', 'Match': 'We', 'Link': 'https://example.org/rule',
         'Suggestions': ['Use'], 'Action': {'Name': '', 'Params': None}}


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.file = self.root / 'guide.md'
        self.file.write_text('We will use this file.\n')
        self.env = os.environ.copy()

    def fake_vale(self, code):
        bindir = self.root / 'bin'
        bindir.mkdir(exist_ok=True)
        executable = bindir / 'vale'
        executable.write_text('#!' + sys.executable + '\nimport sys, json\n' + code + '\n')
        executable.chmod(0o755)
        self.env['PATH'] = str(bindir) + os.pathsep + os.environ['PATH']

    def check(self, *files):
        result = subprocess.run([sys.executable, str(HOOK), '--format', 'json', '--check',
                                 *(files or (self.file.name,))],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertTrue(result.stdout.startswith('{'), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def event(self, name, **kw):
        payload = dict(hook_event_name=name, session_id='report-session', cwd=str(self.root),
                       tool_name='Write', tool_input={'file_path': str(self.file)})
        payload.update(kw)
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_warning_json_is_findings_even_on_exit_zero(self):
        code, result = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'findings')
        self.assertTrue(result['findings'])
        self.assertEqual(result['schema_version'], 1)
        self.assertIn('end_column', result['findings'][0])

    def test_config_error_is_incomplete(self):
        (self.root / '.vale.ini').write_text('StylesPath = absent\n[*.md]\nBasedOnStyles = Missing\n')
        code, result = self.check()
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(result['errors'])
        post = self.event('PostToolUse')['hookSpecificOutput']['additionalContext']
        self.assertIn('could not complete', post)
        self.assertNotIn('Fix the', post)

    def test_invalid_json_is_incomplete(self):
        self.fake_vale("print('not JSON')")
        code, result = self.check()
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'incomplete')

    def test_empty_json_does_not_prove_coverage(self):
        (self.root / '.vale.ini').write_text('[*.txt]\nBasedOnStyles = Vale\nVale.Spelling = NO\n')
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result['coverage']['verification'], 'unknown')
        self.assertNotIn('checked_files', result)

    def test_partial_batch_retains_findings(self):
        files = []
        for i in range(51):
            path = self.root / f'f{i:02}.md'
            path.write_text('Use this file.\n')
            files.append(path.name)
        self.fake_vale(f"if any(x.endswith('f50.md') for x in sys.argv):\n print('E201 bad config', file=sys.stderr); sys.exit(2)\nprint(json.dumps({{sys.argv[-1]: [{ALERT!r}]}}))")
        code, result = self.check(*files)
        self.assertEqual(code, 2)
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(len(result['submitted_files']), 50)
        self.assertTrue(result['errors'])

    def test_invalid_operand_does_not_discard_valid_findings(self):
        code, result = self.check(self.file.name, 'missing.md')
        self.assertEqual(code, 2)
        self.assertTrue(result['findings'])
        self.assertTrue(result['errors'])

    def test_large_feedback_is_complete_and_bounded(self):
        alerts = [dict(ALERT, Line=i+1, Message='Message ' + 'long ' * 100) for i in range(100)]
        self.fake_vale(f'print(json.dumps({{sys.argv[-1]: {alerts!r}}}))')
        post = self.event('PostToolUse')['hookSpecificOutput']['additionalContext']
        self.assertLessEqual(len(post), 16000)
        self.assertIn('omitted', post)
        reports = list((self.root / '.git/vale-state').glob('*.report.json'))
        self.assertEqual(len(reports), 1)
        saved = json.loads(reports[0].read_text())
        self.assertEqual(len(saved['findings']), 100)
        self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)
        active = self.event('Stop', stop_hook_active=True)
        self.assertNotIn('decision', active)
        self.assertLessEqual(len(active['systemMessage']), 16000)
        self.assertIn('unresolved', active['systemMessage'])

    def test_oversized_single_finding_is_omitted_whole(self):
        alert = dict(ALERT, Message='START-' + 'x' * 17000 + '-END')
        self.fake_vale(f'print(json.dumps({{sys.argv[-1]: [{alert!r}]}}))')
        post = self.event('PostToolUse')['hookSpecificOutput']['additionalContext']
        self.assertNotIn('START-', post)
        self.assertIn('1 omitted', post)

    def test_report_write_failure_is_visible(self):
        import hashlib
        state = self.root / '.git/vale-state'
        state.mkdir()
        target = state / (hashlib.sha256(b'report-session').hexdigest() + '.report.json')
        target.symlink_to(self.file)
        original = self.file.read_text()
        alert = dict(ALERT, Message='x' * 17000)
        self.fake_vale(f'print(json.dumps({{sys.argv[-1]: [{alert!r}]}}))')
        post = self.event('PostToolUse')['hookSpecificOutput']['additionalContext']
        self.assertIn('report', post.lower())
        self.assertIn('could not complete', post)
        self.assertEqual(self.file.read_text(), original)

    def test_custom_rules_have_neutral_prefix(self):
        self.fake_vale(f'print(json.dumps({{sys.argv[-1]: [{ALERT!r}]}}))')
        post = self.event('PostToolUse')['hookSpecificOutput']['additionalContext']
        self.assertIn('House.Example', post)
        self.assertNotIn('Google documentation', post)
