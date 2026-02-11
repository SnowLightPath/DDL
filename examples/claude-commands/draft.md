# draft

Write the ideal experience before implementation exists.

## Usage

- `/draft` — Ask what to build, then draft the usage
- `/draft <feature>` — Draft usage for specific feature

## Phases

### Phase 0: INIT

1. Read `CLAUDE.md`
2. Read `DESIGN.md` — extract scopes and existing principles
3. If no `DESIGN.md` exists → ask user to create one or proceed with defaults

### Phase 1: UNDERSTAND

**Swarm trigger**: 2+ scopes in `DESIGN.md`

- Spawn `survey-{scope}` agents in parallel
- Each agent: scan its scope for existing behavior, APIs, user touchpoints
- Single scope: run inline without spawning

Collect survey results into a unified context.

### Phase 2: DRAFT

1. Ask: "What experience do you want?"
2. Write consumer-side code / usage examples together
3. Do NOT implement yet — experience only
4. Iterate until it feels right
5. Run Detection Target scan (parallel):

| ID | Name | Trigger |
|----|------|---------|
| D1 | Vague Experience | Draft lacks concrete input/output examples |
| D2 | Implementation Leak | Draft describes internal mechanics instead of user experience |
| D3 | Missing Edge Case | No error/empty/boundary states described |
| D4 | Principle Conflict | Draft contradicts existing `DESIGN.md` principle |
| D5 | Orphan Principle | Draft implies a principle not yet in `DESIGN.md` |

### Phase 3: SAVE

1. **STOP gate** — Present the draft to user for approval
2. Save approved experience to `DESIGN.md`
3. Suggest: "Run `/realize` to implement this experience"

## Constraints

- Never write implementation code during `/draft`
- Scopes come from `DESIGN.md`, not hardcoded paths
- If D4 fires → stop and resolve conflict before saving
