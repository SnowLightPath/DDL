#!/usr/bin/env python3
"""Check maintained DDL structure and documentation, without running a model.

The command check validates each phase and operand block, not aggregate word
counts. The protocol check (P1-P14 of the instruction-set specification)
counts the units the protocol must define: sections, table rows, operation
steps, literals, keywords, byte budgets and duplicated sentences; it reads the
maintained text only. The
documentation check preserves the existing language/terminology checks. Model
loading and human choice delivery need separate live tests.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sync_mirrors  # noqa: E402

COMMANDS = ("draft", "realize", "reflect", "validate", "resonate", "commit", "docs", "refactoring")
PROTOCOL = "claude-code/skills/ddl-protocol"
# The six operations live beside the entry; the eight implementations live under hosts/<host>/<operation>.md.
OPERATIONS = ("approval", "close", "command-authoring", "git-review", "notebook", "parallel-work")
HOST_NAMES = ("claude-code", "codex")
HOST_OPERATIONS = ("start", "approval", "parallel-work", "git-review")
IMPLEMENTATIONS = tuple(f"{host}/{operation}" for host in HOST_NAMES for operation in HOST_OPERATIONS)
ENTRY_H2 = ("Start", "Instruction set", "Pending STOP", "Reading map", "Interruption")
OPERATION_H2 = ("Read when", "Syntax", "Operands", "Operation", "Formats", "Example", "Exceptions", "Implementation")
HOST_H2 = ("Read when", "Mapping", "Observed", "Coverage")
READING_MAP_HEADER = "| Operation | Read before | Implementation |"
MAPPING_HEADER = "| Concern | Implementation |"
DIRECTIVES = ("# header", "## Usage", "### Phase", "+++DETECT", "+++STOP", "+++SWARM", "+++NEVER",
              "+++Report", "+++DDL_PHASE", "+++DDL_REPORT")
DIRECTIVE_TOKENS = {"# header": "#", "## Usage": "## Usage", "### Phase": "### Phase"}
SHARED_PREFIXES = ("A command run from a user-level install", "1. Read the DDL protocol",
                   "2. Read the project's guidance file")
SWARM_OPERANDS = ("team", "spawn", "type", "max", "batch", "each", "collect")
REPORT_LABELS = ("Decision:", "Recommendation:", "Consequence:", "Review detail:", "Choices:")
# Host tool and API names: allowed only under hosts/ (P10).
TOOL_NAMES = re.compile(r"\b(AskUserQuestion|request_user_input_async|request_user_input|Agent|SendMessage|TeamCreate|"
                        r"TeamDelete|TaskCreate|TaskList|TaskUpdate|NotebookEdit|apply_patch|subagent_type|agent_type|"
                        r"task_name|fork_turns|run_in_background|multiSelect|afkTimeoutMs)\b")
CHECK_ID = {"parallel-work": "P3", "notebook": "P4", "approval": "P5", "close": "P6",
            "git-review": "P7", "command-authoring": "P8"}
OPERANDS_HEADERS = {
    "approval": "| Form | Fires when |",
    "close": "| Command | Authority for steps 1–3 | Git review |",
    "git-review": "| Git action | Supported forms | Unsupported forms |",
    "parallel-work": "| Operand | Position | Required | Default | Meaning |",
    "notebook": "| Section | Holds | Written by | Read by |",
    "command-authoring": "| Role | Phase name | Required |",
}
OPERANDS_ROWS = {
    "parallel-work": ("condition", "team", "spawn", "type", "max", "batch", "each", "collect"),
    "notebook": ("## Intent", "## Scopes", "## Principles", "## Experience", "## Binding Decisions",
                 "## Direction", "## Acceptance Gates", "## Validation"),
}
OPERATION_STEPS = {
    "parallel-work": ("Create team", "Scale", "Spawn", "Monitor", "Collect", "Shutdown"),
    "close": ("Reflect", "Docs", "Resonate", "Validate", "Git review"),
}
FORMATS = {
    "approval": ("+++DDL_REPORT", *REPORT_LABELS, "Outcome:", "approve all", "subset", "hold",
                 "approved in advance (<date>)"),
    "close": ("nothing remains", "left: <item> — <reason>"),
    "git-review": ("language", "operations", "cwd", "command", "reviewId", "report", "question", "nativeRequest",
                   "G-<id>"),
    "parallel-work": ("{scope}", "{scopes}", "command-phase", "role-{scope}"),
    "notebook": ("| Decision | Why it binds | Source |",
                 "Unbound: <topic> — options A / B (delegated to /realize | awaiting choice)",
                 "| Stage | Work (parallel lanes) | Human sees | Gate |", "Approved plan (<date>)", "passed <date>",
                 "approved in advance (<date>)", "approved in /realize plan (<date>)", "approved /draft report (<date>)"),
    "command-authoring": ("### Phase N: NAME", "+++DETECT:", "D1: name — trigger", "+++STOP: always",
                          "+++STOP: on D<n>", "**Pre-condition.**", "+++Report:", *REPORT_LABELS, "+++NEVER:",
                          "+++DDL_PHASE: <PhaseName>", "+++DDL_REPORT"),
}
# Marks that commands write into design.md; every one a command uses must be defined by notebook.md (P4).
NOTEBOOK_MARKS = ("passed <date>", "approved in advance (<date>)", "Approved plan (<date>)", "approved /draft report (<date>)",
                  "approved in /realize plan (<date>)", "Unbound:")
NOTEBOOK_WRITERS = ("draft", "realize", "reflect", "commit")
EXCEPTIONS = {
    "approval": ("receipt", "timeout", "summary", "worker notification", "another session", "cancel", "no selection",
                 "clarification", "ambiguous", "interface unavailable", "informational", "advance approval",
                 "interrupted"),
    "close": ("Binding Drift", "no change", "no Close", "hold", "no Direction", "commit yourself", "review first",
              "compaction", "validate fails", "argument", "documentation only", "cannot reconstruct"),
    "git-review": ("hold", "revision", "timeout", "receipt", "changed", "resume", "compaction", "unsupported", "alias",
                   "no adapter", "hook failure", "unprovable"),
    "parallel-work": ("0 units", "1 unit", "up to max", "batch: auto", "batch: none", "dependent", "STOP", "failed",
                      "no primitive", "argument"),
    "notebook": ("existing heading", "existing code", "automatic memory", "argument", "output format", "delegated",
                 "no reason", "not version controlled", "other notebook file"),
    "command-authoring": ("project copy", "overlay", "no notebook", "missing file", "tool name",
                          "domain phase name", "read-only report"),
}
START_CONCERNS = ("Session start", "Compaction", "Notebook loading", "Adapter paths", "+++DDL_PHASE", "+++DDL_REPORT")
PARALLEL_CONCERNS = ("Team primitive", "type: Explore", "type: general-purpose", "spawn", "Background", "Completion",
                     "Nesting", "Concurrency", "Fallback")
APPROVAL_CONCERNS = ("Choice tool", "Subset", "Receipt", "Timeout", "Mutating tools", "Human input boundary", "Hook")
GIT_CONCERNS = ("Prepare", "nativeRequest", "Revocation", "Push confirmation", "Attribution")
# Keyed by operation: the same concerns for every host's implementation of it (P9).
CONCERNS = {"start": START_CONCERNS, "parallel-work": PARALLEL_CONCERNS, "approval": APPROVAL_CONCERNS,
            "git-review": GIT_CONCERNS}
# Reading budgets in UTF-8 bytes (P13): each path adds its files to the previous one and is counted per host;
# file names are paths under the skill directory with {host} filled in.
BUDGET_PATHS = (
    ("validate", 20000, ("SKILL.md", "hosts/{host}/start.md", "approval.md", "hosts/{host}/approval.md")),
    ("draft", 29000, ("notebook.md",)),
    ("realize-plan", 38000, ("parallel-work.md", "hosts/{host}/parallel-work.md")),
    ("realize-close", 52000, ("close.md", "git-review.md", "hosts/{host}/git-review.md")),
)
EXECUTION_LIMIT = 62000
AUTHOR_ONLY = ("command-authoring",)  # operations read by authors only: outside the execution total
INLINE_CODE = re.compile(r"`+[^`\n]*`+")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def protocol_path(name):
    """The repository path of a protocol file named relative to the skill directory."""
    return f"{PROTOCOL}/{name}"


def protocol_files():
    """Every maintained protocol file: the entry, the six operations and the eight implementations (P10, P14)."""
    files = [f"{PROTOCOL}/SKILL.md"] + [f"{PROTOCOL}/{n}.md" for n in OPERATIONS]
    return files + [f"{PROTOCOL}/hosts/{n}.md" for n in IMPLEMENTATIONS]


def byte_size(relative):
    """The size of a file in bytes, or None when it is missing (reported by P1, P2 or P9)."""
    try:
        return (ROOT / relative).stat().st_size
    except OSError:
        return None


def visible_lines(text):
    """Ignore fenced examples when finding executable phase/report markers."""
    fence = None
    result = []
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append("")
        else:
            result.append(line if fence is None else "")
    return result


# Markdown units: H2 sections, tables, numbered steps, bullets, fences, links.

def h2_sections(text):
    """([titles], {title: raw body lines}) for the H2 headings outside fences."""
    titles, bodies, current = [], {}, []
    for raw, seen in zip(text.splitlines(), visible_lines(text)):
        heading = re.match(r"^## (.+?)\s*$", seen)
        if heading:
            titles.append(heading[1])
            current = bodies.setdefault(heading[1], [])
        else:
            current.append(raw)
    return titles, bodies


def cells(row):
    """The cells of a table row, escaped pipes restored."""
    inner = re.sub(r"^\s*\|", "", row.strip())
    inner = re.sub(r"(?<!\\)\|\s*$", "", inner)
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", inner)]


def table(lines):
    """(header cells, body rows as cell lists) of the first table outside fences, or None."""
    seen = visible_lines("\n".join(lines))
    start = next((i for i, line in enumerate(seen) if line.startswith("|")), None)
    if start is None or start + 1 >= len(seen) or not re.match(r"^\|\s*:?-", seen[start + 1]):
        return None
    rows = []
    for line in seen[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append(cells(line))
    return cells(seen[start]), rows


def header_text(header):
    return "| " + " | ".join(header) + " |"


def plain(cell):
    """A cell without code-span backticks."""
    return cell.replace("`", "").strip()


def link_text(cell):
    """A cell with every inline link reduced to its text and backticks removed."""
    return plain(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell))


def section_text(lines):
    """The raw text of a section with table pipe escapes removed, for literal searches."""
    return "\n".join(lines).replace("\\|", "|")


def is_none(lines):
    return [line.strip() for line in lines if line.strip()] == ["None."]


def steps(lines):
    """The top-level numbered items of a section, outside fences."""
    return [m[1] for line in visible_lines("\n".join(lines)) if (m := re.match(r"^\d+\. (.*)", line))]


def bold_steps(lines):
    return re.findall(r"(?m)^\d+\. \*\*([^*:]+):?\*\*", "\n".join(visible_lines("\n".join(lines))))


def bullets(lines):
    return [line for line in visible_lines("\n".join(lines)) if re.match(r"^[-*] ", line)]


def fenced_blocks(lines):
    """[(fence token, info string, content lines)] for the top-level fences of a section."""
    blocks, fence = [], None
    for line in lines:
        marker = re.match(r"^\s*(`{3,}|~{3,})\s*(.*)$", line)
        if marker and fence is None:
            fence = marker[1]
            blocks.append((fence, marker[2].strip(), []))
        elif marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
            fence = None
        elif fence is not None:
            blocks[-1][2].append(line)
    return blocks


def links(text):
    """The targets of inline Markdown links outside code spans."""
    return re.findall(r"\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)", INLINE_CODE.sub("", text))


def local_targets(text, directory):
    """The resolved files (fragments dropped) that the local links in text point to."""
    targets = set()
    for link in links(text):
        path = link.split("#")[0]
        if not path or path.startswith("/") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
            continue
        targets.add((directory / path).resolve())
    return targets


def keyword_errors(ident, label, section, column, keywords):
    lower = [cell.lower() for cell in column]
    return [f"{ident}: {label}: {section} needs a row whose first cell mentions {k!r}"
            for k in keywords if not any(k.lower() in cell for cell in lower)]


def literal_errors(ident, label, section, text, literals):
    return [f"{ident}: {label}: {section} must contain {lit!r}" for lit in literals if lit not in text]


def operands_rows(ident, label, bodies, errors):
    """The Operands rows after the header check (None when the table is missing or wrongly headed)."""
    found = table(bodies.get("Operands", []))
    expected = OPERANDS_HEADERS[label.removesuffix(".md")]
    if found is None or header_text(found[0]) != expected:
        errors.append(f"{ident}: {label}: Operands table header must be {expected}")
        return None
    return found[1]


def situations(bodies):
    found = table(bodies.get("Exceptions", []))
    return [row[0] for row in found[1]] if found else []


# The authoring template: the single source of the shared Phase 0 lines (R4, P8).

def authoring_template():
    """(frontmatter name, template text or None, errors): the ````markdown fence under ## Example of command-authoring.md."""
    path = f"{PROTOCOL}/command-authoring.md"
    try:
        text = read(path)
    except OSError:
        return None, None, [f"authoring template: missing {path}"]
    blocks = [content for token, info, content in fenced_blocks(h2_sections(text)[1].get("Example", []))
              if token[0] == "`" and len(token) >= 4 and info == "markdown"]
    if not blocks:
        return None, None, [f"authoring template: {path} needs a ````markdown fence under ## Example"]
    template = "\n".join(blocks[0]) + "\n"
    name = re.search(r"(?m)^name:\s*(\S+)", template)
    return (name[1] if name else "command-name"), template, []


