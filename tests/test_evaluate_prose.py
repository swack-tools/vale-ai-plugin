"""Exercise trial validation through files and CLI exit codes, without a model."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/evaluate_prose.py'
CHECKS = ('meaning', 'quantities', 'negation', 'modality', 'prerequisites', 'order',
          'quoted_code', 'rule_references', 'unnecessary_changes')


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'The offline trial validator is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'results'
        run = subprocess.run([sys.executable, str(SCRIPT), '--prepare', str(self.root)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.trials = json.loads((self.root / 'trials.json').read_text())
        self.cases = json.loads((ROOT / 'evals/cases.json').read_text())
        for i, trial in enumerate(self.trials):
            trial.update(host='codex', client_version='test-client', model='test-model',
                         timestamp='2026-09-28T12:00:00Z', session_id=f'session-{i}', home=f'home-{i}',
                         workspace=f'workspace-{i}', settings={'reasoning_effort': 'medium'},
                         reviewer={'kind': 'agent', 'id': 'synthetic-validator-test'},
                         semantic_verdict='pass', notes='Synthetic evidence for validator regression tests only.',
                         review_checks=dict.fromkeys(CHECKS, 'pass'))
            trial['preflight'].update(fresh_session=True, isolated_home=True, isolated_workspace=True)
            case = next(c for c in self.cases if c['case_id'] == trial['case_id'])
            (self.root / trial['output_file']).write_text((ROOT / case['input_file']).read_text())
            trial['reviewed_output_sha256'] = hashlib.sha256((self.root / trial['output_file']).read_bytes()).hexdigest()
        self.save()

    def save(self):
        (self.root / 'trials.json').write_text(json.dumps(self.trials))

    def run_validator(self, *args):
        self.save()
        run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(self.root), '--format', 'json', *args],
                             capture_output=True, text=True, timeout=20)
        self.assertFalse(run.stderr, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(run.returncode, report['exit_code'])
        return run.returncode, report

    def test_complete_reviewed_pairs_pass(self):
        code, report = self.run_validator()
        self.assertEqual(code, 0, report)
        self.assertEqual(len(report['pairs']), 6)
        self.assertEqual(report['lint']['status'], 'not_run')
        self.assertTrue(all(t['literal_status'] == 'pass' for t in report['trials']))
        self.assertTrue(all(t['reviewer']['kind'] == 'agent' for t in report['trials']))

    def test_missing_pair_is_incomplete(self):
        self.trials.pop()
        code, report = self.run_validator()
        self.assertEqual(code, 2)
        self.assertTrue(any('missing' in e.lower() for e in report['errors']))

    def test_literal_change_is_failure(self):
        trial = self.trials[0]
        file = self.root / trial['output_file']
        file.write_text(file.read_text().replace('tool install --version 2.0', 'tool install --version 3.0'))
        trial['reviewed_output_sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
        code, report = self.run_validator()
        self.assertEqual(code, 1, report)
        self.assertEqual(report['trials'][0]['literal_mismatches'],
                         [{'literal': 'tool install --version 2.0', 'expected': 1, 'actual': 0}])

    def test_unreviewed_is_not_pass(self):
        self.trials[0].update(semantic_verdict='unreviewed', reviewer=None,
                              review_checks=dict.fromkeys(CHECKS, 'unreviewed'))
        self.assertEqual(self.run_validator()[0], 2)

    def test_mismatched_model_is_not_paired(self):
        self.trials[1]['model'] = 'different-model'
        self.assertEqual(self.run_validator()[0], 2)

    def test_changed_prompt_or_skill_snapshot_is_incomplete(self):
        for field in ('prompt_file', 'skill_file'):
            with self.subTest(field=field):
                trial = next(t for t in self.trials if t['arm'] == 'skill')
                path = self.root / trial[field]
                original = path.read_bytes()
                path.write_bytes(original + b' changed')
                self.assertEqual(self.run_validator()[0], 2)
                path.write_bytes(original)

    def test_forged_hash_cannot_substitute_different_prompt(self):
        for t in self.trials[:2]:
            path = self.root / t['prompt_file']
            path.write_text('Different task')
            t['prompt_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.run_validator()[0], 2)

    def test_duplicate_arm_and_unknown_case_are_incomplete(self):
        self.trials[1]['arm'] = 'baseline'
        self.assertEqual(self.run_validator()[0], 2)
        self.trials[1]['case_id'] = 'invented-case'
        self.assertEqual(self.run_validator()[0], 2)

    def test_empty_output_cannot_pass(self):
        (self.root / self.trials[0]['output_file']).write_text(' \n')
        self.assertEqual(self.run_validator()[0], 2)

    def test_outside_or_symlink_output_is_rejected(self):
        trial = self.trials[0]
        original = trial['output_file']
        trial['output_file'] = '../outside.md'
        self.assertEqual(self.run_validator()[0], 2)
        trial['output_file'] = original
        path = self.root / original
        path.unlink()
        path.symlink_to(ROOT / 'README.md')
        self.assertEqual(self.run_validator()[0], 2)

    def test_reused_session_and_mismatched_settings_are_incomplete(self):
        self.trials[1]['session_id'] = self.trials[0]['session_id']
        self.assertEqual(self.run_validator()[0], 2)
        self.trials[1]['session_id'] = 'unique'
        self.trials[1]['settings'] = {'reasoning_effort': 'high'}
        self.assertEqual(self.run_validator()[0], 2)

    def test_contaminated_baseline_is_incomplete(self):
        self.trials[0]['preflight']['target_skill'] = True
        self.assertEqual(self.run_validator()[0], 2)

    def test_semantic_failure_is_separate_from_literals(self):
        self.trials[0]['semantic_verdict'] = 'fail'
        self.trials[0]['review_checks']['negation'] = 'fail'
        code, report = self.run_validator()
        self.assertEqual(code, 1, report)
        self.assertEqual(report['trials'][0]['literal_status'], 'pass')
        self.assertEqual(report['trials'][0]['semantic_verdict'], 'fail')

    def test_inconsistent_semantic_review_is_incomplete(self):
        self.trials[0]['review_checks']['modality'] = 'fail'
        self.assertEqual(self.run_validator()[0], 2)

    def test_missing_dimension_cannot_be_reviewed_pass(self):
        del self.trials[0]['review_checks']['prerequisites']
        self.assertEqual(self.run_validator()[0], 2)

    def test_preparation_never_overwrites_existing_results(self):
        original = (self.root / 'trials.json').read_bytes()
        run = subprocess.run([sys.executable, str(SCRIPT), '--prepare', str(self.root)], capture_output=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual((self.root / 'trials.json').read_bytes(), original)

    def test_invalid_timestamp_and_reviewer_are_incomplete(self):
        self.trials[0]['timestamp'] = 'yesterday'
        self.assertEqual(self.run_validator()[0], 2)
        self.trials[0]['timestamp'] = '2026-09-28T12:00:00Z'
        self.trials[0]['reviewer'] = {'kind': 'human', 'id': ''}
        self.assertEqual(self.run_validator()[0], 2)

    def test_prepared_unrun_template_is_incomplete(self):
        other = self.root.parent / 'unrun'
        subprocess.run([sys.executable, str(SCRIPT), '--prepare', str(other)], check=True, capture_output=True)
        run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(other), '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)['status'], 'incomplete')

    def test_edit_after_review_requires_new_review(self):
        path = self.root / self.trials[0]['output_file']
        path.write_text(path.read_text() + '\nThe previous prerequisite is optional.\n')
        self.assertEqual(self.run_validator()[0], 2)

    def test_unknown_field_and_boolean_verdict_are_rejected(self):
        self.trials[0]['sematic_verdict'] = 'pass'
        self.assertEqual(self.run_validator()[0], 2)
        del self.trials[0]['sematic_verdict']
        self.trials[0]['review_checks']['meaning'] = True
        self.assertEqual(self.run_validator()[0], 2)

    def test_extra_protected_command_is_failure(self):
        trial = self.trials[0]
        path = self.root / trial['output_file']
        path.write_text(path.read_text() + '\nRun `tool install --version 2.0` again.\n')
        trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.run_validator()[0], 1)

    def test_malformed_and_oversized_evidence_is_incomplete(self):
        (self.root / 'trials.json').write_text('{"bad": true, "bad": false}')
        run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(self.root), '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('Duplicate JSON key', json.loads(run.stdout)['errors'][0])
        (self.root / self.trials[0]['output_file']).write_bytes(b'x' * (1024 * 1024 + 1))
        self.assertEqual(self.run_validator()[0], 2)

    def test_one_pilot_cannot_mix_models_across_pairs(self):
        self.trials[0]['model'] = self.trials[1]['model'] = 'another-model'
        self.assertEqual(self.run_validator()[0], 2)

    def test_pair_settings_preserve_json_types(self):
        for trial in self.trials:
            trial['settings'] = {'reasoning_effort': 'medium', 'sampling': False}
        self.trials[1]['settings']['sampling'] = 0
        self.assertEqual(self.run_validator()[0], 2)

    def test_command_prefixes_and_appended_arguments_do_not_preserve_literals(self):
        changes = [
            ('installation', 'tool install --version 2.0', 'tool install --version 2.0.1'),
            ('installation', 'tool install --version 2.0', 'tool install --version 2.0 --force'),
            ('installation', "printf 'We will retry, e.g. later.'", "printf 'We will retry, e.g. later.' --bad"),
            ('runbooks', 'restart --grace 30', 'restart --grace 300'),
            ('api-reference', 'GET /v1/items?limit=10', 'GET /v1/items?limit=100'),
            ('source-comments', 'None', 'NoneType'),
            ('runbooks', 'must', "mustn't"),
        ]
        for case, old, new in changes:
            with self.subTest(case=case, replacement=new):
                trial = next(t for t in self.trials if t['case_id'] == case and t['arm'] == 'skill')
                path = self.root / trial['output_file']
                original = path.read_bytes()
                path.write_text(original.decode().replace(old, new))
                trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(self.run_validator()[0], 1)
                path.write_bytes(original)
                trial['reviewed_output_sha256'] = hashlib.sha256(original).hexdigest()

    def test_option_outside_code_span_changes_the_command(self):
        trial = next(t for t in self.trials if t['case_id'] == 'installation' and t['arm'] == 'skill')
        path = self.root / trial['output_file']
        original = path.read_bytes()
        for suffix in (' --force', ' -f', '--force', ' `--force`'):
            with self.subTest(suffix=suffix):
                path.write_text(original.decode().replace('`tool install --version 2.0`', '`tool install --version 2.0`' + suffix))
                trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(self.run_validator()[0], 1)
        path.write_bytes(original)

    def test_deep_json_returns_incomplete_report(self):
        (self.root / 'trials.json').write_text('{"x":' * 100000 + '0' + '}' * 100000)
        run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(self.root), '--format', 'json'],
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertFalse(run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'incomplete')

    def test_review_metadata_cannot_contain_unvalidated_nested_fields(self):
        self.trials[0]['reviewer']['extra'] = {'unvalidated': 'data'}
        self.assertEqual(self.run_validator()[0], 2)

    def test_formatted_option_continuations_change_the_command(self):
        trial = next(t for t in self.trials if t['case_id'] == 'installation' and t['arm'] == 'skill')
        path = self.root / trial['output_file']
        original = path.read_bytes()
        for suffix in (' **--force**', ' [--force](https://example.com)', ' __--force__',
                       ' *--force*', ' ~~--force~~', ' <b>--force</b>',
                       ' &#45;&#45;force', r' \-\-force', ' with **--force**', ' -<b>-</b>force', ' --[force](https://example.com)'):
            with self.subTest(suffix=suffix):
                path.write_text(original.decode().replace('`tool install --version 2.0`', '`tool install --version 2.0`' + suffix))
                trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(self.run_validator()[0], 1)
        path.write_bytes(original)

    def test_output_symlink_loop_returns_incomplete_report(self):
        path = self.root / self.trials[0]['output_file']
        path.unlink()
        path.symlink_to(path.name)
        self.assertEqual(self.run_validator()[0], 2)

    def test_results_root_symlink_loop_returns_incomplete_report(self):
        loop = self.root.parent / 'loop'
        loop.symlink_to('loop')
        run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(loop), '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertFalse(run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'incomplete')

    def test_shell_and_positional_continuations_change_the_command(self):
        trial = self.trials[0]
        path = self.root / trial['output_file']
        original = path.read_bytes()
        for suffix in (' | tee /tmp/install.log', ' > /tmp/log', ' && reboot',
                       ' package-name', ' /tmp/package', ' ; reboot', ' $(reboot)',
                       ' **package-name**', ' &amp;&amp; reboot'):
            with self.subTest(suffix=suffix):
                path.write_text(original.decode().replace('`tool install --version 2.0`', '`tool install --version 2.0`' + suffix))
                trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(self.run_validator()[0], 1)

    def test_protected_code_allows_prose_edits_before_it(self):
        trial = self.trials[0]
        path = self.root / trial['output_file']
        path.write_text(path.read_text().replace('We install the package with', 'Install the package with'))
        trial['reviewed_output_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.run_validator()[0], 0)

    def test_overflowed_json_numbers_are_incomplete(self):
        original = (self.root / 'trials.json').read_text()
        for number in ('1e400', '-1e400', '1e500'):
            with self.subTest(number=number):
                (self.root / 'trials.json').write_text(original.replace('"reasoning_effort": "medium"', '"temperature": ' + number))
                run = subprocess.run([sys.executable, str(SCRIPT), '--results', str(self.root), '--format', 'json'], capture_output=True, text=True)
                self.assertEqual(run.returncode, 2, run.stderr)
                self.assertFalse(run.stderr)
                self.assertEqual(json.loads(run.stdout)['status'], 'incomplete')
