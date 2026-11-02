#!/usr/bin/env python3
"""Check protocol resource generation, local links and installation using temporary fixtures.

Link checks cover ordinary inline Markdown links, not all Markdown syntax; a `#fragment`
must name a heading of the target file by its GitHub slug (P12). The protocol checks
run against a minimal conforming fixture and seven mutations of it (negative tests), so
each check is shown to fail on the unit it counts. Installation checks exercise the
existing installer with disposable homes and projects; they do not claim that either
host loaded a skill, trusted a hook or displayed a native UI.
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


def github_slug(heading):
    """The GitHub anchor of a heading: lowercase, punctuation dropped except `-` and `_`, spaces to `-`."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(path):
    """The anchors of a Markdown file: the slugs of its headings outside fences, duplicates suffixed."""
    seen, result = {}, set()
    for line in check_ddl.visible_lines(path.read_text(encoding="utf-8")):
        heading = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not heading:
            continue
        slug = github_slug(heading[1])
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def local_link_errors(bundle):
    """Validate local links, their anchors and reachability of Markdown resources from the entry point."""
    errors = []
    root = bundle.resolve()
    documents = [bundle / "SKILL.md"]
    references = bundle / "references"
    if references.is_dir():
        documents.extend(sorted(references.rglob("*.md")))
    graph = {}
    known_anchors = {}

    def anchor_missing(path, fragment):
        if path.suffix != ".md":
            return False
        if path not in known_anchors:
            known_anchors[path] = anchors(path)
        return fragment not in known_anchors[path]

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
                token = opening.group(1)
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
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
                if target.scheme or target.netloc or target.path.startswith("/"):
                    continue
                if not target.path:
                    # A bare #fragment refers to a heading of the same file.
                    if target.fragment and anchor_missing(resolved_document, unquote(target.fragment)):
                        errors.append(f"missing anchor: {document}:{number}: {link}")
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
                    if target.fragment and anchor_missing(path, unquote(target.fragment)):
                        errors.append(f"missing anchor: {document}:{number}: {link}")
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


# A minimal conforming protocol fixture: the shapes the checker counts, filled from short dictionaries.

BOOTSTRAP = ("A command run from a user-level install follows the project copy.\n"
             "1. Read the DDL protocol.\n"
             "2. Read project-local runtime guidance.\n")
SWARM_ONE = ("+++SWARM: 2+ units\n\n```\n  team: first\n  spawn: reader\n  type: Explore\n  max: 5\n"
             "  batch: auto\n  each: work\n```\n")
SWARM_TWO = "+++SWARM: 2+ units\n\n```\n  team: second\n  spawn: writer\n  type: general-purpose\n  each: work\n```\n"
PHASES = ("### Phase 0: INIT\n" + BOOTSTRAP + "### Phase 1: WORK\n" + SWARM_ONE + SWARM_TWO +
          "+++DETECT:\n  D1: Example — condition\n### Phase 2: REPORT\n+++STOP: always\n+++Report:\n"
          "### Phase 3: EXECUTE\n**Pre-condition.** Actual approval of the scope.\n")
COMMAND = PHASES + "+++NEVER: Skip a STOP\nMark the gate `passed <date>` in design.md.\n"
TEMPLATE = ("---\nname: command-name\ndescription: One-line intent\nargument-hint: \"[arg]\"\n"
            "disable-model-invocation: true\nmetadata:\n  short-description: Short name\n---\n\n"
            "# command-name\n\nIntent line.\n\n## Usage\n\n- `/command-name` — run\n\n## Phases\n\n" + PHASES +
            "\n## Constraints\n\n+++NEVER: Skip a STOP\n")
GUIDES = (("claude-code/CLAUDE.md", "Commands", "/"), ("codex/AGENTS.md", "Skills", "$"), (".claude/CLAUDE.md", "Commands", "/"))


def md_table(header, rows):
    line = lambda cells: "| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |"  # noqa: E731
    return "\n".join([line(header), "|" + "---|" * len(header)] + [line(row) for row in rows])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_commands(repo, command=COMMAND):
    """The 16 command files and the 3 guides, as the command checks expect them."""
    for directory in ("claude-code/skills", "codex/.agents/skills"):
        for name in COMMANDS:
            write(repo / directory / name / "SKILL.md", command)
    for relative, heading, prefix in GUIDES:
        write(repo / relative, "## " + heading + "\n" + "".join(f"| `{prefix}{name}` | test |\n" for name in COMMANDS))


def write_authoring(repo, template=TEMPLATE, sections=None):
    """command-authoring.md with the template fence under ## Example (other sections optional)."""
    example = "````markdown\n" + template + "````"
    text = (sections or "# Authoring a DDL command\n\n## Example\n\n{example}\n").replace("{example}", example)
    write(repo / "claude-code/skills/ddl-protocol/references/command-authoring.md", text)


