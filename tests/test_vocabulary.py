"""Execute the documented Vale-native vocabulary recipe with the real engine."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'plugins/vale/scripts/prose_lint.py'


@unittest.skipUnless(shutil.which('vale'), 'Integration tests require Vale')
class VocabularyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        shutil.copytree(ROOT / 'plugins/vale/styles', self.root / '.vale/styles')
        self.vocab = self.root / '.vale/styles/config/vocabularies/Project'
        self.vocab.mkdir(parents=True)
        (self.vocab / 'accept.txt').write_text('OxiDex\n')
        (self.vocab / 'reject.txt').write_text('Oxidexx\n')
        self.config = self.root / '.vale.ini'
        self.config.write_text('StylesPath = .vale/styles\nMinAlertLevel = suggestion\nVocab = Project\n'
                               '[*.md]\nBasedOnStyles = Vale, Google\nVale.Spelling = YES\n')

    def check(self, text, *args):
        (self.root / 'guide.md').write_text(text)
        run = subprocess.run([sys.executable, str(HOOK), '--check', 'guide.md', '--format', 'json', *args],
                             cwd=self.root, capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertIn(run.returncode, (0, 1), run.stderr + run.stdout)
        return result

    def test_accept_term_preserves_other_rules(self):
        (self.vocab / 'accept.txt').write_text('')
        before = self.check('Use Oxidex.\n')
        self.assertNotIn('Vale.Terms', [f['rule'] for f in before['findings']])
        (self.vocab / 'accept.txt').write_text('OxiDex\n')
        after = self.check('Use OxiDex, e.g. for testing.\n')
        self.assertEqual([f['rule'] for f in after['findings']], ['Google.Latin'])

    def test_reject_term_reports_expected_rule(self):
        result = self.check('Use Oxidexx.\n')
        rejected = [f for f in result['findings'] if f['rule'] == 'Vale.Avoid']
        self.assertEqual([f['match'] for f in rejected], ['Oxidexx'])
        self.assertEqual(rejected[0]['severity'], 'error')
        casing = self.check('Use Oxidex.\n')
        self.assertIn('Vale.Terms', [f['rule'] for f in casing['findings']])

    def test_spelling_disabled_does_not_claim_spellcheck(self):
        self.config.unlink()
        bundled = self.check('Use qzxxyyzz.\n')
        self.assertEqual(bundled['findings'], [])
        self.config.write_text('StylesPath = .vale/styles\nVocab = Project\n[*.md]\nBasedOnStyles = Vale, Google\nVale.Spelling = NO\n')
        project = self.check('Use qzxxyyzz and Oxidexx.\n')
        self.assertNotIn('Vale.Spelling', [f['rule'] for f in project['findings']])
        self.assertIn('Vale.Avoid', [f['rule'] for f in project['findings']])

    def test_project_vocabulary_changes_never_suppress_findings(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.check('Use Oxidexx.\n')
        for args in [('add', '.'), ('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'base')]:
            subprocess.run(['git', *args], cwd=self.root, check=True)
        (self.vocab / 'reject.txt').write_text('Oxidexx\nOtherTerm\n')
        result = self.check('Use Oxidexx.\n', '--scope', 'new-findings', '--base-ref', 'HEAD')
        self.assertTrue(result['comparison']['fallback_reason'])
        self.assertEqual(result['comparison']['existing'], 0)
        self.assertEqual(len(result['comparison']['actionable_indexes']), len(result['findings']))
