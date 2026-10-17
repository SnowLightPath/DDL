#!/usr/bin/env python3
"""Generate the DDL command mirrors from the production commands.

Production lives in `.claude/commands/` (ignored by git; this tool is for the DDL
maintainer's working copy). Generated files:

  claude   examples/claude-commands/{DDL-PROTOCOL-SKILL,draft,realize,reflect,validate,commit,docs,refactoring}.md
           generic template: production with the DDL-only parts removed
  codex    examples/codex-skills/.agents/skills/<command>/SKILL.md for the same seven commands
           generic template: Codex wording, DDL-only parts removed
  dogfood  .agents/skills/<command>/SKILL.md for the seven commands plus resonate
           this repository's own Codex copy, DDL-only parts kept
           AGENTS.md, .codex/config.toml, .codex/agents/explorer.toml, .codex/agents/worker.toml
           copied from examples/codex-skills/ with the title changed and a $resonate row added

Hand-maintained, never generated: both CLAUDE.md files, the READMEs, and
examples/codex-skills/AGENTS.md and examples/codex-skills/.codex/.

Mirror rules:
  - DDL-only parts: resonate, and reflect's "/resonate" suggestion, which becomes a generic one.
  - Codex wording: YAML frontmatter, /cmd -> $cmd, Phase 0 reads AGENTS.md and the command overlay,
    and protocol references become AGENTS.md section names.

Rules production must follow, or generation stops with an error:
  - every text replaced below occurs exactly once;
  - Phase 0 starts with "1. Read the DDL protocol" and "2. Read project-local runtime guidance";
  - commands cite the protocol only as "(§1.5)", "§1.5 of the protocol", "(§2.3 of the protocol)",
    or "protocol §3".

Usage:
  python3 tools/sync_mirrors.py [REPO] [--out DIR] [--check] [claude|codex|dogfood ...]

--out DIR writes the files that differ from REPO under DIR instead of REPO (dry run).
--check writes nothing, prints a unified diff against the files in REPO, and exits 1 when any file differs.
On success the last stderr line is "N generated, M differ". An error exits 1 with a message instead.
"""
import difflib
import pathlib
import re
import sys

COMMANDS = ["draft", "realize", "reflect", "validate", "commit", "docs", "refactoring"]
CLAUDE_FILES = ["DDL-PROTOCOL-SKILL"] + COMMANDS
DOGFOOD_EXTRA = ["resonate"]
TARGETS = ("claude", "codex", "dogfood")
CODEX_TEMPLATE = pathlib.Path("examples/codex-skills")
CODEX_RUNTIME_FILES = ["AGENTS.md", ".codex/config.toml", ".codex/agents/explorer.toml", ".codex/agents/worker.toml"]

FRONTMATTER = {
    "draft": ("Write the ideal experience before implementation exists, with the technology decisions and outlook it depends on",
              "Draft ideal experience"),
    "realize": ("Write code based on design principles and Binding Decisions in design.md", "Design to Code"),
    "reflect": ("Update documents based on implementation results", "Code to Design"),
    "validate": ("Run mechanical validation per scope as declared in design.md", "Mechanical validation gate"),
    "commit": ("Record verified code changes to the repository", "Verified git commit"),
    "docs": ("Audit and fix documentation quality", "Documentation audit"),
    "refactoring": ("Audit and fix code quality issues", "Code quality audit"),
    "resonate": ("Synchronize English and Japanese versions of the documentation", "Sync en/ja docs"),
}


def replace_once(text, old, new, name):
    if text.count(old) != 1:
        raise SystemExit(f"{name}: expected exactly one occurrence of {old[:60]!r}, found {text.count(old)}")
    return text.replace(old, new)


def strip_production_only(name, text):
    """Remove DDL-repo-only parts for the generic templates."""
    if name == "reflect":
        text = replace_once(text, '2. Suggest: "Run `/resonate` to sync translations" (if multilingual docs exist)',
                            "2. Suggest next command if applicable", name)
    return text


PHASE0 = re.compile(r"(### Phase 0: INIT\n\n)(.*?)(\n\n### )", re.S)