def shared_lines(template):
    """({prefix: line}, errors): the three shared Phase 0 lines, exactly once each in the template."""
    shared, errors = {}, []
    lines = visible_lines(template)
    for prefix in SHARED_PREFIXES:
        found = [line for line in lines if line.startswith(prefix)]
        if len(found) != 1:
            errors.append(f"authoring template: expected one {prefix!r}, got {len(found)}")
        else:
            shared[prefix] = found[0]
    return shared, errors


def check_template(name, template, shared):
    """Structural errors of the template in its Claude Code form and in its Codex form."""
    label = "command-authoring template"
    errors = check_command(label, template, shared)
    try:
        codex = sync_mirrors.to_codex(name, template)
    except SystemExit as exc:
        return errors + [f"{label}: Codex conversion failed: {exc}"]
    return errors + check_command(f"{label} (Codex form)", codex, shared)


def check_shared_contract():
    """The runtime artifacts both adapters must ship (commands mode)."""
    errors = []
    artifacts = ("claude-code/settings.json", "claude-code/agents/explorer.md", "claude-code/agents/worker.md",
                 "claude-code/hooks/ddl_gate.py", "codex/.codex/config.toml", "codex/.codex/hooks.json",
                 "codex/.codex/hooks/ddl_gate.py", "codex/.codex/agents/explorer.toml",
                 "codex/.codex/agents/worker.toml", "codex/.codex/rules/ddl.rules")
    for path in artifacts:
        if not (ROOT / path).is_file():
            errors.append(f"missing runtime artifact: {path}")
    if not re.search(r"(?m)^max_concurrent_threads_per_session\s*=\s*[1-9]\d*", read("codex/.codex/config.toml")):
        errors.append("Codex config: missing positive worker limit")
    for role in ("explorer", "worker"):
        if not re.search(r'(?m)^name\s*=\s*"' + role + '"', read(f"codex/.codex/agents/{role}.toml")):
            errors.append(f"Codex role: missing name {role}")
    return errors


