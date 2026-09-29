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
