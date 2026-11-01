---
name: realize
description: Write code based on design principles and Binding Decisions in design.md
metadata:
  short-description: Design to Code
---

# realize

Manifest design philosophy as working code.

## Usage

- `$realize` — Read `design.md`, discuss what to build
- `$realize <feature>` — Implement specific feature

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex).
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates for the feature (protocol §3)
4. If no `design.md` exists → refuse ("Run `$draft` first")

### Phase 1: READ

+++SWARM: 2+ scopes in design.md

```
  team: realize-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Read {scope}, summarize its current state against the Experience items and principles in this prompt,
    and report whether the code already satisfies each Binding Decision for {scope}.
    Report findings to the lead when done.
  collect: lead collects read results into a unified context
```

+++STOP: always

Lead with the decision to implement the proposed plan, the recommended approach and reason, and what approval authorizes (protocol §1.5). Make the files to touch, principles applied, how each Binding Decision is honored, the Direction stage to start from and any planned deviation, and the gates to pass available as review detail before approval. For each `Unbound:` line marked delegated, state the choice and its reason; for a line marked awaiting choice, present its options one decision at a time. An argument that names a technology different from a Binding Decision on the same topic is shown as a separate Binding Decision change with the D6 options; approving the plan does not approve that change unless the user says so explicitly. Wait for user approval before entering Phase 2. Execute this STOP through the native choice and waiting procedure of protocol §1.5; request receipt never authorizes implementation.

### Phase 2: IMPLEMENT

**Pre-condition.** Enter this phase only after explicit user approval at the STOP that preceded it: the Phase 1 plan on first entry, later a stage's human gate, a D1 or D6 STOP, or a D7 STOP from Phase 3 (per §1.5 of the protocol). If the actual answer does not authorize the proposed scope, return to the phase whose STOP is pending and re-present its current decision.

On first entry, move into `## Binding Decisions` only the delegated `Unbound:` lines whose choice the approved plan stated and the lines the user picked, with Source `approved in $realize plan (<date>)`; write the plan's durable parts under `## Direction` as `Approved plan (<date>)` (protocol §3). Whenever the user approves gates in advance, at the plan or at a later STOP, write `approved in advance (<date>)` after each such gate at once (protocol §3).

+++SWARM: 2+ independent scopes or Direction lanes need changes

```
  team: realize-implement
  spawn: impl-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Follow the approved plan in this prompt. Generate code honoring the principles and the Binding Decisions for {scope}.
    Work only on the Direction stage assigned to {scope}; do not start the next stage.
    If the work would violate a principle or a Binding Decision, stop and report it instead of working around it.
    Report completion, and any deviation from Direction, to the lead when done.
  collect: lead verifies each implementation against principles and Binding Decisions
```

Work through the Direction stages in order unless the approved plan says otherwise; the lanes of the current stage count like scopes for SWARM (§2.3 of the protocol). After each stage, run Phase 3 for that stage's mechanical gate, then execute its human gate as a STOP (§1.5); after approval, return here for the next stage, or to Phase 3's final checks after the last stage. Mark each gate that passes in `design.md`, and keep the gates of a merged, skipped, or reordered stage, as protocol §3 says. Human gates in Acceptance Gates run at the end of the work (Phase 3).

For each change, verify against principles and Binding Decisions:
- Add rationale as comments where non-obvious
- Record every deviation from Direction (merged, reordered, or skipped stage) for the report

+++DETECT:
  D1: Principle Violation — Code contradicts a design.md principle
  D2: Ungrounded Feature — Feature exists in code but not in design.md
  D3: Breaking Change — Public API or behavior changed without design update
  D4: Missing Test — New behavior has no corresponding test
  D5: Hardcoded Value — Magic numbers, secrets, or environment-specific values inline
  D6: Binding Violation — The implementation would replace, bypass, or contradict a Binding Decision, or the reason a Binding Decision gives no longer holds

If D1 or D6 fires, stop before continuing implementation. For D6, present options: keep the decision and change the approach, change the environment, change the Experience, or change the Binding Decision. Only the user chooses, and only the user changes a Binding Decision.

+++STOP: on D1
+++STOP: on D6

### Phase 3: VALIDATE

After a stage, run that stage's mechanical gate and the validation commands of the scopes it changed. After the last stage, run all validation commands in `design.md` and the mechanical gates in Acceptance Gates, in parallel, and mark the gates that pass (protocol §3). Then execute each human gate in Acceptance Gates as a STOP (§1.5) unless the user approved it in advance; after approval, mark it passed and enter Phase 4. Without Direction, the work is a single stage. When D7 fires, STOP below; after approval, return to Phase 2 to fix what failed, then run this phase again.

+++DETECT:
  D7: Validation Failure — any validation command or mechanical gate from `design.md` exits non-zero, cannot run, prints other than the expected value declared with it, or reports an unresolved failure

+++STOP: on D7

### Phase 4: REPORT

+++STOP: always

+++Report:
Outcome: what now works, what remains unresolved, and whether any user decision is needed.
Recommendation: `$reflect` to verify alignment, with a short reason when asking for that next direction.
Consequence: selecting the next command starts its workflow; it does not approve unreviewed changes or waive its STOPs.
Review detail: implemented files/scopes and key decisions; Binding Decisions honored or explicitly changed; Direction stages and deviations; mechanical results and actual human gates passed; advance-approved gates and what each would have shown; detections and their resolution. Distinguish native checks from simulated checks and unverified behavior.
Choices: ask for next direction only if a decision is needed, following protocol §1.5. Do not ask the user to approve work already completed.

## Constraints

+++NEVER: Implement without reading design.md first
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Force code against the philosophy — if it is sound, the code follows naturally
+++NEVER: Change a Binding Decision without the user's approval
