---
name: ddl-protocol
description: "Use this skill when executing or authoring DDL commands (draft, realize, reflect, refactoring, docs, commit, resonate). Triggers: any `/command` invocation registered in CLAUDE.md, requests to create new DDL commands, or tasks referencing design.md-driven workflows with Phases, DETECT, STOP, SWARM. Do NOT use for general coding, documentation, or tasks unrelated to DDL workflow execution."
---

# DDL-PROTOCOL

Design-Doc Loop. Human-LLM collaborative workflow protocol.
Commands are source of truth. This skill describes how to read and write them.

## Quick Reference

| Directive | Syntax | Purpose |
|-----------|--------|---------|
| Phase | `### Phase <N>: <n>` | Ordered execution step (markdown heading) |
| +++STOP | `+++STOP: always` or `+++STOP: on D<N>` | Block until human approves |
| +++DETECT | `+++DETECT:` + `D<N>: <n> — <trigger>` | Parallel violation scan |
| +++SWARM | `+++SWARM: <cond>` + `spawn:` + `each:` | Conditional parallel fork |
| +++NEVER | `+++NEVER: <prohibition>` | Invariant constraint |
| +++Report | `+++Report:` + table rows | Output template for STOP gate |

`+++` marks behavioral directives inside phase bodies. Phase headings stay as `###`.

## Grammar (BNF)

```bnf
<command>    ::= <header> <usage> "## Phases" <phase>{4,6} "## Constraints" <never>{2,4}
<header>     ::= "# " <command-name> NL <intent-line> NL
<usage>      ::= "## Usage" NL <usage-line>+
<phase>      ::= "### Phase " <N> ": " <n> NL <step>* <directive>*
<directive>  ::= <stop> | <detect> | <swarm> | <report>
<stop>       ::= "+++STOP: " ("always" | "on D" <N>) NL
<detect>     ::= "+++DETECT:" NL ("  D" <N> ": " <n> " — " <trigger> NL){1,7}
<swarm>      ::= "+++SWARM: " <cond> NL "  spawn: " <role> NL "  each: " <task> NL
<never>      ::= "+++NEVER: " <text> NL
<report>     ::= "+++Report:" NL <table-row>+
```

## Element Rules

### Phase
- N = 0 ascending. 4–6 per command.
- **Phase 0: INIT is required.** Must read DDL-PROTOCOL-SKILL.md, then `CLAUDE.md`, then `design.md`.
- Canonical names: INIT → SURVEY/READ/DISCOVER → WORK/IMPLEMENT/AUDIT → REPORT → EXECUTE/APPLY → VERIFY

### +++STOP
- Every command needs `+++STOP: always` at its REPORT phase.
- `+++STOP: on D<N>` halts only when that detect target fires.
- Never auto-proceed past a STOP gate.

### +++DETECT
- N = 1 ascending, unique per command. 5–7 recommended.
- Trigger must be operationally verifiable (not vague).
- All targets run in parallel within their phase.

### +++SWARM
- Condition: typically `2+ scopes in design.md`.
- `{scope}` resolves from design.md at runtime.
- Role: `verb-{scope}` (e.g., `reader-backend`, `scanner-docs`).
- Single scope → inline, no SWARM.
- Lead integrates after all agents complete.

### +++NEVER
- 2–4 per command. Imperative form.
- Global NEVERs in CLAUDE.md; command NEVERs in command file.

## Command Template

```markdown
# <command-name>

<One-line intent.>

## Usage

- `/<command>` — <default>
- `/<command> <arg>` — <specific>

## Phases

### Phase 0: INIT

1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `CLAUDE.md`
3. Read `design.md` — extract <relevant items>
4. If no `design.md` → <fallback>

### Phase 1: <SURVEY/READ/DISCOVER>

+++SWARM: 2+ scopes in design.md
  spawn: <role>-{scope}
  each: <task per scope>

### Phase 2: <WORK/IMPLEMENT/AUDIT>

<Core activity>

+++DETECT:
  D1: <n> — <trigger>
  D2: <n> — <trigger>
  D3: <n> — <trigger>
  D4: <n> — <trigger>
  D5: <n> — <trigger>

### Phase 3: <REPORT>

+++STOP: always

+++Report:
| # | <col> | <col> | <col> |

### Phase 4: <EXECUTE/APPLY> (if applicable)

+++SWARM: 2+ approved changes across scopes
  spawn: <role>-{scope}
  each: apply approved changes

### Phase 5: <VERIFY> (if applicable)

Re-scan. Summarize. Suggest next command.

## Constraints

+++NEVER: <prohibition>
+++NEVER: <prohibition>
+++NEVER: <prohibition>
```

## Project File Structure

```
CLAUDE.md          ← Project config, command registry, global DETECT/NEVER
  ↑
commands/*.md      ← Individual commands using +++directives
  ↑
design.md          ← Scopes, principles, validation commands
```

Each layer references only its immediate parent.

## design.md Contract

| Item | Used by | How |
|------|---------|-----|
| Scopes | All | +++SWARM spawn, parallelization |
| Principles | realize, reflect, draft | +++DETECT triggers, +++STOP conditions |
| Validation cmds | realize, refactoring, commit | VERIFY phase execution |
| Doc paths | docs, resonate | Discovery phase |

If absent: `/draft` asks or defaults. `/realize`, `/reflect` refuse. Others scan project root.

## CLAUDE.md Template

```markdown
# <Project Name>

## Protocol
→ DDL-PROTOCOL
→ Read `.claude/commands/DDL-PROTOCOL-SKILL.md` before executing any command

## Commands
| Command | Intent |
|---------|--------|

## Structure
- <project layout>

## Detection Targets
+++DETECT:
  D1: <n> — <trigger>
  D2: <n> — <trigger>

## Behavior
### On session start
### On any task
### On swarm
### On completion

## Constraints
+++NEVER: <prohibition>
+++NEVER: <prohibition>
```

## Execution Checklist

When executing a DDL command:

1. **INIT**: Read DDL-PROTOCOL-SKILL.md → Read CLAUDE.md → Read design.md → Extract scopes/principles
2. **SURVEY**: If 2+ scopes → SWARM; else inline
3. **WORK**: Execute core task. Run +++DETECT in parallel. If +++STOP: on D<N> fires → halt, present to human
4. **REPORT**: Present +++Report table. +++STOP: always. Wait for human
5. **EXECUTE** (if approved): SWARM if multi-scope, else inline
6. **VERIFY** (if applicable): Re-scan, confirm, suggest next command

When authoring a new DDL command:

1. Write one-line intent
2. Define 4–6 phases starting with INIT
3. Add 5–7 +++DETECT targets with verifiable triggers
4. Add +++STOP: always at REPORT (mandatory)
5. Add conditional +++STOP: on D<N> where human judgment needed
6. Add +++SWARM at phases with parallelizable scopes
7. Add 2–4 +++NEVER constraints
8. Verify: Phase 0 reads DDL-PROTOCOL-SKILL.md, then CLAUDE.md, then design.md
