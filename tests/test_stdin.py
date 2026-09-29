"""Draft CLI contracts exercised through real Vale and byte streams."""
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


@unittest.skipUnless(shutil.which('vale'), 'Integration tests require Vale')
class StdinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vale drafts ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def cli(self, data=b'', *args):
        result = subprocess.run([sys.executable, str(HOOK), '--stdin', '--format', 'json', *args],
                                input=data, cwd=self.root, capture_output=True, timeout=30)
        self.assertTrue(result.stdout.startswith(b'{'), result.stderr.decode(errors='replace'))
        return result.returncode, json.loads(result.stdout)

    def test_json_prose_is_not_hook_payload(self):
        code, result = self.cli(b'{"text": "Use this, e.g. for testing."}', '--ext', 'md')
        self.assertEqual(code, 1)
        self.assertEqual(result['schema_version'], 1)
        self.assertTrue(any(f['rule'] == 'Google.Latin' for f in result['findings']))
        self.assertEqual(result['submitted_files'], ['<stdin:draft.md>'])
        self.assertTrue(all(f['path'] == '<stdin:draft.md>' for f in result['findings']))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stdin_mode_conflicts(self):
        for args in [('--check', 'file.md'), ('--all',), ('--doctor',),
                     ('--scope', 'new-findings'), ('--base-ref', 'HEAD')]:
            with self.subTest(args=args):
                code, result = self.cli(b'', '--ext', 'md', *args)
                self.assertEqual(code, 2)
                self.assertEqual(result['status'], 'incomplete')
                self.assertTrue(result['errors'])

    def test_stdin_byte_limit(self):
        code, result = self.cli(b' ' * (1024 * 1024), '--ext', 'md')
        self.assertEqual(code, 0, result)
        for data in (b' ' * (1024 * 1024 + 1), ('é' * 524289).encode()):
            with self.subTest(size=len(data)):
                code, result = self.cli(data, '--ext', 'md')
                self.assertEqual(code, 2)
                self.assertEqual(result['status'], 'incomplete')
                self.assertEqual(result['submitted_files'], [])
                self.assertEqual(result['errors'][0]['code'], 'input_limit')

    def test_invalid_utf8_is_incomplete(self):
        code, result = self.cli(b'bad\xff', '--ext', 'md')
        self.assertEqual(code, 2)
        self.assertEqual(result['errors'][0]['code'], 'input_encoding')
        self.assertEqual(result['submitted_files'], [])

    def test_empty_stdin_has_zero_findings(self):
        code, result = self.cli(b'', '--ext', 'md')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['submitted_files'], ['<stdin:draft.md>'])
        self.assertTrue(result['coverage']['note'])

    def test_extension_and_logical_path_validation(self):
        invalid = [(), ('--ext', 'py'), ('--ext', 'md', '--path', '../draft.md'),
                   ('--ext', 'md', '--path', '/draft.md'), ('--ext', 'md', '--path', 'docs/a.txt'),
                   ('--ext', 'md', '--path', 'C:/draft.md'), ('--ext', 'md', '--path', 'docs\\draft.md')]
        for args in invalid:
            with self.subTest(args=args):
                code, result = self.cli(b'', *args)
                self.assertEqual(code, 2)
                self.assertEqual(result['status'], 'incomplete')
                self.assertEqual(result['submitted_files'], [])

    def test_inherited_comparison_scope_does_not_create_state(self):
        (self.root / '.vale-plugin.toml').write_text('scope = "new-findings"\n')
        before = list(self.root.iterdir())
        code, result = self.cli(b'Use this, e.g. for testing.', '--ext', 'md')
        self.assertEqual(code, 1)
        self.assertIsNone(result['comparison'])
        self.assertEqual(list(self.root.iterdir()), before)

    def file_check(self, name):
        result = subprocess.run([sys.executable, str(HOOK), '--check', name, '--format', 'json'],
                                cwd=self.root, capture_output=True, timeout=30)
        return result.returncode, json.loads(result.stdout)

    def project_config(self):
        styles = ROOT / 'plugins/vale/styles'
        (self.root / '.vale.ini').write_text(
            f'StylesPath = {styles}\nMinAlertLevel = warning\n[docs/*.md]\nBasedOnStyles = Google\n')

    def test_stdin_matches_file_findings(self):
        text = '# Draft\n\nCafé: use this, e.g. for testing.\n'
        (self.root / 'draft.md').write_text(text)
        original = (self.root / 'draft.md').read_bytes()
        code, draft = self.cli(text.encode(), '--ext', 'md', '--path', 'draft.md')
        file_code, saved = self.file_check('draft.md')
        self.assertEqual(code, file_code)
        signature = lambda result: [(f['rule'], f['line'], f['column'], f['end_column']) for f in result['findings']]
        self.assertEqual(signature(draft), signature(saved))
        self.assertTrue(any(f['rule'] == 'Google.Latin' and f['line'] == 3 for f in draft['findings']))
        self.assertEqual((self.root / 'draft.md').read_bytes(), original)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['draft.md'])

    def test_logical_path_selects_project_rules(self):
        self.project_config()
        text = b'Use this, e.g. for testing.\n'
        code, draft = self.cli(text, '--ext', 'md', '--path', 'docs/setup.md')
        self.assertEqual(code, 1, draft)
        self.assertEqual(draft['coverage']['source'], 'project')
        self.assertEqual(draft['config_path'], str(self.root / '.vale.ini'))
        self.assertEqual(draft['findings'][0]['path'], '<stdin:docs/setup.md>')
        code, unmatched = self.cli(text, '--ext', 'md', '--path', 'other/setup.md')
        self.assertEqual(code, 0, unmatched)
        self.assertEqual(unmatched['coverage']['verification'], 'unknown')
        self.assertEqual(unmatched['findings'], [])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['.vale.ini'])

    def test_shell_like_text_is_data(self):
        text = b'Use this, e.g. for testing.\n\n```sh\n$(touch injected)\n`touch backticks`\nprintf "$HOME"; touch semicolon\n```\n'
        code, result = self.cli(text, '--ext', 'md', '--path=-draft.md')
        self.assertEqual(code, 1)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(result['requested_files'], ['<stdin:-draft.md>'])

    def test_stdin_preserves_markdown_exclusions(self):
        text = b'Use this, e.g. for testing.\n\n```text\nUse this, e.g. for testing.\n```\n'
        code, result = self.cli(text, '--ext', 'md')
        self.assertEqual(code, 1)
        self.assertEqual([(f['rule'], f['line']) for f in result['findings']], [('Google.Latin', 1)])

    def test_policy_excluded_draft_matches_file_status(self):
        (self.root / '.vale-plugin.toml').write_text('exclude = ["docs/*.md"]\n')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/setup.md').write_text('Use this, e.g. for testing.')
        code, draft = self.cli(b'Use this, e.g. for testing.', '--ext', 'md', '--path', 'docs/setup.md')
        file_code, saved = self.file_check('docs/setup.md')
        self.assertEqual(code, file_code)
        self.assertEqual(draft['status'], saved['status'])
        self.assertEqual(draft['status'], 'skipped')
        self.assertEqual(draft['skipped_files'][0]['code'], 'excluded_path')
        self.assertEqual(draft['skipped_files'][0]['path'], '<stdin:docs/setup.md>')
        self.assertEqual(draft['submitted_files'], [])

    def test_supported_draft_formats_match_file_results(self):
        for ext in ('txt', 'rst', 'adoc', 'html'):
            with self.subTest(ext=ext):
                text = 'Use this, e.g. for testing.\n'
                if ext == 'html':
                    text = '<p>' + text.strip() + '</p>\n'
                name = 'draft.' + ext
                (self.root / name).write_text(text)
                file_code, saved = self.file_check(name)
                if saved['status'] == 'incomplete' and ext in ('rst', 'adoc') and not os.environ.get('VALE_REQUIRE_PARSERS'):
                    self.skipTest('Optional format parsers unavailable; CI requires them')
                code, draft = self.cli(text.encode(), '--ext', ext)
                self.assertEqual(code, 1, draft)
                self.assertEqual(code, file_code)
                self.assertEqual([(f['rule'], f['line'], f['column'], f['end_column']) for f in draft['findings']],
                                 [(f['rule'], f['line'], f['column'], f['end_column']) for f in saved['findings']])

    def test_oversized_stream_is_rejected_without_waiting_for_eof(self):
        proc = subprocess.Popen([sys.executable, str(HOOK), '--stdin', '--ext', 'md', '--format', 'json'],
                                cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.stdin.write(b' ' * (1024 * 1024 + 1))
            proc.stdin.flush()
            self.assertEqual(proc.wait(timeout=10), 2)
            self.assertEqual(json.loads(proc.stdout.read())['errors'][0]['code'], 'input_limit')
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()

    def test_shared_project_pattern_matches_draft_and_absolute_file(self):
        self.project_config()
        config = self.root / '.vale.ini'
        config.write_text(config.read_text().replace('[docs/*.md]', '[**/docs/*.md]'))
        (self.root / 'docs').mkdir()
        text = 'Use this, e.g. for testing.\n'
        (self.root / 'docs/setup.md').write_text(text)
        code, draft = self.cli(text.encode(), '--ext', 'md', '--path', 'docs/setup.md')
        file_code, saved = self.file_check('docs/setup.md')
        self.assertEqual(code, 1, draft)
        self.assertEqual(code, file_code)
        self.assertEqual(draft['status'], saved['status'])
        self.assertEqual([(f['rule'], f['line'], f['column'], f['end_column']) for f in draft['findings']],
                         [(f['rule'], f['line'], f['column'], f['end_column']) for f in saved['findings']])
