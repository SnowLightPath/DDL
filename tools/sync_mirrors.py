#!/usr/bin/env python3
"""Generate the DDL mirrors from the production skills.

Production lives in `.claude/skills/<name>/SKILL.md` (ignored by git; this tool is for the DDL
maintainer's working copy): the protocol skill `ddl-protocol` and the command skills draft, realize,
reflect, validate, commit, docs, refactoring, and resonate. Generated files:

  claude   examples/claude-commands/.claude/skills/<name>/SKILL.md for ddl-protocol and the seven commands
           generic template: production with the DDL-only parts removed
           examples/claude-commands/.claude/hooks/ddl_gate.py, a copy of tools/ddl_gate.py (the adapter's gate)
  codex    examples/codex-skills/.agents/skills/<command>/SKILL.md for the same seven commands
           generic template: Codex wording, DDL-only parts removed, frontmatter from the Claude frontmatter
           examples/codex-skills/.agents/skills/<command>/agents/openai.yaml (no implicit invocation)
           examples/codex-skills/.codex/hooks/ddl_gate.py, a copy of tools/ddl_gate.py (the Codex adapter's gate)
  dogfood  .agents/skills/<command>/SKILL.md and agents/openai.yaml for the seven commands plus resonate
           this repository's own Codex copy, DDL-only parts kept
           AGENTS.md and the .codex/ adapter files in CODEX_RUNTIME_FILES, copied from examples/codex-skills/
           with the title changed and a $resonate row added
           the .claude/ adapter files in CLAUDE_RUNTIME_FILES, copied from examples/claude-commands/.claude/

Hand-maintained, never generated: both CLAUDE.md files, the READMEs, examples/codex-skills/AGENTS.md,
examples/codex-skills/.codex/ except hooks/ddl_gate.py, the adapter files in examples/claude-commands/.claude/
(settings.json, agents/), and tools/ddl_gate.py, the gate's source: every hooks/ddl_gate.py is a copy of it.

Mirror rules:
  - DDL-only parts: resonate, and reflect's "/resonate" suggestion, which becomes a generic one.
  - Codex wording: the Claude frontmatter (name, description, argument-hint, disable-model-invocation,
    metadata.short-description) becomes a Codex frontmatter (name, description, metadata.short-description)
    plus agents/openai.yaml with allow_implicit_invocation false; /cmd -> $cmd; Phase 0 treats AGENTS.md as
    already in context and reads the command overlay; protocol references become AGENTS.md section names.

Rules production must follow, or generation stops with an error:
  - every command skill starts with a frontmatter that has name (equal to the skill's directory name), description,
    and metadata.short-description;
  - the three texts replaced with replace_once (reflect's /resonate suggestion, the template title,
    the $validate row) occur exactly once, and no § remains after the Codex wording replacements;
  - every command has a "### Phase 0: INIT" block, ended by a blank line and the next "### " heading, whose first
    steps are "1. Read the DDL protocol" and "2. Read project-local runtime guidance";
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
PROTOCOL = "ddl-protocol"
CLAUDE_FILES = [PROTOCOL] + COMMANDS
DOGFOOD_EXTRA = ["resonate"]
TARGETS = ("claude", "codex", "dogfood")
PROD = pathlib.Path(".claude/skills")
CODEX_TEMPLATE = pathlib.Path("examples/codex-skills")
CODEX_RUNTIME_FILES = ["AGENTS.md", ".codex/config.toml", ".codex/agents/explorer.toml", ".codex/agents/worker.toml",
                       ".codex/hooks.json", ".codex/hooks/ddl_gate.py", ".codex/rules/ddl.rules"]
CLAUDE_TEMPLATE = pathlib.Path("examples/claude-commands/.claude")
CLAUDE_RUNTIME_FILES = ["settings.json", "agents/explorer.md", "agents/worker.md", "hooks/ddl_gate.py"]
GATE_SOURCE = pathlib.Path("tools/ddl_gate.py")
GATE_COPY = "hooks/ddl_gate.py"  # the gate's path inside each adapter directory

OPENAI_YAML = ("# DDL: a command skill runs when the user invokes ${name}; Codex does not start it on its own\n"
               "# (AGENTS.md, Codex Runtime Contract).\n"
               "policy:\n"
               "  allow_implicit_invocation: false\n")


def replace_once(text, old, new, name):
    if text.count(old) != 1:
        raise SystemExit(f"{name}: expected exactly one occurrence of {old[:60]!r}, found {text.count(old)}")
    return text.replace(old, new)


def split_frontmatter(name, text):
    """(fields, body). `fields` holds name, description, and short-description; the rest of the frontmatter
    is Claude-only and dropped on the Codex side."""
    m = re.match(r"---\n(.*?)\n---\n\n?", text, re.S)
    if not m:
        raise SystemExit(f"{name}: no frontmatter")
    fields = {}
    for line in m.group(1).split("\n"):
        key, sep, value = line.strip().partition(":")
        if sep and key in ("name", "description", "short-description"):
            fields[key] = value.strip()
    for key in ("name", "description", "short-description"):
        if key not in fields:
            raise SystemExit(f"{name}: frontmatter lacks {key}")
    if fields["name"] != name:
        raise SystemExit(f"{name}: frontmatter name is {fields['name']!r}")
    return fields, text[m.end():]


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
    new = ["1. `AGENTS.md` (Directive Reference, Codex Runtime Contract, +++SWARM Execution, design.md Sections) is in context"
           " from session start; read it only when it is not, and read any applicable command overlay (`commands/<name>.md`)"]
    new += [f"{i}. {s}" for i, s in enumerate(rest, start=2)]
    return text[:m.start(2)] + "\n".join(new) + text[m.end(2):]


SLASH = re.compile(r"(?<![A-Za-z0-9_./-])/(draft|realize|reflect|validate|commit|docs|refactoring|resonate)\b")


def to_codex(name, text, keep_production_only):
    fields, body = split_frontmatter(name, text)
    if not keep_production_only:
        body = strip_production_only(name, body)
    body = codex_phase0(name, body)
    body = body.replace("per §1.5 of the protocol", "per the Codex Runtime Contract in `AGENTS.md`")
    body = body.replace("§1.5 of the protocol", "the Codex Runtime Contract in `AGENTS.md`")
    body = body.replace("(§1.5)", "(Codex Runtime Contract in `AGENTS.md`)")
    body = body.replace("(§2.3 of the protocol)", "(+++SWARM Execution in `AGENTS.md`)")
    body = body.replace("the sections of protocol §3", "the sections listed in design.md Sections of `AGENTS.md`")
    body = body.replace("onto protocol §3", "onto the sections listed in design.md Sections of `AGENTS.md`")
    body = body.replace("protocol §3", "design.md Sections in `AGENTS.md`")
    body = SLASH.sub(r"$\1", body)
    if "§" in body:
        raise SystemExit(f"{name}: unmapped protocol reference left: {re.findall(r'.{0,30}§.{0,20}', body)}")
    head = (f"---\nname: {name}\ndescription: {fields['description']}\nmetadata:\n"
            f"  short-description: {fields['short-description']}\n---\n\n")
    return head + body


def dogfood_runtime(name, text):
    """This repository's own Codex adapter, from the template."""
    if name == "AGENTS.md":
        text = replace_once(text, "# Project Name\n", "# DDL Repository\n", name)
        row = "| `$validate` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |\n"
        text = replace_once(text, row, row + "| `$resonate` | Sync en/ja docs (this repository only) |\n", name)
    return text


