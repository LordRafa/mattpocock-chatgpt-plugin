import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build import NAME, build

SHA = "a" * 40


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.upstream = self.base / "upstream"
        (self.upstream / ".claude-plugin").mkdir(parents=True)
        self.tdd = self.upstream / "skills/engineering/tdd"
        self.teach = self.upstream / "skills/productivity/teach"
        (self.tdd / "agents").mkdir(parents=True)
        (self.teach / "agents").mkdir(parents=True)
        self.manifest("1.3.2", ["./skills/engineering/tdd", "./skills/productivity/teach"])
        (self.upstream / "LICENSE").write_text("MIT License. Matt Pocock")
        (self.tdd / "SKILL.md").write_text("---\nname: tdd\ndescription: TDD.\n---\nRed green refactor\n")
        (self.tdd / "agents/openai.yaml").write_text("interface:\n  display_name: TDD\n  short_description: Test first\n")
        (self.tdd / "notes.md").write_text("Reference")
        (self.teach / "SKILL.md").write_text("---\nname: teach\ndescription: Teach.\ndisable-model-invocation: true\n---\nLearn!\n")
        (self.teach / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        self.state = self.base / "state/latest.json"

    def manifest(self, version, skills):
        (self.upstream / ".claude-plugin/plugin.json").write_text(json.dumps({
            "name": "mattpocock-skills", "version": version, "skills": skills
        }))

    def run_build(self):
        target = self.base / "plugin"
        if target.exists():
            import shutil
            shutil.rmtree(target)
        return build(self.upstream, target, self.base / "dist", self.state, SHA)

    def remember(self, result):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text((self.base / "dist/state.json").read_text())

    def test_version_matches_upstream(self):
        result = self.run_build()
        self.assertTrue(result["changed"])
        self.assertEqual(result["version"], "1.3.2")
        with zipfile.ZipFile(result["archive"]) as archive:
            plugin = json.loads(archive.read(f"{NAME}/plugin.json"))
            self.assertEqual(plugin["version"], "1.3.2")
            self.assertIn(f"{NAME}/skills/tdd/notes.md", archive.namelist())
            self.assertEqual(archive.read(f"{NAME}/LICENSE"), b"MIT License. Matt Pocock")
            self.assertIn("display_name: TDD", archive.read(f"{NAME}/skills/tdd/agents/openai.yaml").decode())
            self.assertIn("allow_implicit_invocation: false", archive.read(f"{NAME}/skills/teach/agents/openai.yaml").decode())

    def test_no_new_release_if_identical(self):
        self.remember(self.run_build())
        self.assertFalse(self.run_build()["changed"])

    def test_content_change_without_version_change(self):
        self.remember(self.run_build())
        (self.tdd / "notes.md").write_text("Changed reference")
        result = self.run_build()
        self.assertTrue(result["changed"])
        self.assertEqual(result["version"], "1.3.2")

    def test_upstream_version_updates_directly(self):
        self.remember(self.run_build())
        self.manifest("1.4.0", ["./skills/engineering/tdd", "./skills/productivity/teach"])
        result = self.run_build()
        self.assertEqual(result["version"], "1.4.0")
        self.assertTrue(result["changed"])

    def test_rejects_duplicates(self):
        self.manifest("1.3.2", ["./skills/engineering/tdd", "./skills/misc/tdd"])
        with self.assertRaises(ValueError):
            self.run_build()

    def test_rejects_symlinks(self):
        (self.tdd / "malicious").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            self.run_build()

    def test_rejects_traversal(self):
        self.manifest("1.3.2", ["./skills/../../etc"])
        with self.assertRaises(ValueError):
            self.run_build()

    def test_rejects_downgrade(self):
        self.remember(self.run_build())
        self.manifest("1.2.9", ["./skills/engineering/tdd", "./skills/productivity/teach"])
        with self.assertRaisesRegex(ValueError, "decreased"):
            self.run_build()


if __name__ == "__main__":
    unittest.main()
