import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import scripts.package_release as package_release
from scripts.validate_release_version import MANIFESTS, mismatches


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plugin = self.root / "plugins" / "vale"
        self.plugin.mkdir(parents=True)
        (self.root / "LICENSE").write_text("Plugin license notice\n", encoding="utf-8")
        (self.plugin / ".claude-plugin").mkdir()
        (self.plugin / ".codex-plugin").mkdir()
        (self.plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        (self.plugin / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        (self.plugin / "shared.txt").write_text("shared", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_both_archives_include_project_license_and_only_client_manifest(self):
        with patch.object(package_release, "ROOT", self.root), patch.object(
            package_release, "PLUGIN", self.plugin
        ):
            for client, excluded, included in (
                ("claude", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"),
                ("codex", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"),
            ):
                target = self.root / f"vale-{client}.zip"
                package_release.archive(target, client)
                with zipfile.ZipFile(target) as archive:
                    self.assertIn("vale/LICENSE", archive.namelist())
                    self.assertEqual(archive.read("vale/LICENSE"), b"Plugin license notice\n")
                    self.assertIn(f"vale/{included}", archive.namelist())
                    self.assertNotIn(f"vale/{excluded}", archive.namelist())

    def test_archives_exclude_eval_suite(self):
        (self.plugin / "evals" / "smoke").mkdir(parents=True)
        (self.plugin / "evals" / "smoke" / "prompt.md").write_text("Check prose.", encoding="utf-8")
        with patch.object(package_release, "ROOT", self.root), patch.object(
            package_release, "PLUGIN", self.plugin
        ):
            for client in ("claude", "codex"):
                target = self.root / f"vale-{client}.zip"
                package_release.archive(target, client)
                with zipfile.ZipFile(target) as archive:
                    self.assertIn("vale/shared.txt", archive.namelist())
                    self.assertFalse(any(name.startswith("vale/evals/") for name in archive.namelist()))

    def test_archives_are_reproducible(self):
        with patch.object(package_release, "ROOT", self.root), patch.object(
            package_release, "PLUGIN", self.plugin
        ):
            first = self.root / "first.zip"
            second = self.root / "second.zip"
            package_release.archive(first, "claude")
            package_release.archive(second, "claude")
        first_hash = hashlib.sha256(first.read_bytes()).digest()
        second_hash = hashlib.sha256(second.read_bytes()).digest()
        self.assertEqual(first_hash, second_hash)


class ReleaseVersionTests(unittest.TestCase):
    def test_both_manifest_versions_must_match_tag(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in MANIFESTS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
            self.assertEqual(mismatches("v1.2.3", root), [])

            codex_manifest = root / "plugins/vale/.codex-plugin/plugin.json"
            codex_manifest.write_text(json.dumps({"version": "1.2.2"}), encoding="utf-8")
            errors = mismatches("v1.2.3", root)
            self.assertEqual(len(errors), 1)
            self.assertIn(".codex-plugin/plugin.json", errors[0])


if __name__ == "__main__":
    unittest.main()
