# validate

Run mechanical validation per scope as declared in design.md.

## Usage

- `/validate` — Validate every scope in design.md
- `/validate <scope>` — Validate a single scope by name

## Phases

### Phase 0: INIT

1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `.claude/CLAUDE.md`
3. Read `design.md` — extract scopes and the Validation block
4. If no `design.md` exists → refuse ("Run `/draft` first to declare scopes and validation")

### Phase 1: SCAN

+++SWARM: 2+ scopes in design.md

```
  team: validate-scan
  spawn: validator-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Run the validation commands for {scope} as declared in design.md.
    Capture exit code, stderr, stdout. Do not modify any files.
    Report PASS / FAIL plus a short output excerpt to team-lead when done.
  collect: lead aggregates per-scope results into a PASS/FAIL matrix
```

+++DETECT:
  D1: Silenced Failure — Non-zero exit code reported as PASS
  D2: Out-of-scope Validation — Validation touches files outside the declared scope
  D3: Design-Validation Drift — Validation command in design.md fails to execute (missing binary, invalid syntax)
  D4: Timeout Ignored — Validation hung or timed out without surfacing
  D5: Hardcoded Path — Validator embeds project paths instead of reading from design.md

### Phase 2: REPORT

+++STOP: always

Emit `+++DDL_REPORT` as the section heading, then output the table below. Do not auto-fix.

+++Report:
| # | Scope | Validation Command | Status | Output Excerpt |
|---|-------|--------------------|--------|---------------|

If any FAIL or detection target fired, list it explicitly with the corresponding D-code.

### Phase 3: SUGGEST

If any FAIL, suggest the next DDL command to run — `/validate` itself never edits:

- Lint / format / style failures → `/refactoring`
- Design-Validation drift (D3) → `/reflect`
- Validation references unimplemented design → `/realize`
- All PASS → suggest `/commit`

## Constraints

+++NEVER: Modify files during /validate — it is read-only
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Auto-proceed past +++STOP after FAIL — wait for user direction
