---
name: validate
description: Run mechanical validation per scope as declared in design.md
metadata:
  short-description: Mechanical validation gate
---

# validate

Run mechanical validation per scope as declared in design.md.

## Usage

- `$validate` — Validate every scope in design.md
- `$validate <scope>` — Validate a single scope by name

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex).
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, the Validation block, and the mechanical gates (commands) listed in Acceptance Gates
4. If no `design.md` exists → refuse ("Declare scopes and a Validation block in design.md first")
5. If a scope is given, validate only that scope (§2.3 of the protocol)

### Phase 1: SCAN

+++SWARM: 2+ scopes in design.md

```
  team: validate-scan
  spawn: validator-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Run the validation commands for {scope} listed in this prompt (the Validation block and the mechanical gates in Acceptance Gates that name {scope}).
    Capture exit code, stderr, stdout. Edit no files; the commands may write only their own caches and build output.
    Report PASS / FAIL plus a short output excerpt to the lead when done.
  collect: lead aggregates per-scope results into a PASS/FAIL matrix
```

Mechanical gates from Acceptance Gates that name no scope are run by the lead and reported as their own rows.

+++DETECT:
  D1: Silenced Failure — Non-zero exit code, or output other than the expected value declared with the command, reported as PASS
  D2: Out-of-scope Validation — Validation touches files outside the declared scope
  D3: Design-Validation Drift — Validation command in design.md fails to execute (missing binary, invalid syntax)
  D4: Timeout Ignored — Validation hung or timed out without surfacing
  D5: Hardcoded Path — Validator embeds project paths instead of reading from design.md

### Phase 2: REPORT

+++STOP: always

Report per §1.5 of the protocol with the table below. Do not auto-fix.

+++Report:
| # | Scope | Validation Command | Status | Output Excerpt | Suggested Next Command |
|---|-------|--------------------|--------|----------------|------------------------|

If any FAIL or detection target fired, list it explicitly with the corresponding D-code.
Choose the suggested next command before emitting the STOP report — `$validate` itself never edits:
lint / format / style failures → `$refactoring`; design-validation drift (D3) → `$reflect`;
validation references unimplemented design → `$realize`; all PASS → `$commit`.

## Constraints

+++NEVER: Edit files during $validate — it is read-only; only the declared commands write, and only their own caches and build output
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Auto-proceed past +++STOP — wait for user direction, even when every check passes