def generate(repo, targets):
    prod = repo / PROD
    if not (repo / GATE_SOURCE).is_file():
        raise SystemExit(f"{GATE_SOURCE}: missing (the gate's source, copied into every adapter)")
    gate = (repo / GATE_SOURCE).read_text()
    out = {}

    def skill(name):
        return (prod / name / "SKILL.md").read_text()

    if "claude" in targets:
        for name in CLAUDE_FILES:
            out[CLAUDE_TEMPLATE / "skills" / name / "SKILL.md"] = strip_production_only(name, skill(name))
        out[CLAUDE_TEMPLATE / GATE_COPY] = gate
    if "codex" in targets:
        for name in COMMANDS:
            base = CODEX_TEMPLATE / ".agents/skills" / name
            out[base / "SKILL.md"] = to_codex(name, skill(name), False)
            out[base / "agents" / "openai.yaml"] = OPENAI_YAML.format(name=name)
        out[CODEX_TEMPLATE / ".codex" / GATE_COPY] = gate
    if "dogfood" in targets:
        for name in COMMANDS + DOGFOOD_EXTRA:
            base = pathlib.Path(".agents/skills") / name
            out[base / "SKILL.md"] = to_codex(name, skill(name), True)
            out[base / "agents" / "openai.yaml"] = OPENAI_YAML.format(name=name)
        # The gate copies come straight from the source, so one run is enough even when the
        # template copies do not exist yet.
        for rel in CODEX_RUNTIME_FILES:
            text = gate if rel.endswith(GATE_COPY) else (repo / CODEX_TEMPLATE / rel).read_text()
            out[pathlib.Path(rel)] = dogfood_runtime(rel, text)
        for rel in CLAUDE_RUNTIME_FILES:
            text = gate if rel == GATE_COPY else (repo / CLAUDE_TEMPLATE / rel).read_text()
            out[pathlib.Path(".claude") / rel] = text
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
    if not (repo / PROD).is_dir():
        raise SystemExit(f"{repo}: no {PROD}/ (not the DDL working copy?)")
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
