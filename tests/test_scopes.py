"""Real-engine scope checks, plus bounded baseline storage regressions."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/vale/scripts'
sys.path.insert(0, str(SCRIPTS))
HOOK = SCRIPTS / 'prose_lint.py'
OLD = 'Use this, e.g. for testing.\n'
NEW = OLD + '\nUse another example, e.g. a second file.\n'


@unittest.skipUnless(shutil.which('vale'), 'Integration tests require Vale')
class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vale scopes ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.file = self.root / 'guide.md'
        self.file.write_text(OLD)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'baseline')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0', '-C', str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(HOOK), *args], cwd=self.root, capture_output=True, text=True)

    def event(self, event, *, scope='new-findings', **extra):
        payload = dict(hook_event_name=event, session_id='scope-session', cwd=str(self.root),
                       tool_name='Edit', tool_input={'file_path': str(self.file)})
        payload.update(extra)
        result = subprocess.run([sys.executable, str(HOOK), '--scope', scope], input=json.dumps(payload),
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def compare(self, *args):
        result = self.cli('--check', str(self.file.relative_to(self.root)), '--scope', 'new-findings', '--base-ref', 'HEAD', '--format', 'json', *args)
        self.assertIn(result.returncode, (0, 1), result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_manual_duplicate_keeps_raw_and_actionable_findings(self):
        self.file.write_text(NEW)
        result = self.compare()
        self.assertEqual(len(result['findings']), 2)
        self.assertEqual(result['comparison']['new'], 1)
        self.assertEqual(result['comparison']['existing'], 1)
        self.assertEqual(result['comparison']['actionable_indexes'], [1])
        self.assertEqual(self.file.read_text(), NEW)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('rev-parse', 'refs/heads/' + self.git('branch', '--show-current')))

    def test_first_pre_freezes_baseline(self):
        self.assertEqual(self.event('PreToolUse'), {})
        self.file.write_text(NEW)
        self.assertEqual(self.event('PreToolUse'), {})
        output = str(self.event('PostToolUse'))
        self.assertIn('1 new', output)
        self.assertIn('1 existing', output)

    def test_edit_before_first_post_uses_original_bytes(self):
        self.event('PreToolUse')
        self.file.write_text(NEW)
        self.assertIn('1 new', str(self.event('PostToolUse')))

    def test_restart_uses_same_baseline(self):
        self.event('PreToolUse')
        self.file.write_text(NEW)
        self.event('PostToolUse')
        self.assertIn('1 new', str(self.event('Stop')))

    def test_stop_still_reports_unfixed_new_violation(self):
        self.event('PreToolUse')
        self.file.write_text(NEW)
        self.event('PostToolUse')
        self.assertEqual(self.event('Stop')['decision'], 'block')
        guarded = self.event('Stop', stop_hook_active=True)
        self.assertNotIn('decision', guarded)
        self.assertIn('1 new', guarded['systemMessage'])

    def test_new_file_reports_all_findings(self):
        self.event('PreToolUse')
        self.file = self.root / 'new.md'
        self.file.write_text(OLD)
        self.assertIn('1 new', str(self.event('PostToolUse')))

    def test_policy_change_disables_suppression(self):
        self.event('PreToolUse')
        (self.root / '.vale.ini').write_text((ROOT / 'plugins/vale/.vale.ini').read_text().replace('StylesPath = styles', 'StylesPath = ' + str(ROOT / 'plugins/vale/styles')))
        self.file.write_text(NEW)
        output = str(self.event('PostToolUse'))
        self.assertIn('fallback', output.lower())
        self.assertIn('Google.Latin', output)

    def test_default_does_not_capture_source(self):
        self.event('PreToolUse', scope='changed-files')
        self.assertFalse(list((self.root / '.git/vale-state').glob('*.baseline')))

    def test_missing_baseline_falls_back(self):
        self.assertIn('fallback', str(self.event('PostToolUse')).lower())

    def test_all_ignores_session_baseline(self):
        self.event('PreToolUse')
        self.file.write_text(NEW)
        result = self.cli('--all', '--format', 'json')
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report['findings']), 2)
        self.assertIsNone(report['comparison'])

    def test_base_ref_is_not_an_option(self):
        result = self.cli('--check', self.file.name, '--scope', 'new-findings', '--base-ref=--help', '--format', 'json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('base_ref', result.stdout)

    def test_invalid_mode_combinations(self):
        for args in [('--all', '--scope', 'new-findings'), ('--check', 'guide.md', '--scope', 'new-findings'),
                     ('--check', 'guide.md', '--base-ref', 'HEAD')]:
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 2)

    def test_non_git_hook_baseline(self):
        directory = tempfile.TemporaryDirectory(prefix='vale nongit ')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.file = self.root / 'guide.md'
        self.file.write_text(OLD)
        self.event('PreToolUse')
        self.file.write_text(NEW)
        self.assertIn('1 new', str(self.event('Stop')))
        self.assertEqual(self.cli('--check', 'guide.md', '--scope', 'new-findings', '--base-ref', 'HEAD').returncode, 2)

    def test_baseline_cap_falls_back(self):
        self.assertTrue((SCRIPTS / 'baseline.py').exists(), 'baseline implementation is required')
        baseline = importlib.import_module('baseline')
        hook = importlib.import_module('prose_lint')
        payload = dict(hook_event_name='PreToolUse', session_id='cap', cwd=str(self.root))
        with patch.object(baseline, 'MAX_TOTAL_BYTES', 1):
            hook.run_hook(payload, scope='new-findings')
        self.file.write_text(NEW)
        payload['hook_event_name'] = 'Stop'
        self.assertIn('fallback', str(hook.run_hook(payload, scope='new-findings')).lower())

    def test_check_document_uses_logical_format_and_preserves_path(self):
        runner = importlib.import_module('vale_runner')
        self.assertTrue(hasattr(runner, 'check_document'))
        result = runner.check_document(self.root, OLD + '\n```text\n' + OLD + '```\n', 'GUIDE.MD')
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].path, str(self.root / 'GUIDE.MD'))
        self.assertEqual(result.findings[0].line, 1)

    def test_project_relative_glob_matches_saved_files_and_drafts(self):
        runner = importlib.import_module('vale_runner')
        (self.root / '.vale.ini').write_text(
            f'StylesPath = {ROOT / "plugins/vale/styles"}\n'
            'MinAlertLevel = suggestion\n'
            '[docs/*.md]\nBasedOnStyles = Google\n'
            '[*.md]\nBasedOnStyles = Google\n'
        )
        documents = {
            'docs/setup.md': self.root / 'docs' / 'setup.md',
            'docs/a file.md': self.root / 'docs' / 'a file.md',
            'docs/-draft.md': self.root / 'docs' / '-draft.md',
            '-draft.md': self.root / '-draft.md',
        }
        for path in documents.values():
            path.parent.mkdir(exist_ok=True)
            path.write_text(OLD)

        saved = runner.run_check(self.root, list(documents))
        self.assertEqual({f.path for f in saved.findings if f.rule == 'Google.Latin'},
                         {str(path) for path in documents.values()})
        absolute_cli = self.cli('--check', str(documents['docs/a file.md']), '--format', 'json')
        self.assertEqual(absolute_cli.returncode, 1, absolute_cli.stdout + absolute_cli.stderr)
        self.assertEqual(json.loads(absolute_cli.stdout)['submitted_files'], ['docs/a file.md'])
        for name, path in documents.items():
            draft = runner.check_document(self.root, OLD, name, relative_identity=True)
            self.assertTrue(any(f.rule == 'Google.Latin' for f in draft.findings), name)
            self.assertTrue(all(f.path == str(path) for f in draft.findings), name)

    def test_project_relative_glob_maps_baseline_and_falls_back_conservatively(self):
        runner = importlib.import_module('vale_runner')
        finding_diff = importlib.import_module('finding_diff')
        self.file = self.root / 'docs' / 'setup.md'
        self.file.parent.mkdir()
        self.file.write_text(OLD)
        (self.root / '.vale.ini').write_text(
            f'StylesPath = {ROOT / "plugins/vale/styles"}\n'
            'MinAlertLevel = suggestion\n'
            '[docs/*.md]\nBasedOnStyles = Google\n'
        )
        before = runner.check_document(self.root, OLD, 'docs/setup.md')
        self.assertEqual(len(before.findings), 1)
        self.assertEqual(before.findings[0].path, str(self.file))
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'project policy')
        self.file.write_text(NEW)
        current = runner.run_check(self.root, ['docs/setup.md'])
        classified = finding_diff.classify_findings(
            OLD, NEW, before.findings, current.findings
        )

        self.assertEqual(len(classified.existing), 1)
        self.assertEqual(len(classified.new), 1)
        self.assertTrue(all(item.path == str(self.file) for item in current.findings))
        report = self.compare()
        self.assertIn('project policy', report['comparison']['fallback_reason'])
        self.assertEqual(report['comparison']['new'], len(report['findings']))

    def test_unchanged_old_finding_is_clean_in_comparison(self):
        result = self.compare()
        self.assertEqual(result['status'], 'clean')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['comparison']['actionable_indexes'], [])

    def test_manual_new_file_uses_empty_baseline(self):
        self.file = self.root / ':new.md'
        self.file.write_text(OLD)
        result = self.compare()
        self.assertEqual(result['comparison']['new'], 1)
        self.assertIsNone(result['comparison']['fallback_reason'])

    def test_deleted_old_finding_counts_unmatched_baseline(self):
        self.file.write_text('Use an example.\n')
        result = self.compare()
        self.assertEqual(result['comparison']['resolved'], 1)
        self.assertEqual(result['comparison']['new'], 0)

    def test_policy_removed_since_git_base_falls_back(self):
        (self.root / '.vale.ini').write_text('[*.md]\nBasedOnStyles = Vale\n')
        self.git('add', '.vale.ini')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'policy')
        (self.root / '.vale.ini').unlink()
        result = self.compare()
        self.assertIn('project policy', result['comparison']['fallback_reason'])
        self.assertEqual(result['comparison']['new'], 1)

    def test_tampered_baseline_falls_back(self):
        self.event('PreToolUse')
        baseline = importlib.import_module('baseline')
        directory = next((self.root / '.git/vale-state').glob('*.baseline'))
        saved = directory / baseline.digest(os.fsencode(self.file.name))
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        saved.write_text('Unexpected replacement.\n')
        self.file.write_text(NEW)
        self.assertIn('Stored baseline bytes changed', str(self.event('Stop')))

    def test_symlink_baseline_falls_back_without_reading_target(self):
        self.event('PreToolUse')
        baseline = importlib.import_module('baseline')
        directory = next((self.root / '.git/vale-state').glob('*.baseline'))
        saved = directory / baseline.digest(os.fsencode(self.file.name))
        saved.unlink()
        saved.symlink_to(self.file)
        self.file.write_text(NEW)
        self.assertIn('Symbolic links', str(self.event('Stop')))

    def test_style_and_vocabulary_changes_invalidate_policy(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        package = self.root / 'package'
        shutil.copytree(ROOT / 'plugins/vale', package)
        payload = dict(hook_event_name='PreToolUse', session_id='policy', cwd=str(self.root))
        with patch.object(runner, 'PACKAGE', package):
            hook.run_hook(payload, scope='new-findings')
            vocabulary = package / 'styles/config/vocabularies/Test/accept.txt'
            vocabulary.parent.mkdir(parents=True, exist_ok=True)
            vocabulary.write_text('Codex\n')
            self.file.write_text(NEW)
            payload['hook_event_name'] = 'Stop'
            output = str(hook.run_hook(payload, scope='new-findings'))
            self.assertIn('Bundled styles or vocabulary changed', output)
            self.assertIn('2 new', output)
            rule = package / 'styles/Google/Latin.yml'
            rule.write_text(rule.read_text() + '\n# changed\n')
            self.assertIn('local rule changed', str(hook.run_hook(payload, scope='new-findings')))

    def test_manual_scope_does_not_create_session_state(self):
        self.compare()
        self.assertFalse((self.root / '.git/vale-state').exists())

    def test_baseline_lint_failure_keeps_current_findings(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        self.file.write_text(NEW)
        failed = runner.empty_result(self.root, ['guide.md'])
        failed.errors.append(runner.Issue('test_failure', 'Before lint failed.'))
        with patch.object(runner, 'check_document', return_value=failed.finish()):
            result = hook.scoped_check(self.root, ['guide.md'], deadline=Deadline(50), scope='new-findings', revision='HEAD')
        self.assertEqual(len(result.actionable_findings), 2)
        self.assertIn('Baseline lint did not complete', result.comparison['fallback_reason'])

    def test_current_document_comparison_uses_the_linted_bytes(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        original = runner.check_document
        self.file.write_text(NEW)
        def edit_after_current_check(*args, **kwargs):
            self.file.write_text(OLD)
            return original(*args, **kwargs)
        with patch.object(runner, 'check_document', side_effect=edit_after_current_check):
            result = hook.scoped_check(self.root, ['guide.md'], deadline=Deadline(50), scope='new-findings', revision='HEAD')
        self.assertEqual(result.comparison['new'], 1)
        self.assertEqual(result.comparison['existing'], 1)

    def test_installed_scope_commands_work_for_both_hosts_and_locations(self):
        nested = self.root / 'nested'
        nested.mkdir()
        for host in ('codex', 'claude'):
            config = self.root / ('.codex' if host == 'codex' else '.claude')
            env = dict(os.environ, CODEX_HOME=str(config), CLAUDE_CONFIG_DIR=str(config))
            for location in ('project', 'user'):
                with self.subTest(host=host, location=location):
                    args = ['--project', str(self.root)] if location == 'project' else ['--user']
                    install = subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--host', host,
                                              *args, '--feedback-scope', 'new-findings'], env=env, capture_output=True, text=True)
                    self.assertEqual(install.returncode, 0, install.stderr)
                    settings = config / ('hooks.json' if host == 'codex' else 'settings.json')
                    hooks = json.loads(settings.read_text())['hooks']
                    self.file.write_text(OLD)
                    for event in ('PreToolUse', 'PostToolUse', 'Stop'):
                        payload = dict(hook_event_name=event, session_id=host + location, cwd=str(self.root),
                                       tool_name='Edit', tool_input={'file_path': str(self.file)})
                        command = hooks[event][0]['hooks'][0]['command']
                        response = subprocess.run(['/bin/sh', '-c', command], env=env, cwd=nested,
                                                  input=json.dumps(payload), capture_output=True, text=True)
                        self.assertEqual(response.returncode, 0, response.stderr)
                        if event == 'PreToolUse':
                            self.file.write_text(NEW)
                        else:
                            self.assertIn('1 new', response.stdout)
                            self.assertIn('1 existing', response.stdout)

    def test_current_text_retention_is_bounded(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        self.assertTrue(hasattr(runner, 'MAX_DOCUMENT_BYTES'), 'Current comparison text needs a total bound')
        from deadline import Deadline
        self.file.write_text(NEW)
        with patch.object(runner, 'MAX_DOCUMENT_BYTES', 1):
            result = hook.scoped_check(self.root, ['guide.md'], deadline=Deadline(50), scope='new-findings', revision='HEAD')
        self.assertEqual(len(result.actionable_findings), 2)
        self.assertIn('Current comparison text', result.comparison['fallback_reason'])

    def test_untracked_rule_cannot_hide_a_new_policy_finding(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        package = self.root / 'package'
        shutil.copytree(ROOT / 'plugins/vale', package)
        self.file.write_text('Use a test file.\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'package')
        (package / 'styles/Google/NewRule.yml').write_text("extends: existence\nmessage: 'New policy finding.'\nlevel: warning\ntokens: ['Use']\n")
        with patch.object(runner, 'PACKAGE', package):
            result = hook.scoped_check(self.root, ['guide.md'], deadline=Deadline(50), scope='new-findings', revision='HEAD')
        self.assertEqual(result.status, 'findings')
        self.assertEqual(result.findings[0].rule, 'Google.NewRule')
        self.assertEqual(result.comparison['new'], 1)
        self.assertTrue(result.comparison['fallback_reason'])

    def test_ignored_installed_policy_has_no_historical_identity(self):
        hook = importlib.import_module('prose_lint')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        package = self.root / '.codex/vale'
        shutil.copytree(ROOT / 'plugins/vale', package)
        (self.root / '.gitignore').write_text('.codex/\n')
        with patch.object(runner, 'PACKAGE', package):
            result = hook.scoped_check(self.root, ['guide.md'], deadline=Deadline(50), scope='new-findings', revision='HEAD')
        self.assertEqual(result.status, 'findings')
        self.assertTrue(result.comparison['fallback_reason'])

    @unittest.skipIf(os.geteuid() == 0, 'Root bypasses directory permission checks')
    def test_unreadable_style_directory_rejects_policy_identity(self):
        baseline = importlib.import_module('baseline')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        package = self.root / 'package'
        shutil.copytree(ROOT / 'plugins/vale', package)
        styles = package / 'styles'
        styles.chmod(0o111)
        try:
            with patch.object(runner, 'PACKAGE', package), self.assertRaises((OSError, ValueError)):
                baseline.policy_identity(self.root, Deadline(50))
        finally:
            styles.chmod(0o755)

    def test_unverified_added_style_cannot_become_a_session_policy(self):
        baseline = importlib.import_module('baseline')
        runner = importlib.import_module('vale_runner')
        from deadline import Deadline
        package = self.root / 'package'
        shutil.copytree(ROOT / 'plugins/vale', package)
        (package / 'styles/Google/Extra.yml').write_text("extends: script\nmessage: 'External dependency.'\nscript: file.txt\n")
        with patch.object(runner, 'PACKAGE', package), self.assertRaises(ValueError):
            baseline.policy_identity(self.root, Deadline(50))

    def test_custom_format_fallback_preserves_full_file_behavior(self):
        self.file = self.root / 'guide.MD'
        self.file.write_text(OLD + '\n```text\n' + OLD + '```\n')
        (self.root / '.vale.ini').write_text('StylesPath = ' + str(ROOT / 'plugins/vale/styles') +
                                            '\nMinAlertLevel = warning\n[formats]\nMD = txt\n[*.MD]\nBasedOnStyles = Google\n')
        full = json.loads(self.cli('--check', self.file.name, '--format', 'json').stdout)
        compared = self.compare()
        self.assertEqual(compared['findings'], full['findings'])
        self.assertTrue(compared['comparison']['fallback_reason'])

    def test_custom_document_adapter_uses_project_format_mapping(self):
        runner = importlib.import_module('vale_runner')
        (self.root / '.vale.ini').write_text('StylesPath = ' + str(ROOT / 'plugins/vale/styles') +
                                            '\nMinAlertLevel = warning\n[formats]\nMD = txt\n[*.MD]\nBasedOnStyles = Google\n')
        result = runner.check_document(self.root, OLD + '\n```text\n' + OLD + '```\n', 'guide.MD')
        self.assertEqual(len(result.findings), 2)