def reference_text(title, syntax, fields, procedure, formats, example, boundaries, runtime):
    """A shared reference with the eight sections; syntax and example are given already fenced."""
    out = [f"# {title}", "", "## Read when", "", "Read this before the step it covers.", "", "## Syntax", "",
           syntax or "None.", "", "## Fields", "", md_table(*fields) if fields else "None.", "", "## Procedure", ""]
    out += [f"{i}. {step}" for i, step in enumerate(procedure, 1)]
    out += ["", "## Formats", ""] + [f"- `{literal}`" for literal in formats]
    out += ["", "## Example", "", example, "", "## Boundaries", "",
            md_table(("Situation", "Behavior"), [(s, "Behavior.") for s in boundaries]), "", "## Runtime", "", runtime, ""]
    return "\n".join(out)


def host_text(name):
    host, _, operation = name.partition("-")
    if operation != "start":
        read_when = f"Read after [the procedure](../{check_ddl.HOST_SHARED[operation]})."
    else:
        read_when = "Read after [the notebook](../notebook.md), then " + ", ".join(
            f"[{op}]({host}-{op}.md)" for op in check_ddl.HOST_SHARED) + "."
    mapping = md_table(("Concern", "Procedure"), [(concern, "The host tool.") for concern in check_ddl.CONCERNS[name]])
    observed = md_table(("Fact", "Version", "Date"), [("An observed fact", "Host 1.0", "2026-11-01")])
    return (f"# {host}: {operation}\n\n## Read when\n\n{read_when}\n\n## Mapping\n\n{mapping}\n\n"
            f"## Observed\n\n{observed}\n\n## Coverage\n\n- The hook checks dispatched calls only.\n"
            "- Internal errors warn and fail open.\n")


ENTRY = ("---\nname: ddl-protocol\ndescription: test\n---\n\n# DDL protocol\n\n## Start\n\n"
         "1. Follow the project copy.\n2. Resolve links relative to the selected protocol.\n"
         "3. Identify the host and read [Claude Code](references/runtimes/claude-start.md) or [Codex](references/runtimes/codex-start.md).\n"
         "4. Read design.md when it is not in context.\n\n## Instruction set\n\nCommands are programs.\n\n"
         + md_table(("Directive", "Syntax", "Count", "Placement", "Rule"),
                    [(f"`{d}`", f"`{s}`", c, p, "Rule.") for d, s, c, p in (
                        ("# header", "# name", "1", "command file"), ("## Usage", "## Usage", "1", "command file"),
                        ("### Phase", "### Phase N: NAME", "3+", "command file"),
                        ("+++DETECT", "+++DETECT:", "1+", "phase body"), ("+++STOP", "+++STOP: always", "1+", "phase body"),
                        ("+++SWARM", "+++SWARM: <condition>", "0+", "phase body"),
                        ("+++NEVER", "+++NEVER: <rule>", "1+", "command file"), ("+++Report", "+++Report:", "0–1", "phase body"),
                        ("+++DDL_PHASE", "+++DDL_PHASE: <PhaseName>", "0+", "runtime output"),
                        ("+++DDL_REPORT", "+++DDL_REPORT", "0+", "runtime output"))])
         + "\n\n- Markdown headings mark structure.\n- `+++` lines are executable instructions.\n"
         "- The fenced block after `+++SWARM:` holds operands.\n\n## Pending STOP\n\nNo mutation while a STOP is pending.\n\n"
         "## Reading map\n\n"
         + md_table(("Before", "Read"), [(f"a {name}", f"[{name}](references/{name}.md)") for name in check_ddl.REFERENCES])
         + "\n\n## Interruption\n\nReconstruct state from the notebook.\n")

SWARM_SYNTAX = ("````\n+++SWARM: 2+ scopes in design.md\n\n```\n  team: command-phase\n  spawn: role-{scope}\n"
                "  type: Explore\n  max: 5\n  batch: auto\n  each: |\n    Work on {scope}.\n  collect: synthesize\n```\n````")
GIT_JSON = ('```json\n{"language": "en", "operations": [\n'
            '  {"cwd": "/repo", "command": ["git", "commit", "--cleanup=verbatim", "-m", "Message"]},\n'
            '  {"cwd": "/repo", "command": ["git", "push", "origin", "main"]}\n]}\n```')
