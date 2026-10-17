# realize

Manifest design philosophy as working code.

## Usage

- `/realize` — Read `design.md`, discuss what to build
- `/realize <feature>` — Implement specific feature

## Phases

### Phase 0: INIT

1. Read the DDL protocol for the current runtime: repo-local `commands/DDL-PROTOCOL-SKILL.md` when present; otherwise, in Claude Code, `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`; in Codex, `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md`.
2. Read project-local runtime guidance when present: `AGENTS.md` for Codex, `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, and any applicable command overlay.
3. Read `design.md` — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates for the feature (protocol §3)
4. If no `design.md` exists → refuse ("Run `/draft` first")

### Phase 1: READ

+++SWARM: 2+ scopes in design.md

```
  team: realize-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Read {scope}, summarize current state vs. design intent,
    and report whether the code already satisfies each Binding Decision for {scope}.
    Report findings to the lead when done.
  collect: lead collects read results into a unified context
```

+++STOP: always

Present the implementation plan: files to touch, principles applied, how each Binding Decision is honored, the Direction stage to start from and any planned deviation, and the gates to pass. For each `Unbound:` line marked delegated, state the choice and its reason; for a line marked awaiting choice, list its options and ask the user to pick one. An argument that names a technology different from a Binding Decision on the same topic is shown as a Binding Decision change with the D6 options; approving the plan does not approve that change unless the user says so explicitly. Wait for user approval before entering Phase 2. After approval and before Phase 2, move into `## Binding Decisions` only the delegated lines whose choice the approved plan stated and the lines the user picked, with Source `approved in /realize plan (<date>)`. Per §1.5 of the protocol, this STOP ends the turn — no mutating tool until approval.

### Phase 2: IMPLEMENT

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 1 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 1 and re-emit the plan.

+++SWARM: 2+ independent scopes or Direction lanes need changes

```
  team: realize-implement
  spawn: impl-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Generate code honoring the principles and the Binding Decisions for {scope}.
    Work only on the Direction stage assigned to {scope}; do not start the next stage.
    If the work would violate a principle or a Binding Decision, stop and report it instead of working around it.
    Report completion, and any deviation from Direction, to the lead when done.
  collect: lead verifies each implementation against principles and Binding Decisions
```

Work through the Direction stages in order unless the approved plan says otherwise; the lanes of the current stage count as independent scopes for SWARM. After each stage, run Phase 3 for that stage's mechanical gate, then execute its human gate as a STOP (§1.5), then return here for the next stage. A merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates. Human gates in Acceptance Gates are STOPs at the end of the work.

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

After a stage, run that stage's mechanical gate and the validation commands of the scopes it changed. After the last stage, run all validation commands in `design.md` and the mechanical gates in Acceptance Gates, in parallel. Without Direction, the work is a single stage.

+++DETECT:
  D7: Validation Failure — any validation command or mechanical gate from `design.md` exits non-zero, cannot run, prints other than the expected value declared with it, or reports an unresolved failure

+++STOP: on D7

### Phase 4: REPORT

+++STOP: always

+++Report:
| Item | Content |
|------|---------|
| Implemented | {files, scopes, key decisions} |
| Binding Decisions | {honored, or changed with the user's approval} |
| Direction | {stages done; deviations and why} |
| Gates | {mechanical results; human gates passed; advance-approved gates and what each would have shown} |
| Detection | {targets that fired and their resolution} |

Suggest: "Run `/reflect` to verify alignment"

## Constraints

+++NEVER: Implement without reading design.md first
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Force code against the philosophy — if it is sound, the code follows naturally
+++NEVER: Change a Binding Decision without the user's approval
