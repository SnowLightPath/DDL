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

- `DESIGN.md` - Design Document

## Directive Reference

| Directive | Syntax | Rule |
|-----------|--------|------|
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | Phase 0 INIT required: load AGENTS.md → DESIGN.md. 4–6 phases per skill |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | `always` required at REPORT phase. Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 5–7 per skill. Run at each phase boundary |
| `+++SWARM` | `+++SWARM: condition` followed by operand block | **Sequential fallback** — see below |
| `+++NEVER` | `+++NEVER: prohibition` | Local constraints per skill |
| `+++Report` | `+++Report:` followed by markdown table rows | Output template presented at STOP gate |

## +++SWARM Execution

When a skill defines `+++SWARM: condition`:

1. Evaluate the condition against `DESIGN.md`
2. If condition is false or single scope → execute `each:` task inline
3. If condition is true with 2+ scopes:

### With multi-agent enabled

When `[agents]` is configured in `.codex/config.toml`:

1. Map the `type:` field to a Codex agent role:
   - `Explore` → `explorer` role (`sandbox_mode = "read-only"`)
   - `general-purpose` → `worker` role (`sandbox_mode = "workspace-write"`)
2. Evaluate scope count against `max:` field to determine concurrency
3. Spawn one agent per scope (or batch when scope count exceeds `max:`)
4. Each agent executes the `each:` task for its assigned scope(s)
5. Lead collects results per the `collect:` field

### Without multi-agent (sequential fallback)

When multi-agent is not enabled:

1. Execute `each:` task **sequentially** for each matching scope
2. The `team:`, `spawn:`, `max:`, `batch:`, `collect:` fields are metadata only — they document what would be parallelized

## Detection Targets

Every skill defines its own D1–D7. Cross-cutting targets below apply **globally**.

+++DETECT:
  G1: Vague Intent — Task description lacks measurable outcome
  G2: Scope Creep — Change touches files outside stated scope
  G3: Principle Violation — Action contradicts `DESIGN.md` principles
  G4: Missing Validation — No verification step after mutation
  G5: Leaked Specifics — Project-specific paths/commands hardcoded in framework files
  G6: Silent Failure — Error swallowed without user notification
  G7: Unreviewed Mutation — Shared artifact changed without +++STOP

## Behavior

### On session start

1. Read `AGENTS.md` (this file)
2. Read `DESIGN.md` if it exists — extract scopes, principles, validation commands

### On any task

1. Identify which scopes (from `DESIGN.md`) are affected
2. Run the skill's Phase sequence
3. Scan for Detection Targets at each phase boundary
4. Never skip a STOP gate

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next skill if applicable (`$draft` → `$realize` → `$reflect`)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from DESIGN.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Add AI attribution to commits or generated code
