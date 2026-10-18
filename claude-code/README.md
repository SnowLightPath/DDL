# DDL for Claude Code

The Claude Code side of [Design-Doc Loop (DDL)](../docs/en/design_philosophy.md): the command skills, the protocol skill `ddl-protocol`, and the adapter. This directory has the layout of a project's `.claude/`: `CLAUDE.md` (the template for a project's `.claude/CLAUDE.md`), `skills/<name>/SKILL.md` for the eight commands and `ddl-protocol`, and the adapter (`settings.json`, `agents/`, `hooks/`).

## Installation

**In the environment** (recommended). One clone serves every project:

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh --claude
```

The script symlinks `~/.claude/skills/<name>` for the nine skills, `~/.claude/agents/explorer.md` and `worker.md`, and `~/.claude/hooks/ddl_gate.py`, and merges the DDL fragment into `~/.claude/settings.json`: the gate hooks, `env` `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, `permissions.ask` for `Bash(git push *)`, and `attribution` off. Existing settings are kept, and the first time `settings.json` is changed a copy is kept next to it as `settings.json.ddl-backup`. Without `--claude`, it installs for each runtime whose home directory exists (`~/.claude`, `~/.codex`); when neither exists, the script stops and asks for `--claude` or `--codex`. `--dry-run` prints what install, doctor, and uninstall would do without writing. `bash DDL/bin/doctor.sh` checks the install: it lists every link and merged entry as OK or not OK, runs the gate's tests, ends with `N OK, M not OK`, and exits 1 when anything is not OK. `bash DDL/bin/uninstall.sh` removes the links and the merged fragment. To update, `git pull` in the clone (the links follow) and run `bash DDL/bin/install.sh` again; it is idempotent.

A project then needs only `design.md` and a short instruction file:

```bash
mkdir -p your-project/.claude
cp DDL/claude-code/CLAUDE.md your-project/.claude/CLAUDE.md
```

**In the project.** Copy this directory into the project's `.claude/` (`bash DDL/bin/install.sh --project your-project --claude` makes the same copy, skipping the README and keeping an existing `CLAUDE.md`):

```bash
cp -R DDL/claude-code/{CLAUDE.md,settings.json,agents,hooks,skills} your-project/.claude/
```

Claude Code runs project hooks after you trust the folder.

- Edit the `# Project Name` title in the copied `CLAUDE.md`.
- A command skill runs on `/name`; its frontmatter shows an argument hint and keeps the model from starting it on its own (`disable-model-invocation`). Commands look up the protocol, when it is not already in context, in the project's copy `.claude/skills/ddl-protocol/SKILL.md`, then the user-level copy `$HOME/.claude/skills/ddl-protocol/SKILL.md`.
- What loads when: Claude Code loads `CLAUDE.md` at session start and re-injects it after compaction; `CLAUDE.md` imports design.md then; the protocol and a command load when the command runs (Phase 0); a worker's prompt is its whole context.
- The adapter: `settings.json` (the gate hook on PreToolUse, Stop, UserPromptSubmit, and SessionStart; spawn depth 1; an ask rule before `git push`; attribution off), `agents/` (`explorer` for read-only work, `worker` for writers), and `hooks/ddl_gate.py`. `CLAUDE.md` imports design.md with the line `@../design.md`, so the notebook is in context from session start. The gate is a `python3` script (standard library only); if `python3` is missing, the hook fails open and the rules hold as instructions. The adapter enforces the mechanical part of the rules (a STOP holds until you speak, workers keep their roles); the rules are the same without it, as instructions (protocol §2.5).
- A project can add an overlay in `commands/<name>.md` at the project root to give a command project facts (target paths, protected terms, validation commands) without copying the whole command, and a project's own copy of a command (`.claude/skills/<name>/SKILL.md`) takes precedence over the user-level one.

Do not create an empty `design.md`: `/realize`, `/reflect`, and `/validate` refuse to run without one, and an empty file defeats that guard. Run `/draft` instead; it writes `design.md` from the experience you describe.

## Commands

### Core Loop

| Command | Usage | Intent |
|---------|-------|--------|
| `/draft` | `/draft`, `/draft <feature>`, `/draft <feature> <technology or outlook>` | Capture ideal experience, and the decisions and outlook it depends on, before implementation |
| `/realize` | `/realize`, `/realize <feature>` | Manifest philosophy as working code |
| `/reflect` | `/reflect`, `/reflect <path>` | Update documents based on implementation |

### Support Commands

