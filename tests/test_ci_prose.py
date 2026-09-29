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
        self.assertEqual(len(self.ci.render_annotations(data)), 10)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.ci.publish(data, self.root / 'report.json', self.root / 'summary.md'), 1)
        self.assertEqual(len(json.loads((self.root / 'report.json').read_text())['findings']), 63)
        summary = (self.root / 'summary.md').read_text()
        self.assertIn('63 findings', summary)
        self.assertIn('53 omitted', summary)

    def test_errors_have_priority_over_findings(self):
        data = result()
        data['findings'] *= 60
        data.update(status='incomplete', errors=[dict(code='engine_error', message='Broken.', path=None)])
        annotations = self.ci.render_annotations(data)
        self.assertEqual(len(annotations), 11)
        self.assertTrue(annotations[0].startswith('::error'))

    def test_per_level_limits_share_error_budget_with_operational_errors(self):
        data = result()
        template = data['findings'][0]
        data['findings'] = []
        for severity in ('error', 'warning', 'suggestion'):
            for i in range(15):
                finding = copy.deepcopy(template)
                finding['severity'] = severity
                data['findings'].append(finding)
        data.update(status='incomplete', errors=[dict(code='engine_error', message='Broken.', path=None)] * 5)
        annotations = self.ci.render_annotations(data)
        self.assertEqual(len(annotations), 30)
        for level in ('error', 'warning', 'notice'):
            self.assertEqual(sum(a.startswith('::' + level + ' ') for a in annotations), 10)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.ci.publish(data, self.root / 'report.json', self.root / 'summary.md'), 2)
        summary = (self.root / 'summary.md').read_text()
        self.assertIn('45 findings: 25 shown, 20 omitted', summary)
        self.assertIn('5 errors: 5 shown, 0 omitted', summary)

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


