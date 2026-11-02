---
name: realize
description: Write code based on design principles and Binding Decisions in design.md, and close the work with one Git review
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

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates for the feature (Notebook)
4. If no `design.md` exists → refuse ("Run `$draft` first")

Read the Notebook operation for the section rules.

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

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

Lead with the decision to implement the complete proposed plan, the recommended approach and reason, and what approval authorizes (Approval). Make the files to touch, principles applied, how each Binding Decision is honored, the Direction stage to start from and any planned deviation, and the gates to pass available as review detail before approval. For each `Unbound:` line marked delegated, state the choice and its reason. Group lines awaiting choice into compatible complete plan options, or leave the unresolved portion pending; do not start a serial approval sequence. An argument that names a technology different from a Binding Decision on the same topic is shown as a separately identified Binding Decision change with the D6 options; approving the plan does not approve that change unless the user explicitly selects an action naming it. Request one batch approval to implement all displayed recommendations, select or revise the plan, or hold. After approval, do not ask again per file, task, or resolved choice; later STOPs still apply. Wait for actual approval before entering Phase 2 through Approval Operation steps 2 and 3 (Ask; Wait and resume); request receipt never authorizes implementation. The plan ends with the Close stage (Close): when Direction lacks one, add it as the final stage, and state the commit and, when the user asked for it, the `remote` push that its Git review will cover.

### Phase 2: IMPLEMENT

**Pre-condition.** Enter this phase only after explicit user approval at the STOP that preceded it: the Phase 1 plan on first entry, later a stage's human gate, a D1 or D6 STOP, or a D7 STOP from Phase 3 (per Approval). If the actual answer does not authorize the proposed scope, return to the phase whose STOP is pending and re-present its current decision.

For planned equivalent alignment of Scopes or Validation before a stage gate, follow Notebook.

On first entry, move into `## Binding Decisions` only the delegated `Unbound:` lines whose choice the approved plan stated and the lines the user picked, with Source `approved in /realize plan (<date>)`; write the plan's durable parts under `## Direction` as `Approved plan (<date>)` (Notebook), including the Close stage when the plan added it. Whenever the user approves gates in advance, at the plan or at a later STOP, write `approved in advance (<date>)` after each such gate at once (Notebook).

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

Work through the Direction stages in order unless the approved plan says otherwise; the lanes of the current stage count like scopes for SWARM (Parallel work). After each stage, run Phase 3 for its mechanical gates, then review all compatible human gates ready at that boundary in one STOP batch (Approval); after approval, return here for the next stage. After the last implementation stage, complete Phase 3's checks and include its ready human gates with those in Acceptance Gates in one review; then enter Phase 4 CLOSE. Its normal path ends with one Git review; a human gate explicitly written into the approved Close stage and any triggered detection STOP still apply. Mark each gate that passes in `design.md`, and keep the gates of a merged, skipped, or reordered stage, as Notebook says. Do not delay a prerequisite gate for evidence that belongs to a later stage.

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

After a stage, run that stage's mechanical gate and the validation commands of the scopes it changed. After the last stage, run all validation commands in `design.md` and the mechanical gates in Acceptance Gates, in parallel, and mark the gates that pass (Notebook). Then combine all compatible ready human gates from the last stage and Acceptance Gates into one named STOP review set (Approval), excluding gates approved in advance. One submitted batch approval passes the named gates; mark each approved gate passed and enter Phase 4 without per-gate questions. Without Direction, the work is a single stage followed by Close. Phase 4 runs the validation commands and mechanical gates again after the Close edits. When D7 fires, STOP below; after approval, return to Phase 2 to fix what failed, then run this phase again.

+++DETECT:
  D7: Validation Failure — any validation command or mechanical gate from `design.md` exits non-zero, cannot run, prints other than the expected value declared with it, or reports an unresolved failure

+++STOP: on D7

### Phase 4: CLOSE

On entry, read the Close operation.