REFERENCE_FIXTURES = {
    "approval": dict(
        title="Approval at a STOP", syntax="```\n+++STOP: always\n+++STOP: on D<n>\n+++DDL_REPORT\n```",
        fields=(("Form", "Fires when"), [("`always`", "REPORT"), ("`on D<n>`", "the detection fires"),
                                         ("design.md human gate", "the stage ends")]),
        procedure=["**Present:** emit `+++DDL_REPORT`.", "**Ask:** one native choice.", "**Wait and resume:** wait."],
        example="```\n+++DDL_REPORT\nDecision: D1\nChoices: approve all / subset / hold\n```",
        runtime="Read [Claude Code](runtimes/claude-approval.md) or [Codex](runtimes/codex-approval.md)."),
    "close": dict(
        title="Close", syntax=None,
        fields=(("Command", "Authority for steps 1–3", "Git review"),
                [("`/realize`", "the approved plan", "one review"), ("`/commit`", "one batch approval", "one review")]),
        procedure=["**Reflect:** add Experience.", "**Docs:** fix references.", "**Resonate:** update counterparts.",
                   "**Validate:** run the Validation block.", "**Git review:** stage the whole set."],
        example="```\n| Close | reflect, docs, resonate, validate, Git review | final diff | Git review |\n```",
        runtime="Read [Claude Code](runtimes/claude-git.md) or [Codex](runtimes/codex-git.md)."),
    "git-review": dict(
        title="Content-bound Git review", syntax="```\npython3 <gate> prepare-git-review --runtime <host>\n```",
        fields=(("Operation", "Supported forms", "Unsupported forms"),
                [("`commit`", "named branch", "forced"), ("`push`", "one remote", "mirror")]),
        procedure=["**Prepare:** stage.", "**Review:** emit the report.", "**Wait:** for the submission.",
                   "**Keep the reviewed index intact:** any change needs a new review."],
        example=GIT_JSON,
        runtime="Read [Claude Code](runtimes/claude-git.md) or [Codex](runtimes/codex-git.md)."),
    "parallel-work": dict(
        title="Parallel work", syntax=SWARM_SYNTAX,
        fields=(("Field", "Position", "Required", "Default", "Meaning"),
                [(f"`{f}`", "block", "no", "-", "Meaning.") for f in check_ddl.FIELDS_ROWS["parallel-work"]]),
        procedure=[f"**{s}**" for s in check_ddl.PROCEDURE_STEPS["parallel-work"]],
        example="```\n+++SWARM: 2+ scopes in design.md\n```",
        runtime="Read [Claude Code](runtimes/claude-parallel.md) or [Codex](runtimes/codex-parallel.md)."),
    "notebook": dict(
        title="The shared notebook", syntax=None,
        fields=(("Section", "Holds", "Written by", "Read by"),
                [(f"`{s}`", "content", "/draft", "every command") for s in check_ddl.FIELDS_ROWS["notebook"]]),
        procedure=["Binding Decisions.", "Direction.", "Acceptance Gates.", "Passed marks.", "Aligned checks."],
        example=md_table(("Stage", "Work (parallel lanes)", "Human sees", "Gate"), [("S0", "work", "diff", "approval")]),
        runtime="Read [Claude Code](runtimes/claude-start.md) or [Codex](runtimes/codex-start.md)."),
    "command-authoring": dict(
        title="Authoring a DDL command", syntax="```\n### Phase N: NAME\n+++DETECT:\n  D1: name — trigger\n```",
        fields=(("Role", "Phase name", "Required"),
                [(r, "domain name", "yes") for r in ("INIT", "SURVEY/READ", "WORK/IMPLEMENT", "REPORT", "EXECUTE", "VERIFY")]),
        procedure=["Copy the template.", "Keep the shared Phase 0 lines verbatim.", "Define phases.", "Run the checker."],
        example="{example}",
        runtime="Read [Claude Code](runtimes/claude-start.md) or [Codex](runtimes/codex-start.md)."),
}