def check_command(label, text, shared_lines):
    """Structural errors of one command file (or the authoring template)."""
    errors = []
    lines = visible_lines(text)
    phases = [(i, int(m[1]), m[2]) for i, line in enumerate(lines)
              if (m := re.match(r"^### Phase (\d+): (.+)", line))]
    if not phases or [p[1] for p in phases] != list(range(len(phases))):
        errors.append(f"{label}: phases must start at zero and be consecutive")
        return errors
    if phases[0][2] != "INIT":
        errors.append(f"{label}: first phase must be INIT")
    init_end = phases[1][0] if len(phases) > 1 else len(lines)
    init = lines[phases[0][0] + 1:init_end]
    for prefix, expected in shared_lines.items():
        found = [line for line in init if line.startswith(prefix)]
        # Generated command names differ; the shared bootstrap contains no invocation.
        if found != [expected]:
            errors.append(f"{label}: INIT rule missing, duplicated or different: {prefix}")
    report_count = 0
    for index, (start, number, title) in enumerate(phases):
        end = phases[index + 1][0] if index + 1 < len(phases) else len(lines)
        body = lines[start + 1:end]
        report_role = title == "REPORT" or (title == "REVIEW" and "+++Report:" in body)
        if report_role:
            report_count += 1
            if "+++STOP: always" not in body:
                errors.append(f"{label}: {title} must contain its own STOP")
        if "+++STOP: always" in body and index + 1 < len(phases):
            following = phases[index + 1][0] + 1
            first = next((line for line in lines[following:] if line.strip()), "")
            if not first.startswith("**Pre-condition."):
                errors.append(f"{label}: phase after {title} lacks an opening approval precondition")
    if not report_count:
        errors.append(f"{label}: no report phase")
    targets = re.findall(r"(?m)^\s+D(\d+):", "\n".join(lines))
    if not targets or list(map(int, targets)) != list(range(1, len(targets) + 1)):
        errors.append(f"{label}: detection targets must be unique and consecutive from D1")
    previous = ""
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if re.match(r"^\s+D\d+:", line) and previous.rstrip() != "+++DETECT:" and not re.match(r"^\s+D\d+:", previous):
            errors.append(f"P11: {label}:{number}: detection line without a preceding +++DETECT: header")
        previous = line
    if not any(line.startswith("+++NEVER:") for line in lines):
        errors.append(f"{label}: missing command constraints")
    raw = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("+++SWARM:"):
            continue
        j = i + 1
        while j < len(raw) and not raw[j].strip():
            j += 1
        if j == len(raw) or not raw[j].startswith("```"):
            errors.append(f"{label}:{i + 1}: SWARM needs an operand block")
            continue
        end = next((k for k in range(j + 1, len(raw)) if raw[k].startswith("```")), len(raw))
        operands = raw[j + 1:end]
        for field in ("team", "spawn", "each"):
            count = sum(bool(re.match(r"^\s{0,2}" + field + r":", x)) for x in operands)
            if count != 1:
                errors.append(f"{label}:{i + 1}: SWARM needs one {field}, got {count}")
        for field, valid in (("type", ("Explore", "general-purpose")), ("batch", ("auto", "none"))):
            for x in operands:
                m = re.match(r"^\s{0,2}" + field + r":\s*(.*?)\s*$", x)
                if m and m[1] not in valid:
                    errors.append(f"P11: {label}:{i + 1}: SWARM {field} must be {' or '.join(valid)}, got {m[1]!r}")
        for x in operands:
            m = re.match(r"^\s{0,2}max:\s*(.*?)\s*$", x)
            if m and not re.fullmatch(r"[1-9]\d*", m[1]):
                errors.append(f"P11: {label}:{i + 1}: SWARM max must be a positive integer, got {m[1]!r}")
    if re.search(r"§\s*\d", text):
        errors.append(f"{label}: obsolete numbered protocol reference")
    if "DESIGN" + ".md" in text:
        errors.append(f"{label}: notebook must be named design.md")
    if re.search(r"TeamCreate|TaskCreate|TaskList|TeamDelete|SendMessage|NotebookEdit|apply_patch|AskUserQuestion|request_user_input", text):
        errors.append(f"{label}: host tool names belong in the implementations under hosts/")
    return errors


