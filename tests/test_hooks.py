"""Exercise real hook subprocesses and Vale against temporary workspaces."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'plugins/vale/scripts/prose_lint.py'
BAD = 'We will simply utilize this, e.g. for testing.\n'
GOOD = 'Use this file for testing.\n'


@unittest.skipUnless(shutil.which('vale'), 'Integration tests require Vale')
class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vale hook ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.file = self.root / 'docs with spaces.md'
        self.file.write_text(GOOD)

    def event(self, event, name='Bash', inputs=None, **extra):
        payload = dict(hook_event_name=event, session_id='test/session', tool_use_id='call1',
                       tool_name=name, tool_input=inputs or {'command': 'a command'}, cwd=str(self.root))
        payload.update(extra)
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                capture_output=True, text=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_shell_edit_feedback_and_stop_correction(self):
        self.assertEqual(self.event('PreToolUse'), {})
        self.file.write_text(BAD)
        post = self.event('PostToolUse')
        self.assertIn('Google.Latin', post['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('decision', post)  # Preserve tool output, even on a failed shell call.
        self.assertEqual(self.event('Stop')['decision'], 'block')
        self.file.write_text(GOOD)
        self.assertEqual(self.event('Stop', stop_hook_active=True), {})

    def test_stop_loop_guard_reports_remaining_findings(self):
        self.event('PreToolUse')
        self.file.write_text(BAD)
        self.assertEqual(self.event('Stop')['decision'], 'block')
        again = self.event('Stop', stop_hook_active=True)
        self.assertNotIn('decision', again)
        self.assertIn('unresolved', again['systemMessage'])

    def test_read_tool_does_not_lint_existing_bad_prose(self):
        self.file.write_text(BAD)
        self.event('PreToolUse', name='mcp__files__read', inputs={'path': str(self.file)})
        self.assertEqual(self.event('PostToolUse', name='mcp__files__read', inputs={'path': str(self.file)}), {})
        self.assertEqual(self.event('Stop'), {})

    def test_mcp_and_unknown_tools_detect_edits_without_parsing_commands(self):
        self.event('PreToolUse', name='mcp__files__edit')
        self.file.write_text(BAD)
        self.assertIn('hookSpecificOutput', self.event('PostToolUse', name='mcp__files__edit'))

    def test_patch_direct_fallback(self):
        self.file.write_text(BAD)
        post = self.event('PostToolUse', name='apply_patch', inputs={'command': '*** Begin Patch\n*** Update File: docs with spaces.md\n*** End Patch'})
        self.assertIn('Google.Latin', post['hookSpecificOutput']['additionalContext'])

    def test_new_file_and_missing_post_event_caught_at_stop(self):
        self.event('PreToolUse')
        (self.root / 'new.md').write_text(BAD)
        self.assertEqual(self.event('Stop')['decision'], 'block')

    def test_read_after_edit_has_no_duplicate_feedback(self):
        self.event('PreToolUse')
        self.file.write_text(BAD)
        self.event('PostToolUse')
        self.event('PreToolUse')
        self.assertEqual(self.event('PostToolUse'), {})
        self.assertEqual(self.event('Stop')['decision'], 'block')

    def test_concurrent_pre_events_do_not_reset_baseline(self):
        self.event('PreToolUse')
        self.file.write_text(BAD)
        self.event('PreToolUse', tool_use_id='call2')
        self.assertIn('hookSpecificOutput', self.event('PostToolUse', tool_use_id='call2'))
        self.assertEqual(self.event('PostToolUse'), {})

    def test_deleted_files_do_not_block(self):
        self.event('PreToolUse')
        self.file.unlink()
        self.assertEqual(self.event('PostToolUse'), {})
        self.assertEqual(self.event('Stop'), {})

    def test_ignored_generated_and_symlink_files(self):
        (self.root / '.gitignore').write_text('generated/\n')
        self.event('PreToolUse')
        (self.root / 'generated').mkdir()
        (self.root / 'generated/file.md').write_text(BAD)
        (self.root / 'alias.md').symlink_to(self.file)
        self.assertEqual(self.event('PostToolUse'), {})

    def test_option_like_filename(self):
        self.event('PreToolUse')
        (self.root / '--config=evil.md').write_text(BAD)
        self.assertIn('Google.Latin', self.event('PostToolUse')['hookSpecificOutput']['additionalContext'])

    def test_source_comments_only(self):
        self.event('PreToolUse')
        code = self.root / 'example.py'
        code.write_text("value = 'We will use this, e.g. for testing.'\n# Use this file for testing.\n")
        self.assertEqual(self.event('PostToolUse'), {})
        self.event('PreToolUse')
        code.write_text('# ' + BAD + 'value = 1\n')
        self.assertIn('Google.Latin', self.event('PostToolUse')['hookSpecificOutput']['additionalContext'])

    def test_non_git_workspace(self):
        shutil.rmtree(self.root / '.git')
        self.event('PreToolUse')
        self.file.write_text(BAD)
        self.assertIn('hookSpecificOutput', self.event('PostToolUse'))

    def test_existing_project_config_is_used(self):
        (self.root / '.vale.ini').write_text('MinAlertLevel = error\n[*.md]\nBasedOnStyles = Vale\nVale.Spelling = NO\n')
        self.event('PreToolUse')
        self.file.write_text(BAD)
        self.assertEqual(self.event('PostToolUse'), {})

    def test_large_file_reports_incomplete_check(self):
        self.event('PreToolUse')
        self.file.write_text('a' * (1024 * 1024 + 1))
        self.assertIn('exceeds', self.event('PostToolUse')['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.event('Stop')['decision'], 'block')

    def test_missing_vale_reports_incomplete_check(self):
        self.event('PreToolUse')
        self.file.write_text(BAD)
        payload = dict(hook_event_name='PostToolUse', session_id='test/session', cwd=str(self.root))
        binary = self.root / 'bin'
        binary.mkdir()
        (binary / 'git').symlink_to(shutil.which('git'))
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
                                text=True, env=dict(os.environ, PATH=str(binary)))
        self.assertIn('Vale is missing', result.stdout)

    def test_project_install_command_from_subdirectory(self):
        subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--project', str(self.root)], check=True, capture_output=True)
        sub = self.root / 'docs'
        sub.mkdir()
        command = json.loads((self.root / '.codex/hooks.json').read_text())['hooks']['PreToolUse'][0]['hooks'][0]['command']
        result = subprocess.run(command, shell=True, cwd=sub, input=json.dumps(dict(hook_event_name='PreToolUse', session_id='installed', cwd=str(sub))), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})


if __name__ == '__main__':
    unittest.main()
