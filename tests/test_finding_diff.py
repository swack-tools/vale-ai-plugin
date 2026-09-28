"""Conservative occurrence matching, independent of engine execution."""
import importlib
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts'
sys.path.insert(0, str(SCRIPTS))
from lint_result import Finding


def finding(line, rule='Google.Latin', column=1):
    return Finding('guide.md', line, column, column + 3, rule, 'error', 'Use for example.', 'e.g.')


class FindingDiffTests(unittest.TestCase):
    def classify(self, *args):
        self.assertTrue((SCRIPTS / 'finding_diff.py').is_file(), 'comparison implementation is missing')
        return importlib.import_module('finding_diff').classify_findings(*args)

    def test_shifted_old_occurrence(self):
        result = self.classify('e.g. here.\n', 'New paragraph.\n\ne.g. here.\n', [finding(1)], [finding(3)])
        self.assertEqual((result.new, result.existing, result.resolved), ([], [0], []))

    def test_added_duplicate_is_new(self):
        before = 'e.g. here.\n\nMiddle.\n\ne.g. here.\n'
        after = before + '\ne.g. here.\n'
        result = self.classify(before, after, [finding(1), finding(5)], [finding(1), finding(5), finding(7)])
        self.assertEqual((len(result.new), len(result.existing), result.resolved), (1, 2, []))

    def test_changed_paragraph_is_not_suppressed(self):
        result = self.classify('Context.\ne.g. here.\n', 'New context.\ne.g. here.\n', [finding(2)], [finding(2)])
        self.assertEqual(result.new, [0])

    def test_moved_paragraph_is_conservative(self):
        result = self.classify('e.g. here.\n\nOther paragraph.\n', 'Other paragraph.\n\ne.g. here.\n',
                               [finding(1)], [finding(3)])
        self.assertEqual(result.new, [0])

    def test_alignment_budget_falls_back(self):
        for before, after in [('x\n' * 1001, 'x\n' * 1001), ('x\n' * 5001, '')]:
            result = self.classify(before, after, [finding(1)], [finding(1)])
            self.assertTrue(result.uncertain)
            self.assertEqual(result.new, [0])

    def test_unknown_context_rule_is_not_suppressed(self):
        result = self.classify('e.g. here.\n', 'New definition.\n\ne.g. here.\n',
                               [finding(1, 'House.Definitions')], [finding(3, 'House.Definitions')])
        self.assertEqual(result.new, [0])

    def test_deleted_occurrence_is_resolved(self):
        result = self.classify('e.g. here.\n', '', [finding(1)], [])
        self.assertEqual((result.new, result.existing, result.resolved), ([], [], [0]))

    def test_unicode_prefix_and_repeated_columns(self):
        text = 'é e.g. and e.g.\n'
        result = self.classify(text, 'Intro.\n\n' + text,
                               [finding(1, column=3), finding(1, column=12)],
                               [finding(3, column=3), finding(3, column=12)])
        self.assertEqual((result.new, result.existing), ([], [0, 1]))
