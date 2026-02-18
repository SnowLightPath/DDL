---
name: realize
description: Write code based on design principles in DESIGN.md
metadata:
  short-description: Design to Code
---

# realize

Manifest design philosophy as working code.

## Usage

- `$realize` — Read `DESIGN.md`, discuss what to build
- `$realize <feature>` — Implement specific feature

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes, principles, validation commands
3. If no `DESIGN.md` exists → refuse ("Run `$draft` first")

### Phase 1: READ

+++SWARM: 2+ scopes in DESIGN.md

```
  team: realize-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Read {scope}, summarize current state vs. design intent.
  collect: lead collects read results into a unified context
```

### Phase 2: IMPLEMENT

+++SWARM: 2+ independent scopes need changes

```
  team: realize-implement
  spawn: impl-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Generate code honoring the principles for {scope}.
  collect: lead verifies each implementation against principles
```

For each change, verify against principles:
- Add rationale as comments where non-obvious

+++DETECT:
  D1: Principle Violation — Code contradicts a DESIGN.md principle
  D2: Ungrounded Feature — Feature exists in code but not in DESIGN.md
  D3: Breaking Change — Public API or behavior changed without design update
  D4: Missing Test — New behavior has no corresponding test
  D5: Hardcoded Value — Magic numbers, secrets, or environment-specific values inline

+++STOP: on D1 (Principle Violation — from Phase 2 DETECT)

### Phase 3: VALIDATE

+++STOP: on D1

Run all validation commands defined in `DESIGN.md`.

### Phase 4: REPORT

+++STOP: always

1. Summarize what was implemented (files, scopes, key decisions)
2. List any Detection Targets that fired and their resolution
3. Suggest: "Run `$reflect` to verify alignment"

## Constraints

+++NEVER: Implement without reading DESIGN.md first
+++NEVER: Hardcode validation commands — they come from DESIGN.md
+++NEVER: Force code against the philosophy — if it is sound, the code follows naturally
