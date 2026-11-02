#!/usr/bin/env python3
"""Check maintained DDL structure and documentation, without running a model.

The command check validates each phase and operand block, not aggregate word
counts. The documentation check preserves the existing language/terminology
checks. Model loading and human choice delivery need separate live tests.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMANDS = ("draft", "realize", "reflect", "validate", "resonate", "commit", "docs", "refactoring")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


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


def check_shared_contract():
    errors = []
    protocol = read("claude-code/skills/ddl-protocol/SKILL.md")
    for directive in ("DETECT", "STOP", "SWARM", "NEVER", "Report", "DDL_REPORT", "DDL_PHASE"):
        if len(re.findall(r"(?m)^\| `\+\+\+" + directive + r"` \|", protocol)) != 1:
            errors.append(f"protocol: expected one definition for +++{directive}")
    close = read("claude-code/skills/ddl-protocol/references/close.md")
    steps = re.findall(r"(?m)^\d+\. \*\*([^*:]+):?\*\*", close)
    if steps != ["Reflect", "Docs", "Resonate", "Validate", "Git review"]:
        errors.append("Close: expected Reflect, Docs, Resonate, Validate, Git review in order")
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


def check_commands():
    errors = []
    template = read("claude-code/skills/ddl-protocol/references/command-authoring.md")
    prefixes = ("A command run from a user-level install", "1. Read the DDL protocol", "2. Read project-local runtime guidance")
    shared = {}
    for prefix in prefixes:
        found = [line for line in template.splitlines() if line.startswith(prefix)]
        if len(found) != 1:
            errors.append(f"authoring template: expected one {prefix!r}, got {len(found)}")
        else:
            shared[prefix] = found[0]
    for directory in ("claude-code/skills", "codex/.agents/skills"):
        for name in COMMANDS:
            path = f"{directory}/{name}/SKILL.md"
            text = read(path)
            lines = visible_lines(text)
            phases = [(i, int(m[1]), m[2]) for i, line in enumerate(lines)
                      if (m := re.match(r"^### Phase (\d+): (.+)", line))]
            if not phases or [p[1] for p in phases] != list(range(len(phases))):
                errors.append(f"{path}: phases must start at zero and be consecutive")
                continue
            if phases[0][2] != "INIT":
                errors.append(f"{path}: first phase must be INIT")
            init_end = phases[1][0] if len(phases) > 1 else len(lines)
            init = lines[phases[0][0] + 1:init_end]
            for prefix, expected in shared.items():
                found = [line for line in init if line.startswith(prefix)]
                # Generated command names differ; the shared bootstrap contains no invocation.
                if found != [expected]:
                    errors.append(f"{path}: INIT rule missing, duplicated or different: {prefix}")
            report_count = 0
            for index, (start, number, title) in enumerate(phases):
                end = phases[index + 1][0] if index + 1 < len(phases) else len(lines)
                body = lines[start + 1:end]
                report_role = title == "REPORT" or (title == "REVIEW" and "+++Report:" in body)
                if report_role:
                    report_count += 1
                    if "+++STOP: always" not in body:
                        errors.append(f"{path}: {title} must contain its own STOP")
                if "+++STOP: always" in body and index + 1 < len(phases):
                    following = phases[index + 1][0] + 1
                    first = next((line for line in lines[following:] if line.strip()), "")
                    if not first.startswith("**Pre-condition."):
                        errors.append(f"{path}: phase after {title} lacks an opening approval precondition")
            if not report_count:
                errors.append(f"{path}: no report phase")
            targets = re.findall(r"(?m)^\s+D(\d+):", "\n".join(lines))
            if not targets or list(map(int, targets)) != list(range(1, len(targets) + 1)):
                errors.append(f"{path}: detection targets must be unique and consecutive from D1")
            if not any(line.startswith("+++NEVER:") for line in lines):
                errors.append(f"{path}: missing command constraints")
            raw = text.splitlines()
            for i, line in enumerate(lines):
                if not line.startswith("+++SWARM:"):
                    continue
                j = i + 1
                while j < len(raw) and not raw[j].strip():
                    j += 1
                if j == len(raw) or not raw[j].startswith("```"):
                    errors.append(f"{path}:{i + 1}: SWARM needs an operand block")
                    continue
                end = next((k for k in range(j + 1, len(raw)) if raw[k].startswith("```")), len(raw))
                operands = raw[j + 1:end]
                for field in ("team", "spawn", "each"):
                    count = sum(bool(re.match(r"^\s{0,2}" + field + r":", x)) for x in operands)
                    if count != 1:
                        errors.append(f"{path}:{i + 1}: SWARM needs one {field}, got {count}")
            if re.search(r"§\s*\d", text):
                errors.append(f"{path}: obsolete numbered protocol reference")
            if "DESIGN" + ".md" in text:
                errors.append(f"{path}: notebook must be named design.md")
            if re.search(r"TeamCreate|TaskCreate|TaskList|TeamDelete|SendMessage|NotebookEdit|apply_patch|AskUserQuestion|request_user_input", text):
                errors.append(f"{path}: runtime tools belong in runtime procedures")
    guides = ("claude-code/CLAUDE.md", "codex/AGENTS.md", ".claude/CLAUDE.md")
    for path in guides:
        text = read(path)
        names = re.findall(r"(?m)^\| `[/$](\w+)` \|", text)
        for name in COMMANDS:
            if names.count(name) != 1:
                errors.append(f"{path}: command table needs one {name}")
        if re.search(r"§\s*\d", text):
            errors.append(f"{path}: obsolete numbered protocol reference")
    headings = [re.findall(r"(?m)^## (.+)", read(p)) for p in guides[:2]]
    if headings[0] != [h.replace("Skills", "Commands") for h in headings[1]]:
        errors.append("runtime instruction templates: heading structure differs")
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
    paths = [ROOT / "README.md", ROOT / "claude-code/README.md", ROOT / "codex/README.md", ROOT / ".claude/CLAUDE.md"]
    paths += list((ROOT / "docs").rglob("*.md"))
    obsolete = ("DESIGN" + ".md", "examples" + "/", ".codex/commands", ".claude/commands",
                "DDL-PROTOCOL-SKILL", "Codex Runtime Contract", "dog" + "food", "EXECUTE → VALIDATE")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in obsolete:
            if token in text:
                errors.append(f"{path.relative_to(ROOT)}: obsolete reference {token!r}")
    return errors


def main():
    if sys.argv[1:] not in (["commands"], ["docs"]):
        raise SystemExit("usage: check_ddl.py commands|docs")
    mode = sys.argv[1]
    errors = check_shared_contract() + check_commands() if mode == "commands" else check_docs()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("COMMANDS_OK" if mode == "commands" else "DOCUMENTS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
