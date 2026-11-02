#!/usr/bin/env python3
"""Check protocol resource generation, local links and installation using temporary fixtures.

Link checks cover ordinary inline Markdown links, not all Markdown syntax. Installation
checks exercise the existing installer with disposable homes and projects; they do not
claim that either host loaded a skill, trusted a hook or displayed a native UI.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tools"))
import check_ddl  # noqa: E402
import ddl_setup  # noqa: E402

SYNC = ROOT / "tools/sync_mirrors.py"
COMMANDS = ("draft", "realize", "reflect", "validate", "commit", "docs", "refactoring", "resonate")
INLINE_LINK = re.compile(r"\[[^\]]+\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)")
INLINE_CODE = re.compile(r"`+[^`\n]*`+")


def local_link_errors(bundle):
    """Validate local links and reachability of Markdown resources from the entry point."""
    errors = []
    root = bundle.resolve()
    documents = [bundle / "SKILL.md"]
    references = bundle / "references"
    if references.is_dir():
        documents.extend(sorted(references.rglob("*.md")))
    graph = {}
    for document in documents:
        if not document.is_file():
            errors.append(f"missing document: {document}")
            continue
        try:
            resolved_document = document.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            errors.append(f"unresolvable document: {document}: {exc}")
            continue
        if document.is_symlink() or not resolved_document.is_relative_to(root):
            errors.append(f"document leaves skill or is a symlink: {document}")
            continue
        graph[resolved_document] = set()
        fence = None
        for number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            opening = re.match(r"^\s*(`{3,}|~{3,})", line)
            if opening:
                symbol = opening.group(1)[0]
                if fence is None:
                    fence = symbol
                elif fence == symbol:
                    fence = None
                continue
            if fence:
                continue
            for link in INLINE_LINK.findall(INLINE_CODE.sub("", line)):
                try:
                    target = urlsplit(link)
                except ValueError:
                    errors.append(f"invalid link: {document}:{number}: {link}")
                    continue
                if target.scheme or target.netloc or not target.path or target.path.startswith("/"):
                    continue
                try:
                    path = (document.parent / unquote(target.path)).resolve()
                except (OSError, RuntimeError) as exc:
                    errors.append(f"unresolvable link: {document}:{number}: {link}: {exc}")
                    continue
                if not path.is_relative_to(root):
                    errors.append(f"link leaves skill: {document}:{number}: {link}")
                elif not path.is_file():
                    errors.append(f"missing link target: {document}:{number}: {link}")
                else:
                    graph[resolved_document].add(path)
    pending = [documents[0].resolve()]
    reached = set()
    while pending:
        path = pending.pop()
        if path in reached:
            continue
        reached.add(path)
        pending.extend(graph.get(path, ()))
    for document in documents[1:]:
        if document.is_file() and not document.is_symlink() and document.resolve() not in reached:
            errors.append(f"unreachable Markdown resource: {document}")
    return errors


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ddl-protocol-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "source fixture"
        self.repo.mkdir()

    def source_fixture(self):
        skills = self.repo / "claude-code/skills"
        for name in ("ddl-protocol", *COMMANDS):
            path = skills / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: {name}\ndescription: test\nshort-description: test\n---\n\n# {name}\n")
        refs = skills / "ddl-protocol/references"
        (refs / "nested").mkdir(parents=True)
        (refs / "intro.md").write_text("# Intro\n[More](nested/procedure.md#part)\n")
        (refs / "nested/procedure.md").write_text("# Part\n[Intro](../intro.md)\n")
        (refs / "nested/data.bin").write_bytes(b"\x00\xff\n")
        (skills / "ddl-protocol/SKILL.md").write_text(
            "---\nname: ddl-protocol\ndescription: test\n---\n\n# Protocol\n[Intro](references/intro.md)\n")
        gate = self.repo / "tools/ddl_gate.py"
        gate.parent.mkdir(parents=True)
        gate.write_text("# fixture\n")
        return refs

    def sync(self, *args):
        return subprocess.run([sys.executable, "-I", str(SYNC), str(self.repo), *args],
                              capture_output=True, text=True, timeout=20)

    def test_resources_are_recursive_exact_and_extras_are_never_deleted(self):
        refs = self.source_fixture()
        self.assertEqual(self.sync().returncode, 0)
        output = self.repo / "codex/.agents/skills/ddl-protocol/references"
        for path in refs.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (output / path.relative_to(refs)).read_bytes())
        self.assertEqual(self.sync("--check").returncode, 0)
        generated = output / "intro.md"
        generated.write_text("altered\n")
        self.assertNotEqual(self.sync("--check").returncode, 0)
        self.assertEqual(self.sync().returncode, 0)
        generated.unlink()
        checked = self.sync("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("missing generated file", checked.stdout)
        self.assertEqual(self.sync().returncode, 0)
        (refs / "nested/new.md").write_text("new resource\n")
        self.assertNotEqual(self.sync("--check").returncode, 0)
        self.assertEqual(self.sync().returncode, 0)
        (refs / "nested/new.md").unlink()
        checked = self.sync("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("unexpected protocol reference", checked.stderr)
        self.assertTrue((output / "nested/new.md").exists())
        unknown = output / "user-note.md"
        unknown.write_text("user-owned\n")
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(unknown.read_text(), "user-owned\n")

    def test_generated_and_source_symlinks_are_not_followed(self):
        refs = self.source_fixture()
        self.assertEqual(self.sync().returncode, 0)
        output = self.repo / "codex/.agents/skills/ddl-protocol/references"
        victim = self.base / "unrelated.txt"
        victim.write_text("keep\n")
        target = output / "intro.md"
        target.unlink()
        target.symlink_to(victim)
        for args in ((), ("--check",)):
            result = self.sync(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr)
            self.assertEqual(victim.read_text(), "keep\n")
        target.unlink()
        self.assertEqual(self.sync().returncode, 0)
        skill = self.repo / "codex/.agents/skills/ddl-protocol/SKILL.md"
        skill.unlink()
        skill.symlink_to(victim)
        self.assertNotEqual(self.sync().returncode, 0)
        self.assertNotEqual(self.sync("--check").returncode, 0)
        self.assertEqual(victim.read_text(), "keep\n")
        skill.unlink()
        self.assertEqual(self.sync().returncode, 0)
        nested = output / "nested"
        shutil.rmtree(nested)
        outside_dir = self.base / "user directory"
        outside_dir.mkdir()
        (outside_dir / "README.md").write_text("keep directory contents\n")
        nested.symlink_to(outside_dir, target_is_directory=True)
        self.assertNotEqual(self.sync().returncode, 0)
        self.assertNotEqual(self.sync("--check").returncode, 0)
        self.assertEqual((outside_dir / "README.md").read_text(), "keep directory contents\n")
        nested.unlink()
        (refs / "linked.md").symlink_to(victim)
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(victim.read_text(), "keep\n")

    def test_links_accept_local_fragments_and_reject_missing_or_escape(self):
        refs = self.source_fixture()
        bundle = refs.parent
        self.assertEqual(local_link_errors(bundle), [])
        intro = refs / "intro.md"
        intro.write_text("[Missing](missing.md)\n")
        self.assertTrue(any("missing link target" in x for x in local_link_errors(bundle)))
        (self.base / "outside.md").write_text("outside\n")
        intro.write_text("[Escape](../../../../../../outside.md)\n")
        self.assertTrue(any("link leaves skill" in x for x in local_link_errors(bundle)))
        intro.write_text("[More](nested/procedure.md)\n```markdown\n[Example](missing.md)\n```\n`[Inline](missing.md)`\n[Web](https://example.com/a)\n")
        self.assertEqual(local_link_errors(bundle), [])
        orphan = refs / "unused.md"
        orphan.write_text("# Unused\n")
        self.assertTrue(any("unreachable Markdown resource" in x for x in local_link_errors(bundle)))
        intro.write_text(intro.read_text() + "\n[Now reachable](unused.md)\n")
        self.assertEqual(local_link_errors(bundle), [])
        orphan.unlink()
        orphan.symlink_to(self.base / "outside.md")
        self.assertTrue(any("symlink" in x for x in local_link_errors(bundle)))

    def test_source_and_generated_skill_links(self):
        for bundle in (ROOT / "claude-code/skills/ddl-protocol", ROOT / "codex/.agents/skills/ddl-protocol"):
            with self.subTest(bundle=bundle):
                self.assertEqual(local_link_errors(bundle), [])

    def test_current_resources_survive_project_installation(self):
        project = self.base / "actual project kit"
        project.mkdir()
        result = subprocess.run([sys.executable, "-I", str(ROOT / "bin/ddl_setup.py"),
                                 "install", "--project", str(project)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for source, installed in ((ROOT / "claude-code/skills/ddl-protocol", project / ".claude/skills/ddl-protocol"),
                                  (ROOT / "codex/.agents/skills/ddl-protocol", project / ".agents/skills/ddl-protocol")):
            for file in (source / "references").rglob("*"):
                if file.is_file():
                    with self.subTest(resource=file.relative_to(source)):
                        self.assertEqual(file.read_bytes(), (installed / file.relative_to(source)).read_bytes())

    def test_existing_installer_delivers_resources_in_both_layouts(self):
        self.source_fixture()
        self.assertEqual(self.sync().returncode, 0)
        # The normal installer expects all of its configured files; create synthetic stand-ins.
        for runtime in ddl_setup.RUNTIMES.values():
            for rel, source in runtime["links"].items():
                path = self.repo / source
                if rel.startswith("skills/"):
                    path.mkdir(parents=True, exist_ok=True)
                    (path / "SKILL.md").touch(exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch(exist_ok=True)
            fragment = self.repo / runtime["fragment"]
            fragment.parent.mkdir(parents=True, exist_ok=True)
            fragment.write_text(json.dumps({"hooks": {}}))
            (self.repo / runtime["project_src"] / "README.md").write_text("top-level README\n")
        (self.repo / "claude-code/skills/draft/README.md").write_text("unrelated README\n")
        home = self.base / "home"
        home.mkdir()
        project = self.base / "project"
        project.mkdir()
        custom = project / ".claude/skills/ddl-protocol/references/user-note.md"
        custom.parent.mkdir(parents=True)
        custom.write_text("keep this\n")
        args = type("Args", (), {"project": None, "claude": True, "codex": True})()
        with mock.patch.object(ddl_setup, "ROOT", self.repo), mock.patch.dict(os.environ, {"HOME": str(home)}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ddl_setup.cmd_install(args, ddl_setup.Report()), 0)
            for runtime, directory in (("claude", ".claude"), ("codex", ".codex")):
                installed = home / directory / "skills/ddl-protocol/references"
                self.assertEqual((installed / "nested/procedure.md").read_text(), "# Part\n[Intro](../intro.md)\n")
                self.assertEqual((installed / "nested/data.bin").read_bytes(), b"\x00\xff\n")
            args.project = str(project)
            self.assertEqual(ddl_setup.cmd_install(args, ddl_setup.Report()), 0)
            self.assertEqual(ddl_setup.cmd_install(args, ddl_setup.Report()), 0)
            for bundle in (project / ".claude/skills/ddl-protocol", project / ".agents/skills/ddl-protocol"):
                self.assertEqual((bundle / "references/nested/procedure.md").read_text(), "# Part\n[Intro](../intro.md)\n")
                self.assertEqual((bundle / "references/nested/data.bin").read_bytes(), b"\x00\xff\n")
            self.assertFalse((project / ".claude/README.md").exists())
            self.assertFalse((project / ".claude/skills/draft/README.md").exists())
            self.assertEqual(custom.read_text(), "keep this\n")
            args.project = None
            self.assertEqual(ddl_setup.cmd_uninstall(args, ddl_setup.Report()), 0)
            self.assertFalse((home / ".claude/skills/ddl-protocol").exists())
            self.assertFalse((home / ".codex/skills/ddl-protocol").exists())

    def test_command_checks_reject_missing_or_misplaced_structure(self):
        template = self.repo / "claude-code/skills/ddl-protocol/references/command-authoring.md"
        template.parent.mkdir(parents=True)
        bootstrap = ("A command run from a user-level install follows the project copy.\n"
                     "1. Read the DDL protocol.\n"
                     "2. Read project-local runtime guidance.\n")
        template.write_text(bootstrap)
        swarm_one = "+++SWARM: 2+ units\n\n```\n  team: first\n  spawn: reader\n  each: work\n```\n"
        swarm_two = "+++SWARM: 2+ units\n\n```\n  team: second\n  spawn: writer\n  each: work\n```\n"
        command = ("### Phase 0: INIT\n" + bootstrap + "### Phase 1: WORK\n" + swarm_one + swarm_two +
                   "+++DETECT:\n  D1: Example — condition\n### Phase 2: REPORT\n+++STOP: always\n"
                   "+++Report:\n+++NEVER: Skip a STOP\n")
        for directory in ("claude-code/skills", "codex/.agents/skills"):
            for name in COMMANDS:
                file = self.repo / directory / name / "SKILL.md"
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(command)
        for relative, heading, prefix in (("claude-code/CLAUDE.md", "Commands", "/"),
                                          ("codex/AGENTS.md", "Skills", "$"),
                                          (".claude/CLAUDE.md", "Commands", "/")):
            file = self.repo / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("## " + heading + "\n" + "".join(f"| `{prefix}{name}` | test |\n" for name in COMMANDS))
        changed = self.repo / "claude-code/skills/draft/SKILL.md"
        guide = self.repo / "claude-code/CLAUDE.md"
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assertEqual(check_ddl.check_commands(), [])
            template.write_text(bootstrap.replace("1. Read the DDL protocol.\n", ""))
            self.assertTrue(any("authoring template" in e for e in check_ddl.check_commands()))
            template.write_text(bootstrap)
            row = "| `/draft` | test |\n"
            original = guide.read_text()
            guide.write_text(original.replace(row, row + row))
            self.assertTrue(any("command table needs one draft" in e for e in check_ddl.check_commands()))
            guide.write_text(original)
            changed.write_text(command.replace("### Phase 2: REPORT\n+++STOP: always", "+++STOP: always\n### Phase 2: REPORT"))
            self.assertTrue(any("REPORT must contain its own STOP" in e for e in check_ddl.check_commands()))
            changed.write_text(command.replace("  team: first\n", "", 1).replace("  team: second\n", "  team: second\n  team: extra\n", 1))
            errors = check_ddl.check_commands()
            self.assertTrue(any("SWARM needs one team, got 0" in e for e in errors), errors)
            self.assertTrue(any("SWARM needs one team, got 2" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