def check_commands():
    name, template, errors = authoring_template()
    shared = {}
    if template is not None:
        shared, shared_errors = shared_lines(template)
        errors += shared_errors + check_template(name, template, shared)
    for directory in ("claude-code/skills", "codex/.agents/skills"):
        for command in COMMANDS:
            path = f"{directory}/{command}/SKILL.md"
            errors += check_command(path, read(path), shared)
    guides = ("claude-code/CLAUDE.md", "codex/AGENTS.md", ".claude/CLAUDE.md")
    for path in guides:
        text = read(path)
        names = re.findall(r"(?m)^\| `[/$](\w+)` \|", text)
        for command in COMMANDS:
            if names.count(command) != 1:
                errors.append(f"{path}: command table needs one {command}")
        if re.search(r"§\s*\d", text):
            errors.append(f"{path}: obsolete numbered protocol reference")
    headings = [re.findall(r"(?m)^## (.+)", read(p)) for p in guides[:2]]
    if headings[0] != [h.replace("Skills", "Commands") for h in headings[1]]:
        errors.append("runtime instruction templates: heading structure differs")
    return errors


# Protocol mode: P1-P10 and P13-P14 (P11 lives in check_command, P12 in tools/test_protocol.py).

def check_entry():
    """P1: the entry's sections, the Instruction set table and the Reading map."""
    path = f"{PROTOCOL}/SKILL.md"
    try:
        text = read(path)
    except OSError:
        return [f"P1: missing {path}"]
    errors = []
    err = lambda message: errors.append(f"P1: SKILL.md: {message}")  # noqa: E731
    titles, bodies = h2_sections(text)
    if titles != list(ENTRY_H2):
        err(f"H2 headings must be {list(ENTRY_H2)}, got {titles}")
    start = steps(bodies.get("Start", []))
    if len(start) != 4:
        err(f"Start needs exactly 4 numbered items, got {len(start)}")
    header = "| Directive | Syntax | Count | Placement | Rule |"
    found = table(bodies.get("Instruction set", []))
    if found is None or header_text(found[0]) != header:
        err(f"Instruction set table header must be {header}, got {header_text(found[0]) if found else 'no table'}")
    else:
        names = [plain(row[0]) for row in found[1]]
        if names != list(DIRECTIVES):
            err(f"Instruction set needs exactly the 10 Directive rows {list(DIRECTIVES)} in order, got {names}")
        for row in found[1]:
            token = DIRECTIVE_TOKENS.get(plain(row[0]), plain(row[0]))
            if len(row) < 5 or token not in row[1]:
                err(f"Instruction set row {plain(row[0])!r}: Syntax cell must contain {token!r}")
    found = table(bodies.get("Reading map", []))
    if found is None or header_text(found[0]) != READING_MAP_HEADER:
        err(f"Reading map table header must be {READING_MAP_HEADER}")
    else:
        if len(found[1]) < 6:
            err(f"Reading map needs at least 6 rows, got {len(found[1])}")
        base = (ROOT / PROTOCOL).resolve()
        hosts = base / "hosts"
        for row in found[1]:
            name = link_text(row[0])
            targets = local_targets(row[0], base)
            if not targets:
                err(f"Reading map row {name!r}: Operation cell needs a link to an operation beside the entry")
            for target in targets:
                if not target.is_file() or target.parent != base:
                    err(f"Reading map row {name!r}: Operation link target is not a file beside the entry: {target.name}")
            cell = row[2] if len(row) > 2 else ""
            targets = local_targets(cell, base)
            if plain(cell) == "none":
                continue
            if not targets:
                err(f"Reading map row {name!r}: Implementation cell needs none or a link to a file under hosts/")
            for target in targets:
                if not target.is_file() or not target.is_relative_to(hosts):
                    err(f"Reading map row {name!r}: Implementation link target is not a file under hosts/: {target.name}")
    return errors


