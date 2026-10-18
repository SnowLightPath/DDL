# Project Name

## Protocol

→ DDL-PROTOCOL
→ Read the DDL protocol before executing any skill, when it is not already in context, in the lookup order of protocol §2.5: the project's copy `.agents/skills/ddl-protocol/SKILL.md`, then the user-level copy `$HOME/.codex/skills/ddl-protocol/SKILL.md`

## Notebook

`design.md` is injected at session start and after a compaction by the adapter's SessionStart hook (Codex adapter, protocol §2.5), so the notebook is in context without a read; when the hooks are not trusted, read `design.md` if it exists. A project whose notebook is another file (protocol §3) names it here.

## Skills

| Skill | Intent |
|-------|--------|
| `$draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `$realize` | Write code based on design principles and Binding Decisions |
| `$reflect` | Update documents based on implementation |
| `$validate` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |
| `$resonate` | Sync multilingual docs (en/ja) |
| `$commit` | Git commit (`$commit remote` also pushes) |
| `$docs` | Audit and fix documentation |
| `$refactoring` | Audit and fix code quality |

## Structure

- `design.md` - Project design document (scopes, principles, validation; Experience, Binding Decisions, Direction, Acceptance Gates when drafted — protocol §3)
- `.agents/skills/<name>/SKILL.md` with `agents/openai.yaml` - The DDL skills and the protocol skill `ddl-protocol`, when DDL is copied into the project (`openai.yaml` keeps Codex from starting a skill on its own; a skill runs on `$name`); with the user-level install they live in `$HOME/.codex/skills/` and a project copy, when present, takes precedence (protocol §2.5)
- `.codex/` - The Codex adapter: `config.toml`, `agents/` (`explorer`, `worker`), `hooks.json` with `hooks/ddl_gate.py`, `rules/ddl.rules` (protocol §2.5), when copied into the project; with the user-level install `agents/`, `hooks/ddl_gate.py`, and `rules/ddl.rules` are symlinked under `$HOME/.codex/`, the hooks are merged into `$HOME/.codex/hooks.json`, and the `config.toml` cap is set by hand

## Detection Targets

Every skill defines its own D-targets (D1, D2, …). Cross-cutting targets below apply globally.

+++DETECT:
  G1: Vague Intent — Task description lacks measurable outcome
  G2: Scope Creep — Change touches files outside stated scope
  G3: Principle Violation — Action contradicts design.md principles
  G4: Missing Validation — No verification step after mutation
  G5: Leaked Specifics — Project-specific paths/commands hardcoded in framework files
  G6: Silent Failure — Error swallowed without user notification
  G7: Unreviewed Mutation — Shared artifact changed without +++STOP

## Behavior

### On session start

1. This file is already in context: Codex reads the `AGENTS.md` chain before any work. Read it again only when it is no longer in context (after a compaction)
2. `design.md` is injected at session start and after a compaction by the adapter's SessionStart hook when the hooks are trusted; otherwise read `design.md` if it exists. Extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates when present. It stays in context; skills re-read it only when it is no longer in context, and an agent reads only the sections its prompt names
3. The DDL protocol loads when a skill runs (Phase 0, lookup order in protocol §2.5), not at session start
4. Memories are a recall layer: a decision found only there is a proposal until design.md records it

### On any task

1. Identify which scopes (from `design.md`) are affected
2. Run the skill's Phase sequence
3. Scan for Detection Targets at each phase boundary

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next skill if applicable (`$draft` → `$realize` → `$reflect`)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from design.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Spawn agents when a SWARM has fewer than 2 units (scopes, Direction lanes, files, document pairs, approved changes; protocol §2.3) — for 2+, follow +++SWARM semantics (mandatory when condition is true; only the lead fans out; runtime mapping in protocol §2.5)
+++NEVER: Add AI attribution to commits or generated code
+++NEVER: Skip emitting +++DDL_PHASE before mutation — Codex's execution-forward bias must be visibly checkpointed
+++NEVER: Output a +++STOP gate without +++DDL_REPORT followed by the +++Report: table, or a brief finding when the phase defines none
