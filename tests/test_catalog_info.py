import json
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

import scripts.check_catalog_info as checker

ROOT = Path(__file__).resolve().parents[1]


class CatalogInfoTests(unittest.TestCase):
    def test_repository_catalog_is_valid(self):
        self.assertEqual([], checker.validate(ROOT))

    def test_unknown_top_level_field_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["manualCount"] = 3
        self.assertTrue(any("schema" in error for error in checker.validate(ROOT, data)))

    def test_catalog_must_identify_the_canonical_package(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["pluginId"] = "typo"
        data["examples"] = []
        data["hooks"] = []
        data["mcpServers"] = {}
        self.assertTrue(any("canonical package" in error for error in checker.validate(ROOT, data)))

    def test_unknown_source_format_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["overview"]["format"] = "markdwon"
        self.assertTrue(any("unsupported source format" in error for error in checker.validate(ROOT, data)))

        data["overview"]["required"] = False
        data["overview"]["path"] = "missing.md"
        self.assertTrue(any("unsupported source format" in error for error in checker.validate(ROOT, data)))

    def test_unknown_source_mode_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["overview"]["mode"] = "lede"
        self.assertTrue(any("unsupported source mode" in error for error in checker.validate(ROOT, data)))

    def test_missing_selector_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        target = None
        def find_selector(value):
            nonlocal target
            if isinstance(value, dict):
                if value.get("format") == "html" and "selector" in value:
                    target = (value, "html")
                    return
                if value.get("format") == "markdown" and "heading_path" in value:
                    target = (value, "markdown")
                    return
                for child in value.values():
                    find_selector(child)
                    if target:
                        return
            elif isinstance(value, list):
                for child in value:
                    find_selector(child)
                    if target:
                        return
        find_selector(data)
        self.assertIsNotNone(target, "catalog must exercise a document selector")
        source, format_name = target
        source.pop("selector" if format_name == "html" else "heading_path")
        self.assertTrue(any("selector" in error or "heading" in error for error in checker.validate(ROOT, data)))

    def test_duplicate_markdown_heading_path_is_ambiguous(self):
        self.assertEqual(2, checker._heading_matches("# Parent\n\n## Same\n\n## Same\n", ["Same"]))

    def test_stale_selector_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        target = None
        def find_selector(value):
            nonlocal target
            if isinstance(value, dict):
                if value.get("format") == "html" and "selector" in value:
                    target = (value, "html")
                    return
                if value.get("format") == "markdown" and "heading_path" in value:
                    target = (value, "markdown")
                    return
                for child in value.values():
                    find_selector(child)
                    if target:
                        return
            elif isinstance(value, list):
                for child in value:
                    find_selector(child)
                    if target:
                        return
        find_selector(data)
        source, format_name = target
        if format_name == "html":
            source["selector"] = "#catalog-section-that-does-not-exist"
        else:
            source["heading_path"] = ["Catalog section that does not exist"]
        self.assertTrue(any("selector" in error or "heading" in error for error in checker.validate(ROOT, data)))

    def test_optional_existing_source_still_requires_a_valid_selector(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        source = data["examples"][0]["sources"][0]
        source["required"] = False
        source["heading_path"] = ["Heading that does not exist"]
        errors = checker.validate(ROOT, data)
        self.assertTrue(any("heading selector must match exactly once" in error for error in errors))

    def test_optional_missing_source_remains_allowed(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        source = data["examples"][0]["sources"][0]
        source["required"] = False
        source["path"] = "docs/not-present.md"
        source.pop("heading_path")
        self.assertFalse(any("source path missing" in error for error in checker.validate(ROOT, data)))

    def test_invented_capability_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["examples"][0]["capability_refs"] = ["mcp_tool:invented_tool"]
        self.assertTrue(any("capability" in error for error in checker.validate(ROOT, data)))

    def test_invented_mcp_server_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["mcpServers"]["invented-server"] = {}
        self.assertTrue(any("MCP server" in error for error in checker.validate(ROOT, data)))

    def test_invented_hook_target_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["hooks"] = [{"target": {"path": "plugins/missing/hooks.json", "pointer": "/hooks/Unknown/0/hooks/0"}}]
        self.assertTrue(any("hook target" in error for error in checker.validate(ROOT, data)))

    def test_missing_hook_source_path_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["hooks"][0]["sources"][0].pop("path")
        errors = checker.validate(ROOT, data)
        self.assertTrue(any("catalog source path must be a string" in error for error in errors))

    def test_example_must_reference_declared_platform(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["examples"][0]["platform"] = "claud-code"
        errors = checker.validate(ROOT, data)
        self.assertTrue(any("example references undeclared platform: claud-code" in error for error in errors))

    def test_path_escape_is_rejected(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        data["examples"][0]["sources"][0]["path"] = "../outside.md"
        self.assertTrue(any("path" in error for error in checker.validate(ROOT, data)))

    def test_documented_platform_requires_sources(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        key = next(iter(data["platforms"]))
        data["platforms"][key]["sources"] = []
        self.assertTrue(any("source" in error for error in checker.validate(ROOT, data)))

    def test_platform_source_must_resolve_even_when_marked_optional(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        key = next(iter(data["platforms"]))
        data["platforms"][key]["sources"] = [
            {"path": "missing.md", "format": "markdown", "mode": "lead", "required": False}
        ]
        self.assertTrue(any("at least one resolved source" in error for error in checker.validate(ROOT, data)))

    def test_native_mcp_server_must_be_declared_in_catalog(self):
        data = json.loads((ROOT / "catalog-info.json").read_text())
        capabilities, hook_targets = checker._native(ROOT, checker.CANONICAL_PLUGIN_ID)
        capabilities.add("mcp_server:new-server")
        with patch.object(checker, "_native", return_value=(capabilities, hook_targets)):
            errors = checker.validate(ROOT, data)
        self.assertTrue(any("native MCP server is missing from metadata: new-server" in error for error in errors))

    def test_native_inventory_follows_declared_component_paths_and_package_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "plugins" / "vale"
            (package / ".claude-plugin").mkdir(parents=True)
            (package / ".codex-plugin").mkdir()
            (package / "custom-skills" / "review-prose").mkdir(parents=True)
            (package / "operations").mkdir()
            (package / "runtime").mkdir()
            (package / "src").mkdir()
            (root / "src").mkdir()
            (package / ".claude-plugin" / "plugin.json").write_text(json.dumps({
                "skills": "custom-skills",
                "commands": "operations",
                "hooks": "runtime/lifecycle.json",
            }))
            (package / ".codex-plugin" / "plugin.json").write_text("{}")
            (package / "custom-skills" / "review-prose" / "SKILL.md").write_text(
                "---\nname: review-prose\ndescription: Review prose.\n---\n"
            )
            (package / "operations" / "audit.md").write_text("# Audit\n")
            (package / "runtime" / "lifecycle.json").write_text(json.dumps({
                "hooks": {"AfterEdit": [{"hooks": [{}]}]}
            }))
            (package / "src" / "server.rs").write_text('tool("package_tool", "description");')
            (root / "src" / "unrelated.rs").write_text('tool("unrelated_tool", "description");')

            capabilities, hook_targets = checker._native(root, "vale")

        self.assertIn("skill:review-prose", capabilities)
        self.assertIn("command:audit", capabilities)
        self.assertIn("mcp_tool:package_tool", capabilities)
        self.assertNotIn("mcp_tool:unrelated_tool", capabilities)
        self.assertIn("plugins/vale/runtime/lifecycle.json#/hooks/AfterEdit/0/hooks/0", hook_targets)


if __name__ == "__main__":
    unittest.main()