def check_schema(label, text, titles, bodies):
    """P2: the eight sections of an operation, their emptiness rules and the Implementation links."""
    errors = []
    err = lambda message: errors.append(f"P2: {label}: {message}")  # noqa: E731
    if titles != list(OPERATION_H2):
        err(f"H2 headings must be {list(OPERATION_H2)}, got {titles}")
    if not re.search(r"(?m)^# \S", "\n".join(visible_lines(text))):
        err("needs an H1 title")
    for title in OPERATION_H2:
        body = bodies.get(title)
        if body is None:
            continue
        if not any(line.strip() for line in body):
            err(f"{title} is empty")
            continue
        if is_none(body):
            if title not in ("Syntax", "Operands"):
                err(f"{title} may not be None.")
            continue
        if title in ("Syntax", "Example") and not fenced_blocks(body):
            err(f"{title} needs a fenced block")
        if title in ("Operands", "Exceptions"):
            found = table(body)
            if found is None or not found[1]:
                err(f"{title} needs a table with at least one row")
            elif title == "Exceptions" and header_text(found[0]) != "| Situation | Behavior |":
                err("Exceptions table header must be | Situation | Behavior |")
    implementation = section_text(bodies.get("Implementation", []))
    directory = ROOT / PROTOCOL
    for host in HOST_NAMES:
        hits = [link for link in links(implementation) if f"hosts/{host}/" in link]
        if not hits:
            err(f"Implementation needs a link whose path contains hosts/{host}/")
        for hit in hits:
            if not (directory / hit.split("#")[0]).is_file():
                err(f"Implementation link target missing: {hit}")
    return errors