def write_protocol_fixture(repo):
    """The entry, six references, eight host files, 16 commands and 3 guides that pass every check."""
    bundle = repo / "claude-code/skills/ddl-protocol"
    write(bundle / "SKILL.md", ENTRY)
    for name, spec in REFERENCE_FIXTURES.items():
        text = reference_text(formats=check_ddl.FORMATS[name], boundaries=check_ddl.BOUNDARIES[name], **spec)
        if name == "command-authoring":
            write_authoring(repo, sections=text)
        else:
            write(bundle / "references" / f"{name}.md", text)
    for name in check_ddl.HOSTS:
        write(bundle / "references/runtimes" / f"{name}.md", host_text(name))
    write_commands(repo)
    return bundle


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
        write_authoring(self.repo)
        write_commands(self.repo)
        template = self.repo / "claude-code/skills/ddl-protocol/references/command-authoring.md"
        changed = self.repo / "claude-code/skills/draft/SKILL.md"
        guide = self.repo / "claude-code/CLAUDE.md"
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assertEqual(check_ddl.check_commands(), [])
            write_authoring(self.repo, TEMPLATE.replace("1. Read the DDL protocol.\n", ""))
            self.assertTrue(any("authoring template" in e for e in check_ddl.check_commands()))
            template.write_text("# Authoring\n\n## Example\n\nNo fence.\n")
            self.assertTrue(any("authoring template" in e for e in check_ddl.check_commands()))
            write_authoring(self.repo)
            row = "| `/draft` | test |\n"
            original = guide.read_text()
            guide.write_text(original.replace(row, row + row))
            self.assertTrue(any("command table needs one draft" in e for e in check_ddl.check_commands()))
            guide.write_text(original)
            changed.write_text(COMMAND.replace("### Phase 2: REPORT\n+++STOP: always", "+++STOP: always\n### Phase 2: REPORT"))
            self.assertTrue(any("REPORT must contain its own STOP" in e for e in check_ddl.check_commands()))
            changed.write_text(COMMAND.replace("  team: first\n", "", 1).replace("  team: second\n", "  team: second\n  team: extra\n", 1))
            errors = check_ddl.check_commands()
            self.assertTrue(any("SWARM needs one team, got 0" in e for e in errors), errors)
            self.assertTrue(any("SWARM needs one team, got 2" in e for e in errors), errors)
            changed.write_text(COMMAND.replace("1. Read the DDL protocol.", "1. Read the DDL protocol first."))
            self.assertTrue(any("INIT rule missing, duplicated or different" in e for e in check_ddl.check_commands()))

    # Protocol checks: the positive case, then one mutation per negative test (spec section 4).

    def mutate(self, path, old, new):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def assert_check(self, errors, ident, *fragments):
        hits = [e for e in errors if e.startswith(ident + ":")]
        self.assertTrue(hits, errors)
        for fragment in fragments:
            self.assertTrue(any(fragment in e for e in hits), hits)

    def test_protocol_fixture_passes_protocol_and_command_checks(self):
        write_protocol_fixture(self.repo)
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assertEqual(check_ddl.check_protocol(), [])
            self.assertEqual(check_ddl.check_commands(), [])

    def test_p1_rejects_name_only_instruction_rows(self):
        entry = write_protocol_fixture(self.repo) / "SKILL.md"
        text = entry.read_text(encoding="utf-8")
        start = text.index("| Directive |")
        end = text.index("\n\n", start)
        rows = "".join(f"| `{directive}` |\n" for directive in check_ddl.DIRECTIVES)
        entry.write_text(text[:start] + "| Directive |\n|---|\n" + rows.rstrip("\n") + text[end:], encoding="utf-8")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_protocol(), "P1", "Instruction set")

    def test_p11_rejects_detection_lines_without_detect_header(self):
        write_protocol_fixture(self.repo)
        self.mutate(self.repo / "claude-code/skills/draft/SKILL.md", "+++DETECT:\n", "")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_commands(), "P11", "+++DETECT:")

    def test_p11_rejects_invalid_swarm_max_and_batch(self):
        write_protocol_fixture(self.repo)
        self.mutate(self.repo / "claude-code/skills/draft/SKILL.md", "  max: 5\n  batch: auto\n", "  max: many\n  batch: later\n")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_commands(), "P11", "max must be a positive integer, got 'many'",
                              "batch must be auto or none, got 'later'")

    def test_p12_rejects_missing_anchor(self):
        refs = self.source_fixture()
        bundle = refs.parent
        intro = refs / "intro.md"
        intro.write_text("# Intro\n\n## Phase 0: INIT\n\n[Same file](#phase-0-init) [Other](nested/procedure.md#part)\n"
                         "```markdown\n## Not a heading\n```\n")
        self.assertEqual(local_link_errors(bundle), [])
        intro.write_text("# Intro\n[Other](nested/procedure.md#missing) [Same file](#not-a-heading)\n```markdown\n## Not a heading\n```\n")
        errors = local_link_errors(bundle)
        self.assertEqual(len([e for e in errors if "missing anchor" in e]), 2, errors)

    def test_p4_rejects_undefined_passed_mark_used_by_realize(self):
        bundle = write_protocol_fixture(self.repo)
        self.mutate(bundle / "references/notebook.md", "- `passed <date>`\n", "")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_protocol(), "P4", "/realize writes 'passed <date>'")

    def test_p2_rejects_missing_schema_heading(self):
        bundle = write_protocol_fixture(self.repo)
        self.mutate(bundle / "references/approval.md", "## Formats\n", "")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_protocol(), "P2", "approval.md: H2 headings")

    def test_p9_rejects_blank_observed_date(self):
        bundle = write_protocol_fixture(self.repo)
        self.mutate(bundle / "references/runtimes/claude-approval.md", "| 2026-11-01 |", "|  |")
        with mock.patch.object(check_ddl, "ROOT", self.repo):
            self.assert_check(check_ddl.check_protocol(), "P9", "claude-approval.md: Observed row 1 needs a YYYY-MM-DD Date")


if __name__ == "__main__":
    unittest.main()
