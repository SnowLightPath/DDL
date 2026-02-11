# Project Name

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

- `DESIGN.md` - Design Document

## Detection Targets

Every command defines its own D1–D7. Cross-cutting targets below apply **globally**.

| ID | Name | Trigger |
|----|------|---------|
| D1 | Vague Intent | Task description lacks measurable outcome |
| D2 | Scope Creep | Change touches files outside stated scope |
| D3 | Principle Violation | Action contradicts `DESIGN.md` principles |
| D4 | Missing Validation | No verification step after mutation |
| D5 | Leaked Specifics | Project-specific paths/commands hardcoded in framework files |
| D6 | Silent Failure | Error swallowed without user notification |
| D7 | Unreviewed Mutation | Shared artifact changed without STOP gate |

## Behavior

### On session start

1. Read `CLAUDE.md` (this file)
2. Read `DESIGN.md` if it exists — extract scopes, principles, validation commands

### On any task

1. Identify which scopes (from `DESIGN.md`) are affected
2. Run the command's Phase sequence
3. Scan for Detection Targets at each phase boundary
4. Never skip a STOP gate

### On swarm

- Spawn agents only when 2+ independent scopes exist
- Agent naming: `{role}-{scope}` (e.g., `survey-backend`, `scanner-docs`)
- Each agent reads only its assigned scope
- Lead integrates results and runs cross-scope analysis
- Prefer parallel batches over sequential execution

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next command if applicable (`/draft` → `/realize` → `/reflect`)

## Constraints

- **No hardcoded paths** — scopes come from `DESIGN.md`
- **No hardcoded commands** — validation commands come from `DESIGN.md`
- **STOP gates are blocking** — never auto-proceed past a STOP gate
- **Swarm is optional** — single-scope tasks run without spawning agents
- **Attribution** — never add AI attribution to commits or generated code