def check_parallel_work(text, bodies):
    label, ident, errors = "parallel-work.md", "P3", []
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None and [plain(row[0]) for row in rows] != list(OPERANDS_ROWS["parallel-work"]):
        errors.append(f"{ident}: {label}: Operands rows must be exactly {list(OPERANDS_ROWS['parallel-work'])} in order")
    syntax = "\n".join(line for _, _, content in fenced_blocks(bodies.get("Syntax", [])) for line in content)
    if not re.search(r"(?m)^\+\+\+SWARM:", syntax):
        errors.append(f"{ident}: {label}: Syntax fence needs a +++SWARM: line")
    for key in SWARM_OPERANDS:
        if not re.search(r"(?m)^\s*" + key + ":", syntax):
            errors.append(f"{ident}: {label}: Syntax fence needs the operand {key}")
    names = bold_steps(bodies.get("Operation", []))
    if names != list(OPERATION_STEPS["parallel-work"]) or len(steps(bodies.get("Operation", []))) != 6:
        errors.append(f"{ident}: {label}: Operation needs exactly 6 steps named {list(OPERATION_STEPS['parallel-work'])}")
    errors += literal_errors(ident, label, "Formats", section_text(bodies.get("Formats", [])), FORMATS["parallel-work"])
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["parallel-work"])
    return errors


def check_notebook(text, bodies):
    label, ident, errors = "notebook.md", "P4", []
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None and [plain(row[0]) for row in rows] != list(OPERANDS_ROWS["notebook"]):
        errors.append(f"{ident}: {label}: Operands rows must be exactly {list(OPERANDS_ROWS['notebook'])} in order")
    defined = section_text(bodies.get("Formats", []))
    errors += literal_errors(ident, label, "Formats", defined, FORMATS["notebook"])
    for command in NOTEBOOK_WRITERS:
        try:
            uses = read(f"claude-code/skills/{command}/SKILL.md")
            twin = ROOT / f"codex/.agents/skills/{command}/SKILL.md"
            if twin.is_file():
                uses += "\n" + twin.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"{ident}: missing claude-code/skills/{command}/SKILL.md")
            continue
        for mark in NOTEBOOK_MARKS:
            if mark in uses and mark not in defined:
                errors.append(f"{ident}: {label}: /{command} writes {mark!r} but Formats does not define it")
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["notebook"])
    return errors


def check_approval(text, bodies):
    label, ident, errors = "approval.md", "P5", []
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None:
        for form in ("always", "on D<n>"):
            if not any(form in plain(row[0]) for row in rows):
                errors.append(f"{ident}: {label}: Operands needs a row for {form!r}")
    count = len(steps(bodies.get("Operation", [])))
    if count != 3:
        errors.append(f"{ident}: {label}: Operation needs exactly 3 steps (Present, Ask, Wait and resume), got {count}")
    errors += literal_errors(ident, label, "Formats", section_text(bodies.get("Formats", [])), FORMATS["approval"])
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["approval"])
    return errors


def check_close(text, bodies):
    label, ident, errors = "close.md", "P6", []
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None:
        for command in ("/realize", "/commit"):
            if not any(command in plain(row[0]) for row in rows):
                errors.append(f"{ident}: {label}: Operands needs a row for {command}")
    names = bold_steps(bodies.get("Operation", []))
    if names != list(OPERATION_STEPS["close"]) or len(steps(bodies.get("Operation", []))) != 5:
        errors.append(f"{ident}: {label}: Operation needs exactly the steps Reflect, Docs, Resonate, Validate, Git review in order")
    errors += literal_errors(ident, label, "Formats", section_text(bodies.get("Formats", [])), FORMATS["close"])
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["close"])
    return errors


def check_git_review(text, bodies):
    label, ident, errors = "git-review.md", "P7", []
    err = lambda message: errors.append(f"{ident}: {label}: {message}")  # noqa: E731
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None:
        for operation in ("commit", "push"):
            if not any(operation in plain(row[0]) for row in rows):
                err(f"Operands needs a row for {operation!r}")
    count = len(steps(bodies.get("Operation", [])))
    if count < 4:
        err(f"Operation needs at least 4 steps, got {count}")
    errors += literal_errors(ident, label, "Formats", section_text(bodies.get("Formats", [])), FORMATS["git-review"])
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["git-review"])
    # The Example is a parsable Git review request with a commit and a push operation.
    blocks = [content for _, info, content in fenced_blocks(bodies.get("Example", [])) if info == "json"]
    if not blocks:
        err("Example needs a ```json fence")
        return errors
    try:
        data = json.loads("\n".join(blocks[0]))
    except ValueError as exc:
        err(f"Example JSON does not parse: {exc}")
        return errors
    if not isinstance(data, dict) or "language" not in data:
        err("Example JSON needs a language key")
    operations = data.get("operations") if isinstance(data, dict) else None
    if not isinstance(operations, list) or not operations:
        err("Example JSON needs a non-empty operations list")
        return errors
    commands = []
    for operation in operations:
        if not isinstance(operation, dict) or "cwd" not in operation or "command" not in operation:
            err("every Example operation needs cwd and command")
            continue
        command = operation["command"]
        commands.append(" ".join(map(str, command)) if isinstance(command, list) else str(command))
    for kind in ("git commit", "git push"):
        if not any(kind in command for command in commands):
            err(f"Example operations need a {kind} operation")
    return errors


