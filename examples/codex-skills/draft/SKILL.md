---
name: draft
description: Write the ideal experience before implementation exists
metadata:
  short-description: Draft ideal experience
---

# draft

Write the ideal experience before implementation exists.

## Usage

- `$draft` — Ask what to build, then draft the usage
- `$draft <feature>` — Draft usage for specific feature

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes and existing principles
3. If no `DESIGN.md` exists → ask user to create one or proceed with defaults

### Phase 1: UNDERSTAND

+++SWARM: 2+ scopes in DESIGN.md

```
  team: draft-survey
  spawn: survey-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for existing behavior, APIs, user touchpoints.
  collect: lead collects survey results into a unified context
```

### Phase 2: DRAFT

1. Ask: "What experience do you want?"
2. Write consumer-side code / usage examples together
3. Do NOT implement yet — experience only
4. Iterate until it feels right

+++DETECT:
  D1: Vague Experience — Draft lacks concrete input/output examples
  D2: Implementation Leak — Draft describes internal mechanics instead of user experience
  D3: Missing Edge Case — No error/empty/boundary states described
  D4: Principle Conflict — Draft contradicts existing DESIGN.md principle
  D5: Orphan Principle — Draft implies a principle not yet in DESIGN.md

+++STOP: on D4

### Phase 3: REPORT

+++STOP: always

1. Present the draft to user for approval

### Phase 4: EXECUTE

1. Save approved experience to `DESIGN.md`
2. Suggest: "Run `$realize` to implement this experience"

## Constraints

+++NEVER: Write implementation code during $draft
+++NEVER: Hardcode scopes — they come from DESIGN.md
+++NEVER: Save draft with unresolved principle conflict
