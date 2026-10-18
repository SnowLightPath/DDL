# Project Name

## Protocol

→ DDL-PROTOCOL
→ Read the DDL protocol before executing any command, when it is not already in context, in the lookup order of protocol §2.5: repo-local `commands/DDL-PROTOCOL-SKILL.md`, then `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`

## Commands

| Command | Intent |
|---------|--------|
| `/draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `/realize` | Write code based on design principles and Binding Decisions |
| `/reflect` | Update documents based on implementation |
| `/validate` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |
| `/commit` | Git commit (`/commit remote` also pushes) |
| `/docs` | Audit and fix documentation |
| `/refactoring` | Audit and fix code quality |

## Structure

- `design.md` - Project design document (scopes, principles, validation; Experience, Binding Decisions, Direction, Acceptance Gates when drafted — protocol §3)

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
2. Read `design.md` if it exists — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates when present. It stays in context; commands re-read it only after a compaction, and a worker reads only the sections its prompt names
3. The DDL protocol loads when a command runs (Phase 0, lookup order in protocol §2.5), not at session start
4. Automatic memory is a recall layer: a decision found only there is a proposal until design.md records it

### On any task

1. Identify which scopes (from `design.md`) are affected
2. Run the command's Phase sequence
3. Scan for Detection Targets at each phase boundary

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next command if applicable (`/draft` → `/realize` → `/reflect`)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from design.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Spawn agents when a SWARM has fewer than 2 units (scopes, Direction lanes, files, document pairs, approved changes; protocol §2.3) — for 2+, follow +++SWARM semantics (mandatory when condition is true; only the lead fans out; runtime mapping in protocol §2.5)
+++NEVER: Add AI attribution to commits or generated code
