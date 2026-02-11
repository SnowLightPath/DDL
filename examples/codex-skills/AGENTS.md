# DDL Repository

## Skills

| Skill | Intent |
|-------|--------|
| `$draft` | Write the user-side experience first |
| `$realize` | Write code based on design principles |
| `$reflect` | Update documents based on implementation |
| `$commit` | Git commit |
| `$docs` | Audit and fix documentation |
| `$refactoring` | Audit and fix code quality |

## Structure

- `DESIGN.md` - Design principles (temporary)

## Detection Targets

Every skill defines its own D1–D7. Cross-cutting targets below apply **globally**.

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

### Execution model

Codex processes all scopes **sequentially** (one at a time). When multiple scopes are defined in `DESIGN.md`, iterate through them in order. There is no parallel agent spawning.

### On session start

1. Read `AGENTS.md` (this file)
2. Read `DESIGN.md` if it exists — extract scopes, principles, validation commands

### On any task

1. Identify which scopes (from `DESIGN.md`) are affected
2. Run the skill's Phase sequence, processing each scope sequentially
3. Scan for Detection Targets at each phase boundary
4. Never skip a STOP gate

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next skill if applicable (`$draft` → `$realize` → `$reflect`)

## Constraints

- **No hardcoded paths** — scopes come from `DESIGN.md`
- **No hardcoded commands** — validation commands come from `DESIGN.md`
- **STOP gates are blocking** — never auto-proceed past a STOP gate
- **Attribution** — never add AI attribution to commits or generated code