Enter this phase only when the approved plan includes the Close stage (approved at the Phase 1 STOP) and every earlier stage's gates are marked passed; a D1, D6, or D7 STOP on the way returns to the phase whose decision is pending. Run the Close stage as Close defines, in order:

1. Reflect: compare the code with design.md; add the Experience the code revealed, check every Binding Decision, replace the Direction stages whose gates are all marked passed (including this work's own stages) with their outcome and delete their `Approved plan` lines, retire Acceptance Gates whose gates are all marked passed after moving continuing mechanical gates into Validation, and correct Scopes and Validation. Write design.md as it will read after the commit; the Git review in Phase 5 is the gate that records it. A Binding Drift is D6: stop as in Phase 2
2. Docs: audit and fix the documentation the change set touches
3. Resonate: align every changed document with its language counterpart, including dated Changelog rows where the project keeps them
4. Validate: run all validation commands in `design.md` and the mechanical gates in Acceptance Gates again; D7 stops as in Phase 3
5. Read the Git review operation and its implementation for the current host, stage the whole change set (implementation, design.md, documents), then prepare the Git review for the commit and for the push when the plan names `remote`; a commit precedes its push in the review

Apply steps 1–3 with a SWARM shaped like Phase 2's, team `realize-close`, when 2+ scopes change; the lead performs the comparison, the validation, and the review preparation.

### Phase 5: REVIEW

+++STOP: always

+++Report:
Decision: record the closed work as the prepared Git review, revise it, or hold.
Recommendation: the purpose of the change set and why its implementation, design.md, and documentation changes belong in one commit; keep material detections visible.
Consequence: commit exactly the staged set with the exact message; the push, when the plan named `remote`, is part of the same selected action. A hold or revision records nothing and leaves the Close edits in the working tree for revision.
Review detail: the prepared review ID and the link to its complete report and diff; the complete file list and scopes; the exact message; a summary of the design.md changes (Experience added, stages and gates retired, Validation updated) and of the documentation changes; every material detection.
Choices: use the prepared native question and its exact action labels for one whole-set approval (Git review). Approval of a different file set, message, or push target is not approval of this proposal.

### Phase 6: RECORD

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 5 STOP gate (per Approval). If the actual answer does not authorize this work, return to Phase 5 and re-present the current decision.

1. Keep the reviewed index intact; do not restage newer working-tree contents after approval
2. Verify that the staged set, contents, base, and message still match the prepared review; if they differ, rebuild the review and return to Phase 5
3. Re-run the secret scan against the exact staged content

+++DETECT:
  D8: Secret Leak — a file the commit would include contains an API key, token, or credential
  D9: Git Review Mismatch — the prepared review, native submitted answer, staged contents, message, or destination cannot be matched

+++STOP: on D8
+++STOP: on D9

4. Create the reviewed commit with the approved verbatim message in the supported ordinary form (Git review Operands), then push only the reviewed operation when the plan named `remote`
5. Report the commit hash and the push result as progress

### Phase 7: REPORT

+++STOP: always

+++Report:
Outcome: the commit (and push) that closed the work, what now works, and either that nothing remains or what was left with its reason (for example a Binding Drift awaiting the user's choice).
Recommendation: none after a Close; name a next command only when work this command cannot do itself remains, with the reason (Approval).
Consequence: this report asks for no approval; a named leftover starts its own workflow only when the user chooses it.
Review detail: implemented files/scopes and key decisions; Binding Decisions honored or explicitly changed; Direction stages and deviations; mechanical results and actual human gates passed; advance-approved gates and what each would have shown; the Close changes recorded; detections and their resolution. Distinguish native checks from simulated checks and unverified behavior.
Choices: none; state that no approval is needed and end the turn.

## Constraints

+++NEVER: Implement without reading design.md first
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Force code against the philosophy — if it is sound, the code follows naturally
+++NEVER: Change a Binding Decision without the user's approval
+++NEVER: Suggest a next command after the Close stage — state that nothing remains, or name what was left with its reason