class SelectionTests(unittest.TestCase):
    def setUp(self):
        RenderTests.setUp(self)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        import subprocess
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'change')
        return self.git('rev-parse', 'HEAD').strip()

    def select(self):
        self.assertTrue(hasattr(self.ci, 'changed_documents'), 'Changed document selection is not implemented')
        return self.ci.changed_documents(self.root, self.base, self.git('rev-parse', 'HEAD').strip())

    def cli(self, head=None, base=None, event=None):
        import subprocess
        return subprocess.run([os.sys.executable, str(ROOT / 'scripts/ci_prose.py'),
            '--base=' + (base or self.base), '--head=' + (head or self.git('rev-parse', 'HEAD').strip()),
            *(['--event', event] if event else []), '--output', str(self.root / 'report.json'), '--summary', str(self.root / 'summary.md')],
            cwd=self.root, text=True, capture_output=True)

    def test_renamed_doc_is_checked_at_destination(self):
        self.git('mv', 'docs/test.md', 'docs/renamed.md')
        self.commit()
        self.assertEqual(self.select(), ['docs/renamed.md'])

    def test_deleted_doc_is_skipped(self):
        (self.root / 'docs/test.md').unlink()
        self.commit()
        self.assertEqual(self.select(), [])
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('No applicable changed documentation files', (self.root / 'summary.md').read_text())
        self.assertEqual(json.loads((self.root / 'report.json').read_text())['status'], 'no-applicable-files')

    def test_space_and_newline_filename(self):
        for name in ('docs/a b.md', 'docs/a\nb.md'):
            (self.root / name).write_text('Use the file.\n')
        self.commit()
        self.assertEqual(self.select(), ['docs/a\nb.md', 'docs/a b.md'])
        self.assertEqual(self.cli().returncode, 0)

    def test_existing_prose_in_changed_file_is_reported(self):
        (self.root / 'docs/test.md').write_text('We will do this.\n\nUse the file.\n')
        self.commit()
        proc = self.cli()
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        data = json.loads((self.root / 'report.json').read_text())
        self.assertTrue(any(f['line'] == 1 and f['rule'] == 'Google.Will' for f in data['findings']))
        self.assertIn('file=docs/test.md,line=1', proc.stdout)
        self.assertIn('title=Google.Will', proc.stdout)
        self.assertIsNone(data['comparison'])

    def test_fixture_directory_is_not_selected(self):
        (self.root / 'tests').mkdir()
        (self.root / 'tests/bad.md').write_text('We will do this.\n')
        self.commit()
        self.assertEqual(self.select(), [])

    def test_initial_push_selects_roots(self):
        self.base = '0' * 40
        self.assertEqual(self.select(), ['docs/test.md'])

    def test_invalid_or_stale_commit_fails_without_commands(self):
        for sha in ('--help', 'HEAD', 'f' * 40):
            proc = self.cli(base=sha)
            self.assertEqual(proc.returncode, 2)
            self.assertIn('::error', proc.stdout)
        (self.root / 'docs/test.md').write_text('Use the file.\n')
        old = self.base
        self.commit()
        self.assertEqual(self.cli(head=old).returncode, 2)
        (self.root / 'docs/test.md').write_text('Modified.\n')
        self.assertEqual(self.cli().returncode, 2)

    def test_project_policy_is_reused_but_comparison_is_not(self):
        (self.root / '.vale.ini').write_text('StylesPath = styles\nMinAlertLevel = suggestion\n[*.md]\nBasedOnStyles = Local\n')
        (self.root / 'styles/Local').mkdir(parents=True)
        (self.root / 'styles/Local/Term.yml').write_text("extends: existence\nmessage: Avoid foobar.\nlevel: warning\ntokens:\n  - foobar\n")
        (self.root / '.vale-plugin.toml').write_text('scope = "new-findings"\n')
        (self.root / 'docs/test.md').write_text('Use foobar.\n')
        self.commit()
        proc = self.cli()
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        data = json.loads((self.root / 'report.json').read_text())
        self.assertEqual([f['rule'] for f in data['findings']], ['Local.Term'])
        self.assertEqual(data['coverage']['source'], 'project')
        self.assertIsNone(data['comparison'])

    def test_asset_only_change_is_not_a_prose_failure(self):
        (self.root / 'docs/assets').mkdir()
        (self.root / 'docs/assets/favicon.svg').write_text('<svg/>')
        self.commit()
        self.assertEqual(self.select(), [])
        proc = self.cli()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads((self.root / 'report.json').read_text())['status'], 'no-applicable-files')

    def test_initial_push_ignores_assets_and_project_exclusions(self):
        (self.root / 'docs/icon.svg').write_text('<svg/>')
        (self.root / 'docs/ignored.md').write_text('We will do this.')
        (self.root / '.vale-plugin.toml').write_text('exclude = ["docs/ignored.md"]\n')
        self.commit()
        self.base = '0' * 40
        self.assertEqual(self.select(), ['docs/test.md'])
        self.assertEqual(self.cli().returncode, 1)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(report['status'], 'findings')
        self.assertEqual(report['errors'], [])

    def test_selected_symlink_still_fails(self):
        (self.root / 'docs/link.md').symlink_to('test.md')
        self.commit()
        self.assertEqual(self.select(), ['docs/link.md'])
        proc = self.cli()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(json.loads((self.root / 'report.json').read_text())['errors'][0]['code'], 'unsupported_path')

    def test_pr_ignores_target_only_changes_but_push_compares_trees(self):
        (self.root / 'code.py').write_text('x = 1\n')
        topic = self.commit()
        self.git('checkout', '-q', '--detach', self.base)
        (self.root / 'docs/test.md').write_text('Read the file.\n')
        target = self.commit()
        self.git('checkout', '-q', '--detach', topic)
        pr = self.cli(base=target, event='pull_request')
        self.assertEqual(pr.returncode, 0, pr.stdout + pr.stderr)
        self.assertEqual(json.loads((self.root / 'report.json').read_text())['status'], 'no-applicable-files')
        push = self.cli(base=target, event='push')
        self.assertEqual(push.returncode, 1, push.stdout + push.stderr)
        self.assertIn('title=Google.Will', push.stdout)