| Command | Usage | Intent |
|---------|-------|--------|
| `/validate` | `/validate`, `/validate <scope>` | Run mechanical validation per scope: the Validation commands (lint/test/build) and the mechanical gates in Acceptance Gates |
| `/resonate` | `/resonate`, `/resonate <path>` | Synchronize multilingual document versions |
| `/commit` | `/commit` (local only), `/commit remote` (commit and push) | Record verified changes to repository |
| `/docs` | `/docs`, `/docs <path>` | Audit and fix documentation quality |
| `/refactoring` | `/refactoring`, `/refactoring <path>` | Audit and fix code quality |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Command Structure

Every command follows the DDL-PROTOCOL defined in the protocol skill `ddl-protocol` (`skills/ddl-protocol/SKILL.md`):

1. **Phases** — ordered steps (INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY). A phase that follows a `+++STOP: always` opens with a **Pre-condition** line: enter only after explicit approval at that STOP
2. **+++DETECT** — automated checks that run in parallel within their phase (D1, D2, … per command)
3. **+++SWARM** — parallel workers that fan out over scopes, Direction lanes, or files when 2 or more exist, one per unit or batch (`team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:`), run with the runtime's own mechanism (protocol §2.5); without a parallel primitive, the lead executes the assignments itself; each worker's prompt is its whole context: the scope's paths, the Experience items the scope serves, the principles, the Binding Decisions, the Direction stage, the scope's validation commands, the rows the user approved for the phase (verbatim), and in `/realize` the approved plan (protocol §2.4 Step 3)
4. **+++STOP** — mandatory human approval before mutating shared artifacts; the agent ends its turn and waits, starting or continuing no worker until approval (protocol §1.5), with its report headed `+++DDL_REPORT`. `+++STOP: always` halts at REPORT, and `+++STOP: on D{n}` halts when that DETECT fires. Human gates written in design.md (Direction and Acceptance Gates) run as STOPs too. Advance approval applies only to design.md human gates the user names or explicitly waives, and is written after that gate at once as `approved in advance (<date>)`; it never skips a STOP written in a command file. A conversation summary (compaction) is not a user message and approves nothing: when the report a STOP asked about is no longer in context verbatim, the command rebuilds it from design.md, git, and the files it described and asks again, and what the user approves is written to design.md at once (protocol §1.5)
5. **+++Report** — the table template the agent fills in and shows at a STOP
6. **+++DDL_PHASE** / **+++DDL_REPORT** — output markers: `+++DDL_PHASE: <PhaseName>` on the first line of a phase that mutates state, and `+++DDL_REPORT` as the heading above the report table at every STOP
7. **+++NEVER** — invariants that must never be violated

## design.md Sections

`design.md` holds these sections; each item names who writes it. A project uses only the sections it needs. Retiring a section (a spent Direction, accepted Acceptance Gates) also shrinks what every later session loads. Experience is always needed and comes first; Binding Decisions, Direction, and Acceptance Gates are optional, and `/draft` asks about them only when the user's words point to them:

1. **Intent** — why the project exists. Written by the human
2. **Scopes** — the scope table that drives SWARM. Written by the human and `/reflect`
3. **Principles** — design principles, under `## Principles` or `## Core Principles`. Written by `/draft` (D5) and `/reflect`
4. **Experience** — consumer-side usage with inputs, outputs, and error / empty / boundary states. Written by `/draft` and `/reflect`
5. **Binding Decisions** — technology fixed before implementation because the Experience depends on it, an external constraint requires it, or the human prefers it and says so (Decision, Why it binds, Source); only the human binds. Written by the human through `/draft`; `/realize` records a delegated choice once the human approves it
6. **Direction** — non-binding outlook: stages, parallel lanes, what the human sees, and each stage's gates; `/realize` appends `passed <date>` to each gate that passes (after `approved in advance (<date>)` when the gate was waived) and writes the approved plan under the table as `Approved plan (<date>)`. Written by `/draft`; `/realize` marks gates passed and writes the Approved plan lines; `/reflect` retires passed stages with their Approved plan lines
7. **Acceptance Gates** — mechanical gates and human gates that define done; the work is accepted when `/realize` has marked every gate passed, and `/reflect` then retires the section (lasting checks move to Validation). Written by `/draft`; `/realize` marks gates passed; `/reflect` retires the section
8. **Validation** — per-scope mechanical checks. Written by the human and `/reflect`

See protocol §3 (`skills/ddl-protocol/SKILL.md`).

## Philosophy

These commands are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a rigid process—it's a collection of desired designs.
> DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.
