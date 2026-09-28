"""Reject broken distributable resources before a client installs the package."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'scripts/validate_plugin.py').is_file(), 'Repository validator is missing')
        spec = importlib.util.spec_from_file_location('package_validation', ROOT / 'scripts/validate_plugin.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='vale package ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('.agents', '.claude-plugin', 'plugins'):
            shutil.copytree(ROOT / name, self.root / name)

    def change(self, name, update):
        path = self.root / name
        data = json.loads(path.read_text()); update(data)
        path.write_text(json.dumps(data))

    def errors(self):
        return '\n'.join(self.module.validate_repository(self.root))

    def test_current_package_is_valid(self):
        self.assertEqual(self.errors(), '')

    def test_missing_skill_resource(self):
        path = self.root / 'plugins/vale/skills/check-prose/SKILL.md'
        path.write_text(path.read_text() + '\nRead [the local resource](references/missing.md).\n')
        self.assertIn('references/missing.md', self.errors())

    def test_marketplace_source_is_contained(self):
        for manifest, source in (('.agents/plugins/marketplace.json', {'source':'local','path':'../outside'}),
                                 ('.claude-plugin/marketplace.json', '../outside')):
            with self.subTest(host=manifest):
                original = (self.root / manifest).read_text()
                self.change(manifest, lambda d: d['plugins'][0].update(source=source))
                self.assertIn(manifest, self.errors())
                (self.root / manifest).write_text(original)

    def test_manifest_versions_agree(self):
        self.change('plugins/vale/.claude-plugin/plugin.json', lambda d: d.update(version='9.0.0'))
        self.assertIn('version', self.errors())

    def test_hook_entry_exists(self):
        (self.root / 'plugins/vale/scripts/prose_lint.py').unlink()
        self.assertIn('prose_lint.py', self.errors())

    def test_optional_host_fields_are_not_cross_validated(self):
        self.change('plugins/vale/.claude-plugin/plugin.json', lambda d: d.update(userConfig={'organization':{'type':'string','title':'Organization'}}))
        self.change('plugins/vale/.codex-plugin/plugin.json', lambda d: d.update(futureOptionalMetadata={'enabled':True}))
        self.assertEqual(self.errors(), '')

    def test_symlink_resource_cannot_escape_package(self):
        (self.root / 'outside.md').write_text('outside')
        resource = self.root / 'plugins/vale/skills/check-prose/outside.md'
        resource.symlink_to(self.root / 'outside.md')
        self.assertIn('symlink', self.errors())

    def test_invalid_skill_metadata_is_reported(self):
        path = self.root / 'plugins/vale/skills/check-prose/agents/openai.yaml'
        path.write_text('interface: []\n')
        self.assertIn('openai.yaml', self.errors())

    def test_malformed_manifest_is_actionable(self):
        (self.root / '.agents/plugins/marketplace.json').write_text('[]')
        self.assertIn('.agents/plugins/marketplace.json', self.errors())

    def test_malformed_hook_command_is_diagnostic(self):
        self.change('plugins/vale/hooks/hooks.json', lambda d: d['hooks']['Stop'][0]['hooks'][0].update(command=42))
        self.assertIn('hooks.json', self.errors())

    def test_missing_codex_author_name_is_diagnostic(self):
        self.change('plugins/vale/.codex-plugin/plugin.json', lambda d: d.update(author={}))
        self.assertIn('author', self.errors())

    def test_invalid_semver_prerelease_is_diagnostic(self):
        for host in ('codex','claude'):
            self.change(f'plugins/vale/.{host}-plugin/plugin.json', lambda d: d.update(version='1.0.0-01'))
        self.assertIn('version', self.errors())

    def test_codex_interface_requires_prompt_and_capabilities(self):
        name = 'plugins/vale/.codex-plugin/plugin.json'
        original = (self.root / name).read_text()
        for field in ('defaultPrompt', 'capabilities'):
            with self.subTest(field=field):
                self.change(name, lambda d: d['interface'].pop(field))
                self.assertIn(field, self.errors())
                (self.root / name).write_text(original)
