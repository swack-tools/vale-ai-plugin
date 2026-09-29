"""CI presentation preserves checker semantics without workflow-command injection."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def result(path='docs/test.md'):
    return dict(schema_version=1, status='findings', config_path='config.ini',
                requested_files=[path], submitted_files=[path], skipped_files=[], errors=[],
                coverage=dict(source='bundled', verification='configured_invocation', note='Configured.'),
                comparison=None, findings=[dict(path=path, line=1, column=1, end_column=3,
                rule='Google.Will', severity='warning', message='Use present tense.', match='will',
                link=None, suggestions=[], action=None)])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'scripts/ci_prose.py').is_file(), 'CI renderer has not been implemented')
        spec = importlib.util.spec_from_file_location('ci_prose', ROOT / 'scripts/ci_prose.py')
        self.ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ci)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.cwd)
        (self.root / 'docs').mkdir()
        (self.root / 'docs/test.md').write_text('We will do this.\n')

    def test_annotation_escapes_workflow_syntax(self):
        name = 'docs/::a%,b:\r\n.md'
        (self.root / name).write_text('We will do this.\n')
        data = result(name)
        data['findings'][0]['message'] = '::notice::first%\r\n::error::injected'
        annotation, = self.ci.render_annotations(data)
        self.assertEqual(annotation, '::warning file=docs/%3A%3Aa%25%2Cb%3A%0D%0A.md,line=1,col=1,endColumn=3,title=Google.Will::::notice::first%25%0D%0A::error::injected')
        self.assertEqual(len(annotation.splitlines()), 1)

    def test_virtual_path_is_not_file_annotation(self):
        for path in ('<stdin:md>', '../outside.md', 'missing.md', 'docs'):
            with self.subTest(path=path):
                annotation, = self.ci.render_annotations(result(path))
                self.assertNotIn('file=', annotation)
                self.assertNotIn('line=', annotation)

    def test_symlink_and_stale_line_have_no_location(self):
        (self.root / 'link.md').symlink_to(self.root / 'docs/test.md')
        self.assertNotIn('file=', self.ci.render_annotations(result('link.md'))[0])
        data = result()
        data['findings'][0]['line'] = 100
        self.assertNotIn('line=', self.ci.render_annotations(data)[0])

    def test_operational_error_fails_check(self):
        data = result()
        data.update(status='incomplete', findings=[], errors=[dict(code='engine_error', message='Missing Vale.\n::notice::bad', path=None)])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.ci.publish(data, self.root / 'result.json', self.root / 'summary.md')
        self.assertEqual(code, 2)
        self.assertIn('::error', output.getvalue())
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads((self.root / 'result.json').read_text()), data)

    def test_display_cap_keeps_full_summary(self):
        data = result()
        data['findings'] *= 63
        self.assertEqual(len(self.ci.render_annotations(data)), 50)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.ci.publish(data, self.root / 'report.json', self.root / 'summary.md'), 1)
        self.assertEqual(len(json.loads((self.root / 'report.json').read_text())['findings']), 63)
        summary = (self.root / 'summary.md').read_text()
        self.assertIn('63 findings', summary)
        self.assertIn('13 omitted', summary)

    def test_errors_have_priority_over_findings(self):
        data = result()
        data['findings'] *= 60
        data.update(status='incomplete', errors=[dict(code='engine_error', message='Broken.', path=None)])
        annotations = self.ci.render_annotations(data)
        self.assertEqual(len(annotations), 50)
        self.assertTrue(annotations[0].startswith('::error'))

    def test_invalid_schema_and_contradictory_status_are_rejected(self):
        for change in ({'schema_version': 2}, {'status': 'clean'}, {'findings': [None]}, {'errors': 'oops'}, {'comparison': {}}):
            data = result()
            data.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ci.render_annotations(data)
        for field, value in [('line', True), ('column', -1), ('severity', 'unknown')]:
            data = result()
            data['findings'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.ci.render_annotations(data)
