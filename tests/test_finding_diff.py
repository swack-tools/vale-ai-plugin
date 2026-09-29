"""Conservative occurrence matching, independent of engine execution."""
import importlib
import json
import shutil
import subprocess
import tempfile
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

    def test_missing_source_location_always_falls_back_to_actionable(self):
        missing = Finding('guide.md', None, None, None, 'Google.Latin', 'error', 'Use for example.', 'e.g.')
        result = self.classify('e.g. here.\n', 'e.g. here.\n', [missing], [missing])
        self.assertEqual(result.new, [0])
        self.assertEqual(result.existing, [])
        self.assertEqual(result.resolved, [])
        self.assertTrue(result.uncertain)
        self.assertIn('source location', result.reason.lower())

    def test_unicode_prefix_and_repeated_columns(self):
        text = 'é e.g. and e.g.\n'
        result = self.classify(text, 'Intro.\n\n' + text,
                               [finding(1, column=3), finding(1, column=12)],
                               [finding(3, column=3), finding(3, column=12)])
        self.assertEqual((result.new, result.existing), ([], [0, 1]))


@unittest.skipUnless(shutil.which('vale'), 'Integration tests require Vale')
class ValeUnicodeCoordinateTests(unittest.TestCase):
    def test_markdown_and_source_comment_spans_use_preprocessed_offsets(self):
        with tempfile.TemporaryDirectory(prefix='vale unicode coordinates ') as temp:
            root = Path(temp).resolve()
            markdown = root / 'unicode.md'
            comments = root / 'unicode.py'
            markdown_lines = ['**e.g. and e.g.**', '**é e.g. and e.g.**', '**e\u0301 e.g. and e.g.**',
                             '**😀 e.g. and e.g.**', '**😀😀 e.g. and e.g.**']
            prefixes = ['', 'é ', 'e\u0301 ', '😀 ', '😀😀 ']
            comment_lines = ['# ' + prefix + 'e.g.' for prefix in prefixes]
            markdown.write_text('\n'.join(markdown_lines) + '\n', encoding='utf-8')
            comments.write_text('\n'.join(comment_lines) + '\n', encoding='utf-8')
            config = Path(__file__).resolve().parents[1] / 'plugins/vale/.vale.ini'
            result = subprocess.run(['vale', '--no-global', f'--config={config}', '--output=JSON', str(markdown), str(comments)],
                                    cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, result.stderr)
            raw = json.loads(result.stdout)
            hook = Path(__file__).resolve().parents[1] / 'plugins/vale/scripts/prose_lint.py'
            wrapped = subprocess.run([sys.executable, str(hook), '--format', 'json', '--check',
                                      str(markdown), str(comments)], cwd=root,
                                     capture_output=True, text=True, check=False)
            self.assertEqual(wrapped.returncode, 1, wrapped.stderr + wrapped.stdout)
            normalized = json.loads(wrapped.stdout)
            self.assertEqual(normalized['status'], 'findings')
            self.assertEqual([(item['path'], item['line'], item['column'], item['end_column'])
                              for item in normalized['findings']],
                             [(str(path), alert['Line'], *alert['Span'])
                              for path in (markdown, comments) for alert in raw[str(path)]])
            decoded = {}
            for name, lines in ((str(markdown), markdown_lines), (str(comments), comment_lines)):
                decoded[name] = []
                expected = []
                for line_number, line in enumerate(lines, 1):
                    start = 0
                    while (offset := line.find('e.g.', start)) >= 0:
                        expected.append((line_number, [offset + 1, offset + len('e.g.')]))
                        start = offset + len('e.g.')
                self.assertEqual([(alert['Line'], alert['Span']) for alert in raw[name]], expected)
                for alert in raw[name]:
                    line = lines[alert['Line'] - 1]
                    start, end = alert['Span']
                    self.assertEqual(line[start - 1:end], alert['Match'])
                    decoder = importlib.import_module('vale_runner').decode_alert
                    decoded[name].append(decoder(alert, name))
            diff = importlib.import_module('finding_diff')
            for name, lines in ((str(markdown), markdown_lines), (str(comments), comment_lines)):
                text = '\n'.join(lines) + '\n'
                unchanged = diff.classify_findings(text, text, decoded[name], decoded[name])
                self.assertEqual((unchanged.new, unchanged.existing, unchanged.resolved),
                                 ([], list(range(len(decoded[name]))), []))
                duplicate_line = '# e.g.' if name.endswith('.py') else 'e.g.'
                duplicate_text = text + '\n' + duplicate_line + '\n'
                path = Path(name)
                path.write_text(duplicate_text, encoding='utf-8')
                duplicate_run = subprocess.run(
                    ['vale', '--no-global', f'--config={config}', '--output=JSON', str(path)], cwd=root,
                    capture_output=True, text=True, check=False)
                self.assertEqual(duplicate_run.returncode, 1, duplicate_run.stderr)
                decoder = importlib.import_module('vale_runner').decode_alert
                duplicate_findings = [decoder(alert, name) for alert in json.loads(duplicate_run.stdout)[name]]
                added = diff.classify_findings(text, duplicate_text, decoded[name], duplicate_findings)
                self.assertEqual(len(added.new), 1)
                self.assertEqual(len(added.existing), len(decoded[name]))

                shifted_lines = list(lines)
                shifted_lines[3] = shifted_lines[3].replace('😀', 'é 😀', 1)
                shifted_text = '\n'.join(shifted_lines) + '\n'
                path.write_text(shifted_text, encoding='utf-8')
                shifted_run = subprocess.run(
                    ['vale', '--no-global', f'--config={config}', '--output=JSON', str(path)], cwd=root,
                    capture_output=True, text=True, check=False)
                self.assertEqual(shifted_run.returncode, 1, shifted_run.stderr)
                shifted_findings = [decoder(alert, name) for alert in json.loads(shifted_run.stdout)[name]]
                shifted = diff.classify_findings(text, shifted_text, decoded[name], shifted_findings)
                changed_line = next(i for i, finding in enumerate(shifted_findings) if finding.line == 4)
                self.assertIn(changed_line, shifted.new)
