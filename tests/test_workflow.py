"""Exercise publication guards and dependencies from the actual workflow."""
import ast
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def condition(expression, event, ref):
    expression = expression.removeprefix('${{').removesuffix('}}').strip()
    expression = expression.replace('github.event_name', repr(event)).replace('github.ref', repr(ref))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    tree = ast.parse(expression, mode='eval')
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq, ast.Constant)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError('Unsupported publication guard expression')
    return eval(compile(tree, '<workflow condition>', 'eval'), {'__builtins__': {}})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load((ROOT / '.github/workflows/ci-pages.yml').read_text(), Loader=yaml.BaseLoader)

    def test_only_main_push_can_publish_artifacts_and_deploy(self):
        jobs = self.workflow['jobs']
        guards = [jobs['deploy']['if']]
        uploads = [s for s in jobs['build']['steps'] if 'actions/upload-pages-artifact@' in s.get('uses', '')]
        self.assertEqual(len(uploads), 1)
        guards.append(uploads[0]['if'])
        cases = [('pull_request','refs/heads/main',False), ('pull_request','refs/pull/8/merge',False),
                 ('push','refs/heads/main',True), ('push','refs/heads/topic',False),
                 ('schedule','refs/heads/main',False), ('workflow_dispatch','refs/heads/main',False)]
        for guard in guards:
            for event, ref, expected in cases:
                with self.subTest(event=event, ref=ref, guard=guard):
                    self.assertEqual(condition(guard, event, ref), expected)
        self.assertNotIn('pull_request_target', self.workflow['on'])

    def test_deployment_requires_all_checks_and_read_only_pr_jobs(self):
        jobs = self.workflow['jobs']
        self.assertEqual(set(jobs['deploy']['needs']), {'test', 'native', 'build'})
        self.assertEqual(self.workflow['permissions'], {'contents':'read'})
        for name in ('test', 'native', 'build'):
            self.assertNotIn('permissions', jobs[name])
            for step in jobs[name]['steps']:
                if 'actions/checkout@' in step.get('uses', ''):
                    self.assertEqual(step.get('with', {}).get('persist-credentials'), 'false')
        self.assertEqual(jobs['deploy']['permissions'], {'pages':'write', 'id-token':'write'})
