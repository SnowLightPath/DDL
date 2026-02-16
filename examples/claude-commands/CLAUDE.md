# Project Name

## Protocol

→ DDL-PROTOCOL
→ Read `.claude/commands/DDL-PROTOCOL-SKILL.md` before executing any command

## Commands

| Command | Intent |
|---------|--------|
| `/draft` | Write the user-side experience first |
| `/realize` | Write code based on design principles |
| `/reflect` | Update documents based on implementation |
| `/commit` | Git commit |
| `/docs` | Audit and fix documentation |
| `/refactoring` | Audit and fix code quality |

## Structure

- `design.md` - Design Document

## Detection Targets

Every command defines its own D1–D7. Cross-cutting targets below apply globally.

+++DETECT:
  D1: Vague Intent — Task description lacks measurable outcome
  D2: Scope Creep — Change touches files outside stated scope
  D3: Principle Violation — Action contradicts design.md principles
  D4: Missing Validation — No verification step after mutation
  D5: Leaked Specifics — Project-specific paths/commands hardcoded in framework files
  D6: Silent Failure — Error swallowed without user notification
  D7: Unreviewed Mutation — Shared artifact changed without +++STOP

## Behavior

### On session start

1. Read `CLAUDE.md` (this file)
2. Read `design.md` if it exists — extract scopes, principles, validation commands

### On any task

1. Identify which scopes (from `design.md`) are affected
2. Run the command's Phase sequence
3. Scan for Detection Targets at each phase boundary

+++NEVER: Skip a +++STOP

### On swarm

+++SWARM: 2+ independent scopes exist
  spawn: {role}-{scope}
  each: read only its assigned scope

- Lead integrates results and runs cross-scope analysis
- Prefer parallel batches over sequential execution

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next command if applicable (`/draft` → `/realize` → `/reflect`)

## Constraints

+++NEVER: Hardcode paths — scopes come from design.md
+++NEVER: Hardcode commands — validation commands come from design.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Spawn agents for single-scope tasks — swarm is optional
+++NEVER: Add AI attribution to commits or generated code
