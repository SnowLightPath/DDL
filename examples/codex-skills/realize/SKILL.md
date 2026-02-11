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

For each scope in `DESIGN.md`, sequentially read and summarize current state vs. design intent.

### Phase 2: IMPLEMENT

For each scope that needs changes, sequentially generate code honoring its principles.

For each change, verify against principles:
- If implementation would violate a principle → **STOP**: "Update the principle, or change the approach?"
- Add rationale as comments where non-obvious

### Phase 3: VALIDATE

Run Detection Target scan:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Principle Violation | Code contradicts a `DESIGN.md` principle |
| D2 | Ungrounded Feature | Feature exists in code but not in `DESIGN.md` |
| D3 | Breaking Change | Public API or behavior changed without design update |
| D4 | Missing Test | New behavior has no corresponding test |
| D5 | Hardcoded Value | Magic numbers, secrets, or environment-specific values inline |

**STOP gate on D1**: If Principle Violation detected → halt and present conflict to user.

Run all validation commands defined in `DESIGN.md`.

### Phase 4: REPORT

1. Summarize what was implemented (files, scopes, key decisions)
2. List any Detection Targets that fired and their resolution
3. Suggest: "Run `$reflect` to verify alignment"

## Constraints

- Never implement without reading `DESIGN.md` first
- Validation commands come from `DESIGN.md`, not hardcoded
- If the philosophy is sound, the code follows naturally
