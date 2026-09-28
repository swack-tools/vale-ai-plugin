"""Prove optional parsers produce actual findings and never fake a clean check."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts/prose_lint.py'


class FormatTests(unittest.TestCase):
    def check_format(self, ext, parser):
        if not shutil.which(parser):
            if os.environ.get('VALE_REQUIRE_PARSERS') == '1':
                self.fail(f'Required parser missing: {parser}')
            self.skipTest(f'Optional parser missing: {parser}')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / ('guide.' + ext)
            path.write_text('We will use this, e.g. for testing.\n')
            result = subprocess.run([sys.executable, str(HOOK), '--check', str(path)],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Google.Latin', result.stdout)

    def test_rst_parser_reports_google_rule(self):
        self.check_format('rst', 'rst2html')

    def test_adoc_parser_reports_google_rule(self):
        self.check_format('adoc', 'asciidoctor')

    def test_missing_parser_is_non_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            tools = root / 'bin'
            tools.mkdir()
            (tools / 'vale').symlink_to(shutil.which('vale'))
            for ext in ('rst', 'adoc'):
                path = root / ('guide.' + ext)
                path.write_text('Use this file.\n')
                result = subprocess.run([sys.executable, str(HOOK), '--check', str(path)],
                                        cwd=root, env=dict(os.environ, PATH=str(tools)),
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('not found', result.stdout + result.stderr)
