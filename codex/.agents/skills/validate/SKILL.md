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

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, the Validation block, and the mechanical gates (commands) listed in Acceptance Gates
4. If no `design.md` exists → refuse ("Declare scopes and a Validation block in design.md first")
5. If a scope is given, validate only that scope

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

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

Mechanical gates from Acceptance Gates that name no scope are run by the lead and reported as named results.

Mark a check PASS only from an observed command result: its exit code and, when declared, its expected output must match. A failed worker launch, empty response, or absent result leaves the check NOT RUN. Run that check in the lead when possible and report the sequential fallback; otherwise report the blocker. Do not turn a worker or host failure into a validation success.

+++DETECT:
  D1: Silenced Failure — A missing result, non-zero exit code, or output other than the expected value declared with the command is reported as PASS
  D2: Out-of-scope Validation — Validation touches files outside the declared scope
  D3: Design-Validation Drift — Validation command in design.md fails to execute (missing binary, invalid syntax)
  D4: Timeout Ignored — Validation hung or timed out without surfacing
  D5: Hardcoded Path — Validator embeds project paths instead of reading from design.md

### Phase 2: REPORT

+++STOP: always

Emit `+++DDL_REPORT`, then report the results without auto-fixing. If a next action needs a decision, follow Approval before asking; an informational report still emits the marker and ends the turn without asking for approval.

+++Report:
Outcome: the overall PASS/FAIL result and every unresolved failure or blocker, without a full command inventory in the main report.
Recommendation: the next command selected below with a short reason, or, when every check passes, that nothing remains.
Consequence: choosing that command starts its workflow, not an automatic fix or a waiver of its approval gates; when nothing remains, no choice is offered.
Review detail: each scope or gate's Validation Command, Status, exit code and Output Excerpt, with the corresponding detection code where applicable.
Choices: when next direction is needed, request it for the complete proposed next action through Approval, without per-check approval; otherwise state that no approval is required and end the turn.

If any FAIL or detection target fired, list it explicitly with the corresponding D-code.
Choose the suggested next command before emitting the STOP report — `$validate` itself never edits:
lint / format / style failures → `$refactoring`; design-validation drift (D3) → `$reflect`;
validation references unimplemented design → `$realize`; all PASS → no next command: state that nothing remains.

## Constraints

+++NEVER: Edit files during $validate — it is read-only; only the declared commands write, and only their own caches and build output
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Auto-proceed past +++STOP — wait for user direction, even when every check passes
