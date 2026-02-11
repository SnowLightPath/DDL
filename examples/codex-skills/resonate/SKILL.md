---
name: resonate
description: Synchronize multilingual document versions
metadata:
  short-description: Sync multilingual docs
---

# resonate

Synchronize multilingual document versions.

## Usage

- `$resonate <path>` — Sync documents at path

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — identify multilingual document pairs
3. Discover language counterparts in target path

### Phase 1: READ

For each language version, sequentially parse and extract section structure and content.

### Phase 2: COMPARE

Section-by-section comparison across language pairs:

1. Align sections by heading structure
2. Identify dissonance per section

Run Detection Target scan:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Missing Nuance | Translation loses meaning present in source |
| D2 | Different Emphasis | Section weight or tone differs between languages |
| D3 | Structural Mismatch | Heading hierarchy or section order differs |
| D4 | Untranslated Section | Section exists in one language but not the other |
| D5 | Stale Translation | Source updated after translation was last changed |

### Phase 3: REPORT

**STOP gate** — Present dissonance table to user. Do NOT apply changes without approval.

### Phase 4: APPLY

Apply approved changes to BOTH language versions.

## Constraints

- Proposals refine BOTH versions — neither language is strictly "source"
- Never auto-apply — STOP gate is mandatory
