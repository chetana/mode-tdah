import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "mode-tdah"
HEADER = (
    "MODE TDAH ACTIF (permanent). Les règles ci-dessous s'appliquent à chaque réponse. "
    "« stop adhd mode » le désactive pour cette session ; supprimer {flag} "
    "pour le désactiver définitivement.\n\n"
)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


class ModeTdahHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "plugin with spaces"
        shutil.copytree(PLUGIN / "hooks", self.root / "hooks")
        shutil.copytree(PLUGIN / "skills", self.root / "skills")
        self.config = Path(tmp.name) / "claude config"
        self.config.mkdir()
        self.flag = self.config / ".mode-tdah-always"

    def runtimes(self):
        out = []
        if node := shutil.which("node"):
            out.append(("node", [node, self.root / "hooks" / "always-on.mjs"]))
        if sh := shutil.which("sh"):
            out.append(("sh", [sh, self.root / "hooks" / "always-on.sh"]))
        if ps := shutil.which("pwsh") or shutil.which("powershell"):
            out.append(("powershell", [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
                                       "-File", self.root / "hooks" / "always-on.ps1"]))
        return out

    def run_hook(self, cmd, env_extra=None):
        env = os.environ.copy()
        env["CLAUDE_CONFIG_DIR"] = str(self.config)
        env.update(env_extra or {})
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                              encoding="utf-8", env=env, check=False)

    @staticmethod
    def norm(s):
        return s.replace("\r\n", "\n").replace("\\", "/")

    def test_silent_without_flag(self):
        self.assertTrue(self.runtimes())
        for name, cmd in self.runtimes():
            with self.subTest(runtime=name):
                r = self.run_hook(cmd)
                self.assertEqual((0, "", ""), (r.returncode, r.stdout, r.stderr))

    def test_silent_with_legacy_flag_only(self):
        (self.config / ".i-have-adhd-always").touch()
        for name, cmd in self.runtimes():
            with self.subTest(runtime=name):
                self.assertEqual("", self.run_hook(cmd).stdout)
        self.assertTrue((self.config / ".i-have-adhd-always").exists())

    def test_french_header_and_stripped_frontmatter_identical_across_runtimes(self):
        self.flag.touch()
        outputs = {}
        for name, cmd in self.runtimes():
            with self.subTest(runtime=name):
                r = self.run_hook(cmd)
                self.assertEqual(0, r.returncode)
                self.assertEqual("", r.stderr)
                out = self.norm(r.stdout)
                self.assertTrue(out.startswith(self.norm(HEADER.format(flag=self.flag))), out[:300])
                self.assertNotIn("name: mode-tdah", out)
                self.assertNotIn("disable-model-invocation", out)
                self.assertIn("# mode-tdah", out)
                self.assertIn("mode normal", out)
                outputs[name] = out
        self.assertEqual(1, len(set(outputs.values())))

    def test_unclosed_frontmatter_is_kept(self):
        (self.root / "skills" / "mode-tdah" / "SKILL.md").write_text(
            "---\nname: x\nCorps sans fin de fence.\n", encoding="utf-8")
        self.flag.touch()
        for name, cmd in self.runtimes():
            with self.subTest(runtime=name):
                self.assertIn("Corps sans fin de fence.", self.run_hook(cmd).stdout)

    def test_hooks_json_launcher_reads_plugin_root(self):
        cfg = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
        hook = cfg["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertIn("always-on.mjs", hook["command"])
        self.flag.touch()
        env = os.environ.copy()
        env.update(CLAUDE_CONFIG_DIR=str(self.config), CLAUDE_PLUGIN_ROOT=str(self.root))
        r = subprocess.run(hook["command"], shell=True, capture_output=True, text=True,
                           encoding="utf-8", env=env, input="{}", check=False)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertTrue(r.stdout.startswith("MODE TDAH ACTIF (permanent)."))

    def test_hook_swallows_missing_plugin_root(self):
        self.flag.touch()
        cfg = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
        cmd = cfg["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        env = os.environ.copy()
        env.update(CLAUDE_CONFIG_DIR=str(self.config), CLAUDE_PLUGIN_ROOT=str(self.root / "absent"))
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, check=False)
        self.assertEqual((0, "", ""), (r.returncode, r.stdout, r.stderr))


class ManifestTest(unittest.TestCase):
    def test_names_are_consistent(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        fm = frontmatter(PLUGIN / "skills" / "mode-tdah" / "SKILL.md")
        self.assertIsNotNone(fm)
        self.assertEqual("mode-tdah", manifest["name"])
        self.assertRegex(fm, r"(?m)^name: mode-tdah$")

    def test_marketplace_exposes_french_plugin(self):
        mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual("mode-tdah", mk["name"])
        sources = {p["name"]: p["source"] for p in mk["plugins"]}
        self.assertEqual({"mode-tdah": "./plugins/mode-tdah"}, sources)
        self.assertTrue((ROOT / sources["mode-tdah"] / ".claude-plugin" / "plugin.json").is_file())


class ClineInstallerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.rules = self.home / ".cline" / "rules"
        self.rules.mkdir(parents=True)
        self.other = self.rules / "20-output-style.md"
        self.other.write_text("autre règle\n")
        self.cwd = Path(tmp.name) / "proj"
        self.cwd.mkdir()
        self.script = PLUGIN / "install-cline.sh"

    def run_script(self, *args):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(["sh", str(self.script), *args], capture_output=True, text=True,
                              env=env, cwd=self.cwd, check=False)

    def test_install_idempotent_and_uninstall_global(self):
        target = self.rules / "30-mode-tdah.md"
        r = self.run_script()
        self.assertEqual(0, r.returncode, r.stderr)
        first = target.read_text(encoding="utf-8")
        self.assertNotIn("name: mode-tdah", first)
        self.assertNotIn("disable-model-invocation", first)
        self.assertIn("# mode-tdah", first)
        self.assertEqual(0, self.run_script().returncode)
        self.assertEqual(first, target.read_text(encoding="utf-8"))
        self.assertEqual("autre règle\n", self.other.read_text())
        self.assertEqual([], [p for p in self.rules.iterdir() if p.name.startswith(".mode-tdah.")])
        self.assertEqual(0, self.run_script("--uninstall").returncode)
        self.assertFalse(target.exists())
        self.assertEqual("autre règle\n", self.other.read_text())
        self.assertEqual(0, self.run_script("--uninstall").returncode)

    def test_project_scope(self):
        self.assertEqual(0, self.run_script("--project").returncode)
        target = self.cwd / ".clinerules" / "mode-tdah.md"
        self.assertTrue(target.is_file())
        self.assertFalse((self.rules / "30-mode-tdah.md").exists())
        self.assertEqual(0, self.run_script("--project", "--uninstall").returncode)
        self.assertFalse(target.exists())

    def test_unknown_option_fails(self):
        self.assertEqual(2, self.run_script("--bidon").returncode)


class StaticChecksTest(unittest.TestCase):
    def test_ps1_has_utf8_bom(self):
        # Windows PowerShell 5 lit un fichier sans BOM en ANSI et abîme les accents.
        data = (PLUGIN / "hooks" / "always-on.ps1").read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"OpenStandardOutput", data)

    def test_skill_structure(self):
        path = PLUGIN / "skills" / "mode-tdah" / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        self.assertRegex(frontmatter(path), r"(?m)^name: mode-tdah$")
        self.assertEqual([str(i) for i in range(1, 11)],
                         re.findall(r"(?m)^### (\d+)\. ", text))
        self.assertRegex(text, r"(?m)^## Quand déroger aux règles$")
        self.assertRegex(text, r"(?m)^## Vérification avant envoi$")
        self.assertNotIn("apprêtes", text)

    def test_license_is_shipped(self):
        self.assertEqual((ROOT / "LICENSE").read_text(), (PLUGIN / "LICENSE").read_text())


if __name__ == "__main__":
    unittest.main()