def check_command_authoring(text, bodies):
    label, ident, errors = "command-authoring.md", "P8", []
    err = lambda message: errors.append(f"{ident}: {label}: {message}")  # noqa: E731
    rows = operands_rows(ident, label, bodies, errors)
    if rows is not None:
        roles = " ".join(plain(row[0]) for row in rows)
        for role in ("INIT", "SURVEY", "READ", "WORK", "IMPLEMENT", "REPORT", "EXECUTE", "VERIFY"):
            if role not in roles:
                err(f"Operands needs a row for the {role} role")
    count = len(steps(bodies.get("Operation", [])))
    if count < 4:
        err(f"Operation needs at least 4 steps, got {count}")
    errors += literal_errors(ident, label, "Formats", section_text(bodies.get("Formats", [])), FORMATS["command-authoring"])
    name, template, template_errors = authoring_template()
    errors += [f"{ident}: {e}" for e in template_errors]
    if template is not None:
        shared, shared_errors = shared_lines(template)
        errors += [f"{ident}: {e}" for e in shared_errors]
        errors += [e if e.startswith("P11: ") else f"{ident}: {e}" for e in check_template(name, template, shared)]
        errors += literal_errors(ident, label, "template", template,
                                 ("+++DETECT:", "+++Report:", "**Pre-condition.**", "+++NEVER:"))
        for prefix in SHARED_PREFIXES:
            if any(line.startswith(prefix) for line in visible_lines(text)):
                err(f"shared Phase 0 line repeated outside the template fence: {prefix!r}")
    errors += keyword_errors(ident, label, "Exceptions", situations(bodies), EXCEPTIONS["command-authoring"])
    return errors


def check_implementations():
    """P9 (and the P2 heading rule) for the eight implementations under hosts/."""
    errors = []
    directory = ROOT / PROTOCOL / "hosts"
    base = (ROOT / PROTOCOL).resolve()
    for name in IMPLEMENTATIONS:
        host, _, operation = name.partition("/")
        label = f"hosts/{name}.md"
        err = lambda message, label=label: errors.append(f"P9: {label}: {message}")  # noqa: E731
        try:
            text = read(f"{PROTOCOL}/hosts/{name}.md")
        except OSError:
            err("missing")
            continue
        titles, bodies = h2_sections(text)
        if titles != list(HOST_H2):
            errors.append(f"P2: {label}: H2 headings must be {list(HOST_H2)}, got {titles}")
        if not re.search(r"(?m)^# \S", "\n".join(visible_lines(text))):
            err("needs an H1 title")
        found = table(bodies.get("Mapping", []))
        if found is None or header_text(found[0]) != MAPPING_HEADER:
            err(f"Mapping table header must be {MAPPING_HEADER}")
        else:
            errors += keyword_errors("P9", label, "Mapping", [row[0] for row in found[1]], CONCERNS[operation])
        found = table(bodies.get("Observed", []))
        if found is None or header_text(found[0]) != "| Fact | Version | Date |":
            err("Observed table header must be | Fact | Version | Date |")
        elif not found[1]:
            err("Observed needs at least one row")
        else:
            for number, row in enumerate(found[1], 1):
                if len(row) < 3 or not row[1]:
                    err(f"Observed row {number} needs a non-empty Version")
                date = row[2] if len(row) > 2 else ""
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    err(f"Observed row {number} needs a YYYY-MM-DD Date, got {date!r}")
        if len(bullets(bodies.get("Coverage", []))) < 2:
            err("Coverage needs at least two bullets")
        targets = local_targets(section_text(bodies.get("Read when", [])), directory / host)
        if operation != "start":
            if base / f"{operation}.md" not in targets:
                err(f"Read when needs a link back to ../../{operation}.md")
        else:
            if not any(target.parent == base for target in targets):
                err("Read when needs a link back to an operation or the entry")
            for sibling in HOST_OPERATIONS[1:]:
                if (directory / host / f"{sibling}.md").resolve() not in targets:
                    err(f"Read when needs a link to {sibling}.md")
    return errors


def check_vocabulary():
    """P10: no section signs anywhere; host tool names only under hosts/."""
    errors = []
    for path in protocol_files():
        try:
            text = read(path)
        except OSError:
            continue  # reported by P1, P2 or P9
        label = path[len(PROTOCOL) + 1:]
        if "§" in text:
            errors.append(f"P10: {label}: contains a section sign (§); refer to operations by name and link")
        if "/hosts/" not in path:
            names = sorted({m[1] for m in TOOL_NAMES.finditer(text)})
            if names:
                errors.append(f"P10: {label}: host tool names belong under hosts/: {', '.join(names)}")
    return errors


def check_budget():
    """P13: the cumulative byte budgets of the validate, draft, realize-plan and realize-close paths per host, and the execution total."""
    errors = []
    for host in HOST_NAMES:
        files, total = [], 0
        for name, limit, additions in BUDGET_PATHS:
            for file in (addition.format(host=host) for addition in additions):
                size = byte_size(protocol_path(file))
                if size is not None:
                    files.append(file)
                    total += size
            if total > limit:
                errors.append(f"P13: {host} {name}: {total} bytes exceeds {limit} ({' + '.join(files)})")
    execution = ["SKILL.md"] + [f"{n}.md" for n in OPERATIONS if n not in AUTHOR_ONLY]
    execution += [f"hosts/{n}.md" for n in IMPLEMENTATIONS]
    sizes = [byte_size(protocol_path(file)) for file in execution]
    total = sum(size for size in sizes if size is not None)
    if total > EXECUTION_LIMIT:
        errors.append(f"P13: execution total: {total} bytes exceeds {EXECUTION_LIMIT}")
    return errors