def codex_phase0(name, text):
    m = PHASE0.search(text)
    if not m:
        raise SystemExit(f"{name}: Phase 0 block not found")
    steps = [line for line in m.group(2).split("\n") if line.strip()]
    if not (steps[0].startswith("1. Read the DDL protocol") and steps[1].startswith("2. Read project-local runtime guidance")):
        raise SystemExit(f"{name}: unexpected Phase 0 steps")
    rest = [re.sub(r"^\d+\. ", "", s) for s in steps[2:]]
    new = ["1. Read `AGENTS.md` — Directive Reference, Codex Runtime Contract, +++SWARM Execution, and design.md Sections"
           " — and any applicable command overlay (`commands/<name>.md`)"]
    new += [f"{i}. {s}" for i, s in enumerate(rest, start=2)]
    return text[:m.start(2)] + "\n".join(new) + text[m.end(2):]


SLASH = re.compile(r"(?<![A-Za-z0-9_./-])/(draft|realize|reflect|validate|commit|docs|refactoring|resonate)\b")


def to_codex(name, text, keep_production_only):
    if not keep_production_only:
        text = strip_production_only(name, text)
    text = codex_phase0(name, text)
    text = text.replace("per §1.5 of the protocol", "per the Codex Runtime Contract in `AGENTS.md`")
    text = text.replace("§1.5 of the protocol", "the Codex Runtime Contract in `AGENTS.md`")
    text = text.replace("(§1.5)", "(Codex Runtime Contract in `AGENTS.md`)")
    text = text.replace("(§2.3 of the protocol)", "(+++SWARM Execution in `AGENTS.md`)")
    text = text.replace("the sections of protocol §3", "the sections listed in design.md Sections of `AGENTS.md`")
    text = text.replace("onto protocol §3", "onto the sections listed in design.md Sections of `AGENTS.md`")
    text = text.replace("protocol §3", "design.md Sections in `AGENTS.md`")
    text = SLASH.sub(r"$\1", text)
    if "§" in text:
        raise SystemExit(f"{name}: unmapped protocol reference left: {re.findall(r'.{0,30}§.{0,20}', text)}")
    desc, short = FRONTMATTER[name]
    head = f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  short-description: {short}\n---\n\n"
    return head + text


def dogfood_runtime(name, text):
    """This repository's own Codex adapter, from the template."""
    if name == "AGENTS.md":
        text = replace_once(text, "# Project Name\n", "# DDL Repository\n", name)
        row = "| `$validate` | Run mechanical validation per scope |\n"
        text = replace_once(text, row, row + "| `$resonate` | Sync en/ja docs (this repository only) |\n", name)
    return text


def generate(repo, targets):
    prod = repo / ".claude" / "commands"
    out = {}
    if "claude" in targets:
        for name in CLAUDE_FILES:
            text = (prod / f"{name}.md").read_text()
            out[pathlib.Path("examples/claude-commands") / f"{name}.md"] = strip_production_only(name, text)
    if "codex" in targets:
        for name in COMMANDS:
            text = (prod / f"{name}.md").read_text()
            out[pathlib.Path("examples/codex-skills/.agents/skills") / name / "SKILL.md"] = to_codex(name, text, False)
    if "dogfood" in targets:
        for name in COMMANDS + DOGFOOD_EXTRA:
            text = (prod / f"{name}.md").read_text()
            out[pathlib.Path(".agents/skills") / name / "SKILL.md"] = to_codex(name, text, True)
        for rel in CODEX_RUNTIME_FILES:
            text = (repo / CODEX_TEMPLATE / rel).read_text()
            out[pathlib.Path(rel)] = dogfood_runtime(rel, text)
    return out


def main(argv):
    args = list(argv)
    check = "--check" in args
    if check:
        args.remove("--check")
    out_dir = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            raise SystemExit("--out needs a directory")
        out_dir = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    unknown = [a for a in args if a.startswith("--")]
    if unknown:
        raise SystemExit(f"unknown option: {' '.join(unknown)}")
    repo = pathlib.Path(args.pop(0) if args and args[0] not in TARGETS else ".").resolve()
    if not (repo / ".claude" / "commands").is_dir():
        raise SystemExit(f"{repo}: no .claude/commands/ (not the DDL working copy?)")
    bad = [a for a in args if a not in TARGETS]
    if bad:
        raise SystemExit(f"unknown target: {' '.join(bad)} (choose from {', '.join(TARGETS)})")
    targets = args or list(TARGETS)
    files = generate(repo, targets)
    changed = 0
    for rel, text in sorted(files.items()):
        current = repo / rel
        old = current.read_text() if current.exists() else ""
        if old == text:
            continue
        changed += 1
        if check:
            sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                                       f"a/{rel}", f"b/{rel}"))
        else:
            dest = (out_dir or repo) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
            print(f"wrote {dest}")
    print(f"{len(files)} generated, {changed} differ", file=sys.stderr)
    return 1 if check and changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
