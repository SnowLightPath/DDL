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

1. Read `AGENTS.md` — Directive Reference, Codex Runtime Contract, +++SWARM Execution, and DESIGN.md Sections
2. Read `DESIGN.md` — extract scopes, the Validation block, and the mechanical gates (commands) listed in Acceptance Gates
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
    Run the validation commands for {scope} as declared in DESIGN.md, including mechanical gates in Acceptance Gates that name {scope}.
    Capture exit code, stderr, stdout. Do not modify any files.
    Report PASS / FAIL plus a short output excerpt to the lead when done.
  collect: lead aggregates per-scope results into a PASS/FAIL matrix
```

Mechanical gates from Acceptance Gates that name no scope are run by the lead and reported as their own rows.

+++DETECT:
  D1: Silenced Failure — Non-zero exit code, or output other than the expected value declared with the command, reported as PASS
  D2: Out-of-scope Validation — Validation touches files outside the declared scope
  D3: Design-Validation Drift — Validation command in DESIGN.md fails to execute (missing binary, invalid syntax)
  D4: Timeout Ignored — Validation hung or timed out without surfacing
  D5: Hardcoded Path — Validator embeds project paths instead of reading from DESIGN.md

### Phase 2: REPORT

+++STOP: always

Emit `+++DDL_REPORT` as the section heading, then output the table below. Do not auto-fix.

+++Report:
| # | Scope | Validation Command | Status | Output Excerpt | Suggested Next Command |
|---|-------|--------------------|--------|----------------|------------------------|

If any FAIL or detection target fired, list it explicitly with the corresponding D-code.
Choose the suggested next command before emitting the STOP report — `$validate` itself never edits:
lint / format / style failures → `$refactoring`; design-validation drift (D3) → `$reflect`;
validation references unimplemented design → `$realize`; all PASS → `$commit`.

## Constraints

+++NEVER: Modify files during $validate — it is read-only
+++NEVER: Hardcode validation commands — they come from DESIGN.md
+++NEVER: Auto-proceed past +++STOP after FAIL — wait for user direction