def sentences(text):
    """[(line number, normalized sentence)] of the prose outside fences and code spans: split at `.`, `;`, `:` and
    line ends, reduced to lowercase letters and single spaces, 60 or more characters long (P14)."""
    result = []
    for number, line in enumerate(visible_lines(text), 1):
        for piece in re.split(r"[.;:]", INLINE_CODE.sub("", line)):
            normalized = " ".join(re.sub(r"[^a-z ]+", " ", piece.lower()).split())
            if len(normalized) >= 60:
                result.append((number, normalized))
    return result


def check_duplicates():
    """P14: no sentence of 60 or more normalized characters appears in two protocol files or twice in one."""
    errors, places = [], {}
    for path in protocol_files():
        try:
            text = read(path)
        except OSError:
            continue  # reported by P1, P2 or P9
        label = path[len(PROTOCOL) + 1:]  # named as in P13
        for number, sentence in sentences(text):
            places.setdefault(sentence, []).append((label, number))
    for sentence, found in places.items():
        first = f"{found[0][0]}:{found[0][1]}"
        for label, number in found[1:]:
            errors.append(f'P14: duplicate sentence: {first} and {label}:{number}: "{sentence[:60]}"')
    return errors


def check_protocol():
    errors = check_entry()
    checks = {"parallel-work": check_parallel_work, "notebook": check_notebook, "approval": check_approval,
              "close": check_close, "git-review": check_git_review, "command-authoring": check_command_authoring}
    for name in OPERATIONS:
        path = f"{PROTOCOL}/{name}.md"
        try:
            text = read(path)
        except OSError:
            errors.append(f"P2: missing {path}")
            continue
        titles, bodies = h2_sections(text)
        errors += check_schema(f"{name}.md", text, titles, bodies)
        errors += checks[name](text, bodies)
    errors += check_implementations()
    errors += check_vocabulary()
    errors += check_budget()
    errors += check_duplicates()
    return errors


def check_docs():
    errors = []
    documents = []
    for name in ("design_philosophy", "design_philosophy_extended"):
        pair = [read(f"docs/{lang}/{name}.md") for lang in ("en", "ja")]
        documents.extend(pair)
        levels = [re.findall(r"(?m)^(#+) ", text) for text in pair]
        if levels[0] != levels[1]:
            errors.append(f"{name}: English/Japanese heading structure differs")
        if any("Binding Decisions" not in text for text in pair):
            errors.append(f"{name}: missing Binding Decisions explanation")
    japanese = "\n".join(read(f"docs/ja/{n}.md") for n in ("design_philosophy", "design_philosophy_extended"))
    for row in read("docs/ja/GLOSSARY.md").splitlines():
        if not row.startswith("| ") or row.startswith("| 英語"):
            continue
        cells = [x.strip() for x in row.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        for token in filter(None, map(str.strip, cells[2].split("、"))):
            found = re.search(r"(?<![専部名])門", japanese) if token == "門" else token in japanese
            if found:
                errors.append(f"Japanese glossary: forbidden translation {token!r}")
    for token in ("コンテキストウィンドウ", "コンパクション", "帰属表記", "ゲート"):
        if token not in japanese:
            errors.append(f"Japanese glossary: missing required term {token}")
    pairs = (("#### Context Engineering", "#### コンテキストエンジニアリング"),
             ("#### Instructions and Mechanisms", "#### 指示と仕組み"))
    for english, translated in pairs:
        if english not in documents[2] or translated not in documents[3]:
            errors.append(f"philosophy: missing paired section {english}")
    if "LLMs lack long-term memory" in documents[2] or "LLM には長期記憶がありません" in documents[3]:
        errors.append("philosophy: obsolete memory explanation")
    flow = "INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY"
    for path in ("claude-code/README.md", "codex/README.md", "docs/en/design_philosophy_extended.md", "docs/ja/design_philosophy_extended.md"):
        if flow not in read(path):
            errors.append(f"{path}: missing the documented phase-role sequence")
    paths = [ROOT / "README.md", ROOT / "claude-code/README.md", ROOT / "codex/README.md", ROOT / ".claude/CLAUDE.md",
             ROOT / "claude-code/CLAUDE.md", ROOT / "codex/AGENTS.md"]
    paths += list((ROOT / "docs").rglob("*.md"))
    # Names of the protocol tree before the hosts/ layout are obsolete in every document (the tokens are split so
    # that this file does not match a search for them).
    obsolete = ("DESIGN" + ".md", "examples" + "/", ".codex/commands", ".claude/commands",
                "DDL-PROTOCOL-SKILL", "Codex Runtime Contract", "dog" + "food", "EXECUTE → VALIDATE",
                "references" + "/", "runtimes" + "/", "-start" + ".md", "examples" + ".md")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in obsolete:
            if token in text:
                errors.append(f"{path.relative_to(ROOT)}: obsolete reference {token!r}")
    return errors


MODES = {"commands": (lambda: check_shared_contract() + check_commands(), "COMMANDS_OK"),
         "docs": (check_docs, "DOCUMENTS_OK"),
         "protocol": (check_protocol, "PROTOCOL_OK")}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        raise SystemExit("usage: check_ddl.py commands|docs|protocol")
    check, success = MODES[sys.argv[1]]
    errors = check()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(success)
    return 0


if __name__ == "__main__":
    sys.exit(main())
