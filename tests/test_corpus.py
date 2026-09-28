"""Check selected rule locations against independently labeled synthetic prose."""
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/prose'
CATEGORIES = {'installation', 'troubleshooting', 'runbooks', 'api-reference', 'source-comments', 'correct-prose'}


class CorpusTests(unittest.TestCase):
    def cases(self):
        manifest = FIXTURES / 'manifest.json'
        self.assertTrue(manifest.is_file(), 'The labeled prose corpus is missing')
        return json.loads(manifest.read_text())

    def test_manifest_schema_and_paths(self):
        cases = self.cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({c['id'] for c in cases}), 12)
        self.assertEqual(Counter((c['category'], c['kind']) for c in cases),
                         Counter((category, kind) for category in CATEGORIES for kind in ('positive', 'negative')))
        for case in cases:
            with self.subTest(case=case['id']):
                path = FIXTURES / case['input']
                self.assertTrue(path.resolve().is_relative_to(FIXTURES.resolve()))
                self.assertFalse(path.is_symlink())
                self.assertIn(case['format'], ('md', 'py'))
                self.assertEqual(path.suffix, '.' + case['format'])
                content = path.read_text()
                self.assertTrue(case['protected_literals'])
                for literal in case['protected_literals']:
                    self.assertTrue(literal)
                    self.assertIn(literal, content)
                for item in case['expected_findings'] + case['forbidden_findings']:
                    self.assertRegex(item['rule'], r'^Google\.[A-Za-z]+$')
                    self.assertIs(type(item['line']), int)
                    self.assertGreaterEqual(item['line'], 1)
                    self.assertLessEqual(item['line'], len(content.splitlines()))
                self.assertTrue(case['expected_findings'] if case['kind'] == 'positive' else case['forbidden_findings'])

    def findings(self, case):
        if not shutil.which('vale'):
            if os.environ.get('CI') or os.environ.get('VALE_REQUIRE_PARSERS') == '1':
                self.fail('The required corpus suite needs Vale on PATH')
            self.skipTest('Corpus integration requires Vale on PATH')
        path = (FIXTURES / case['input']).resolve()
        run = subprocess.run(['vale', '--no-global', '--config', str(ROOT / 'plugins/vale/.vale.ini'),
                              '--minAlertLevel=suggestion', '--output=JSON', '--', str(path)],
                             capture_output=True, text=True, timeout=20)
        self.assertIn(run.returncode, (0, 1), run.stderr + run.stdout)
        self.assertFalse(run.stderr.strip(), run.stderr)
        data = json.loads(run.stdout)
        self.assertFalse(set(data) - {str(path)})
        return Counter((f['Check'], f['Line']) for f in data.get(str(path), []))

    def test_positive_and_negative_cases(self):
        for case in self.cases():
            with self.subTest(case=case['id']):
                actual = self.findings(case)
                expected = Counter((f['rule'], f['line']) for f in case['expected_findings'])
                selected = {f['rule'] for f in case['expected_findings'] + case['forbidden_findings']}
                self.assertEqual(Counter({k: v for k, v in actual.items() if k[0] in selected}), expected)
                for item in case['forbidden_findings']:
                    self.assertEqual(actual[(item['rule'], item['line'])], 0)

    def test_rule_multiplicity(self):
        case = next(c for c in self.cases() if c['id'] == 'api-reference-positive')
        actual = self.findings(case)
        self.assertEqual(actual[('Google.Latin', 1)], 2)
        self.assertEqual(actual[('Google.Latin', 3)], 0)
