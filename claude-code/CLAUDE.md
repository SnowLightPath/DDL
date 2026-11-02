# Project Name

## Protocol

→ DDL-PROTOCOL
→ Read the DDL protocol before executing any command, when it is not already in context, in this lookup order: the project's copy `.claude/skills/ddl-protocol/SKILL.md`, then the user-level copy `$HOME/.claude/skills/ddl-protocol/SKILL.md`

## Notebook

@../design.md

The line above imports `design.md` into this file, so the notebook is in context from session start and after a compaction (Claude Code adapter, the protocol’s runtime guidance). A project with a root `CLAUDE.md` writes `@design.md`; a project whose notebook is another file (the protocol’s Notebook feature) points the line at that file.

## Commands

| Command | Intent |
|---------|--------|
| `/draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `/realize` | Write code based on design principles and Binding Decisions, then close the work with one Git review |
| `/reflect` | Update documents based on implementation |
| `/validate` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |
| `/resonate` | Sync multilingual docs (en/ja) |
| `/commit` | Close the work and commit (`/commit remote` also pushes) |
| `/docs` | Audit and fix documentation |
| `/refactoring` | Audit and fix code quality |

## Structure

- `design.md` - Project design document (scopes, principles, validation; Experience, Binding Decisions, Direction, Acceptance Gates when drafted — the protocol’s Notebook feature)
- `.claude/skills/<name>/SKILL.md` - The DDL command skills and the protocol skill `ddl-protocol` (the frontmatter keeps Claude Code from starting a command on its own; a command runs on `/name`), when DDL is copied into the project; with the user-level install they live in `$HOME/.claude/skills/` and a project copy, when present, takes precedence (the protocol’s runtime guidance)
- `.claude/skills/ddl-protocol/references/` - Focused protocol feature and runtime guidance, read when needed from the selected protocol
- `.claude/settings.json`, `.claude/agents/`, `.claude/hooks/` - The Claude Code adapter (the gate hook and its wiring, the `explorer` and `worker` definitions; the protocol’s runtime guidance), when copied into the project; with the user-level install `agents/` and `hooks/` are symlinked under `$HOME/.claude/` and the settings fragment is merged into `$HOME/.claude/settings.json`

## Detection Targets

Every command defines its own D-targets (D1, D2, …). Cross-cutting targets below apply globally.

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

1. This file is already in context: Claude Code loads `CLAUDE.md` or `.claude/CLAUDE.md` at session start and re-injects it after compaction. Do not read it again
2. `design.md` loads with this file through the adapter's import (the protocol’s runtime guidance); when the import is unavailable, read `design.md` if it exists. Extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates when present. It stays in context; commands re-read it only when it is no longer in context after a compaction, and a worker reads only the sections its prompt names
3. The DDL protocol loads when a command runs (Phase 0, the project copy before the user-level copy), not at session start
4. Automatic memory is a recall layer: a decision found only there is a proposal until design.md records it

### On any task

1. Identify which scopes (from `design.md`) are affected
2. Run the command's Phase sequence
3. Scan for Detection Targets at each phase boundary

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. After a Close stage (the protocol’s Close feature), state that nothing remains; otherwise name a next command only when work this command cannot do remains, with the reason (`/draft` ends by naming `/realize`; `/realize` ends with Close)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from design.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Spawn agents when a SWARM has fewer than 2 units (scopes, Direction lanes, files, document pairs, approved changes; the protocol’s Parallel work feature) — for 2+, follow +++SWARM semantics (mandatory when condition is true; only the lead fans out; runtime mapping in the protocol)
+++NEVER: Add AI attribution to commits or generated code
