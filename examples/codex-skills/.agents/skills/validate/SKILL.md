---
name: validate
description: Run mechanical validation per scope as declared in DESIGN.md
metadata:
  short-description: Mechanical validation gate
---

# validate

Run mechanical validation per scope as declared in DESIGN.md.

## Usage

- `$validate` — Validate every scope in DESIGN.md
- `$validate <scope>` — Validate a single scope by name

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes and the Validation block
3. If no `DESIGN.md` exists → refuse ("Run `$draft` first to declare scopes and validation")

### Phase 1: SCAN

+++SWARM: 2+ scopes in DESIGN.md

```
  team: validate-scan
  spawn: validator-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Run the validation commands for {scope} as declared in DESIGN.md.
    Capture exit code, stderr, stdout. Do not modify any files.
    Report PASS / FAIL plus a short output excerpt to team-lead when done.
  collect: lead aggregates per-scope results into a PASS/FAIL matrix
```

+++DETECT:
  D1: Silenced Failure — Non-zero exit code reported as PASS
  D2: Out-of-scope Validation — Validation touches files outside the declared scope
  D3: Design-Validation Drift — Validation command in DESIGN.md fails to execute (missing binary, invalid syntax)
  D4: Timeout Ignored — Validation hung or timed out without surfacing
  D5: Hardcoded Path — Validator embeds project paths instead of reading from DESIGN.md

### Phase 2: REPORT

+++STOP: always

Emit `+++DDL_REPORT` as the section heading (Codex Runtime Contract), then output the table below. Do not auto-fix.

+++Report:
| # | Scope | Validation Command | Status | Output Excerpt |
|---|-------|--------------------|--------|---------------|

If any FAIL or detection target fired, list it explicitly with the corresponding D-code.

### Phase 3: SUGGEST

If any FAIL, suggest the next skill to run — `$validate` itself never edits:

- Lint / format / style failures → `$refactoring`
- Design-Validation drift (D3) → `$reflect`
- Validation references unimplemented design → `$realize`
- All PASS → suggest `$commit`

## Constraints

+++NEVER: Modify files during $validate — it is read-only
+++NEVER: Hardcode validation commands — they come from DESIGN.md
+++NEVER: Auto-proceed past +++STOP after FAIL — wait for user direction
