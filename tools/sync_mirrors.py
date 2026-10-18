#!/usr/bin/env python3
"""Generate the Codex skills and the gate copies from the Claude Code skills.

Source: `claude-code/skills/<name>/SKILL.md`, the single hand-maintained copy of the nine DDL skills: the
protocol `ddl-protocol` and the eight commands draft, realize, reflect, validate, commit, docs, refactoring,
and resonate. `tools/ddl_gate.py` is the gate's source.

Generated files (20):
  codex/.agents/skills/<name>/SKILL.md            for the nine skills
  codex/.agents/skills/<name>/agents/openai.yaml  for the nine skills (no implicit invocation)
  claude-code/hooks/ddl_gate.py                   a byte copy of tools/ddl_gate.py
  codex/.codex/hooks/ddl_gate.py                  a byte copy of tools/ddl_gate.py

Hand-maintained, never generated: claude-code/CLAUDE.md, claude-code/README.md, claude-code/settings.json,
claude-code/agents/, codex/AGENTS.md, codex/README.md, codex/.codex/ except hooks/ddl_gate.py, and
tools/ddl_gate.py.

Rules:
  - A command SKILL.md keeps name, description, and metadata.short-description from the Claude frontmatter and
    drops argument-hint and disable-model-invocation, which Codex does not know (agents/openai.yaml replaces
    the latter). Its body is the Claude body with slash commands turned into skills: `/draft` -> `$draft` for
    the eight command names, not inside paths or words (the SLASH regex). Nothing else changes: § references
    to the protocol stay, because the Codex protocol is the same skill, and Phase 0 stays as written.
  - The protocol SKILL.md keeps name and description (and metadata.short-description when the source has
    one); its body is copied unchanged, not even `/cmd` -> `$cmd`, since it describes both runtimes.
  - agents/openai.yaml is the same fixed text for every command skill, with the skill's name; the protocol
    gets a comment saying it is read in Phase 0 and never invoked.
  - Both hooks/ddl_gate.py files are byte copies of tools/ddl_gate.py.

Errors (exit 1 with a message): REPO/claude-code/skills is not a directory; tools/ddl_gate.py or a skill is
missing; a skill has no frontmatter, a frontmatter name different from its directory name, or no description;
a command has no metadata.short-description.

Usage:
  python3 tools/sync_mirrors.py [REPO] [--out DIR] [--check]

REPO defaults to the current directory. --out DIR writes the files that differ under DIR instead of REPO
(dry run). --check writes nothing, prints a unified diff for every file that differs, and exits 1 when any
differs. Unknown options and extra positional arguments are errors. On success the last stderr line is
"N generated, M differ".
"""
import difflib
import pathlib
import re
import sys

COMMANDS = ["draft", "realize", "reflect", "validate", "commit", "docs", "refactoring", "resonate"]
PROTOCOL = "ddl-protocol"
SKILLS = [PROTOCOL] + COMMANDS
SOURCE = pathlib.Path("claude-code/skills")
CODEX_SKILLS = pathlib.Path("codex/.agents/skills")
GATE_SOURCE = pathlib.Path("tools/ddl_gate.py")
GATE_COPIES = [pathlib.Path("claude-code/hooks/ddl_gate.py"), pathlib.Path("codex/.codex/hooks/ddl_gate.py")]

OPENAI_POLICY = ("policy:\n"
                 "  allow_implicit_invocation: false\n")
OPENAI_YAML = ("# DDL: a skill runs when the user invokes ${name}; Codex does not start it on its own (protocol §2.5).\n"
               + OPENAI_POLICY)
OPENAI_YAML_PROTOCOL = ("# DDL: the protocol skill; commands read it in Phase 0, nobody invokes $ddl-protocol, and Codex "
                        "does not start it on its own (protocol §2.5).\n" + OPENAI_POLICY)

SLASH = re.compile(r"(?<![A-Za-z0-9_./-])/(draft|realize|reflect|validate|commit|docs|refactoring|resonate)\b")


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def split_frontmatter(name, text, short_description):
    """(fields, body). `fields` holds name, description, and short-description when present; the rest of the
    frontmatter is Claude-only and dropped on the Codex side. `short_description` says whether it is required."""
    m = re.match(r"---\n(.*?)\n---\n\n?", text, re.S)
    if not m:
        raise SystemExit(f"{name}: no frontmatter")
    fields = {}
    for line in m.group(1).split("\n"):
        key, sep, value = line.strip().partition(":")
        if sep and key in ("name", "description", "short-description"):
            fields[key] = value.strip()
    required = ("name", "description") + (("short-description",) if short_description else ())
    for key in required:
        if key not in fields:
            raise SystemExit(f"{name}: frontmatter lacks {key}")
    if fields["name"] != name:
        raise SystemExit(f"{name}: frontmatter name is {fields['name']!r}")
    return fields, text[m.end():]


def to_codex(name, text):
    """The Codex SKILL.md: Codex frontmatter, then the body with /cmd -> $cmd for a command and unchanged
    for the protocol."""
    fields, body = split_frontmatter(name, text, short_description=name != PROTOCOL)
    if name != PROTOCOL:
        body = SLASH.sub(r"$\1", body)
    head = f"---\nname: {name}\ndescription: {fields['description']}\n"
    if "short-description" in fields:
        head += f"metadata:\n  short-description: {fields['short-description']}\n"
    return head + "---\n\n" + body


def generate(repo):
    if not (repo / GATE_SOURCE).is_file():
        raise SystemExit(f"{GATE_SOURCE}: missing (the gate's source, copied into both adapters)")
    out = {}
    for name in SKILLS:
        source = repo / SOURCE / name / "SKILL.md"
        if not source.is_file():
            raise SystemExit(f"{source.relative_to(repo)}: missing")
        out[CODEX_SKILLS / name / "SKILL.md"] = to_codex(name, read(source))
        yaml = OPENAI_YAML_PROTOCOL if name == PROTOCOL else OPENAI_YAML.format(name=name)
        out[CODEX_SKILLS / name / "agents" / "openai.yaml"] = yaml
    gate = read(repo / GATE_SOURCE)
    for rel in GATE_COPIES:
        out[rel] = gate
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
    if len(args) > 1:
        raise SystemExit(f"unexpected argument: {' '.join(args[1:])} (usage: sync_mirrors.py [REPO] [--out DIR] [--check])")
    repo = pathlib.Path(args[0] if args else ".").resolve()
    if not (repo / SOURCE).is_dir():
        raise SystemExit(f"{repo}: no {SOURCE}/ (not the DDL repository?)")
    files = generate(repo)
    changed = 0
    for rel, text in sorted(files.items()):
        current = repo / rel
        old = read(current) if current.exists() else ""
        if old == text:
            continue
        changed += 1
        if check:
            sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                                       f"a/{rel}", f"b/{rel}"))
        else:
            dest = (out_dir or repo) / rel
            write(dest, text)
            print(f"wrote {dest}")
    print(f"{len(files)} generated, {changed} differ", file=sys.stderr)
    return 1 if check and changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
