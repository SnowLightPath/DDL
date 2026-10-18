# draft

Write the ideal experience before implementation exists, together with the decisions and outlook that the experience cannot be separated from.

## Usage

- `/draft` — Ask what to build, then draft the usage
- `/draft <feature>` — Draft usage for specific feature
- `/draft <feature> <technology or outlook>` — Same, with a technology the experience depends on (framework, language, platform, software) or an outlook on the path to implementation; /draft sorts them into the right sections

## Phases

### Phase 0: INIT

1. Read the DDL protocol for the current runtime when it is not already in context: repo-local `commands/DDL-PROTOCOL-SKILL.md` when present; otherwise, in Claude Code, `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`; in Codex, `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md`.
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, existing principles, and any Experience, Binding Decisions, Direction, and Acceptance Gates (protocol §3)
4. If no `design.md` exists → ask user to create one or proceed with defaults

### Phase 1: UNDERSTAND

+++SWARM: 2+ scopes in design.md

```
  team: draft-understand
  spawn: survey-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for existing behavior, APIs, user touchpoints,
    and the technology it already depends on (manifests, lockfiles, config, entry points).
    Report findings to the lead when done.
  collect: lead collects survey results into a unified context and lists existing technology as premises
```

### Phase 2: DRAFT

1. If the request does not already describe the experience, ask: "What experience do you want?"
2. Sort what the user said into the sections of protocol §3, then ask only for what is missing. Experience is always needed; Binding Decisions, Direction, and Acceptance Gates are optional, so ask about them only when the user's words point to them:
   - **Experience** — consumer-side usage with concrete inputs and outputs, including error, empty, and boundary states
   - **Binding Decisions** — a technology the user fixes because the experience depends on it, an external constraint requires it, or the user states a preference for it. Record the Decision, Why it binds, and the Source (the user's words with the date, or the user's approval of the report that listed it; protocol §3). If the user gave no reason, ask once; without an answer, list it as Unbound (protocol §3)
   - **Direction** — the user's outlook on the path to implementation: stage order, parallel lanes, what to show the user when, and human gates. Non-binding
   - **Acceptance Gates** — what must hold when done: mechanical gates (commands, each with its expected result when exit code alone cannot show failure) and human gates (approvals)
3. Write consumer-side code / usage examples together, in the language and on the platform the Binding Decisions name. For a library or SDK, the consumer-side language is part of the Experience: ask for it if the user did not name it, and record it as a Binding Decision
4. Show the technology found in Phase 1, and any decision found only in the harness's automatic memory, as existing premises; either becomes a Binding Decision only when the user gives a reason
5. When the user delegates a choice, present 2–3 options with trade-offs and list them as Unbound (protocol §3) until the user picks one, or until the user approves the choice in the `/realize` plan
6. Do NOT implement yet — experience, decisions, and outlook only
7. Iterate until it feels right

+++DETECT:
  D1: Vague Experience — Draft lacks concrete input/output examples
  D2: Implementation Leak — Experience describes internal mechanics, or the draft contains implementation code; a technology recorded in Binding Decisions, an `Unbound:` line, or Direction is not a leak
  D3: Missing Edge Case — No error/empty/boundary states described
  D4: Principle Conflict — Draft contradicts existing design.md principle
  D5: Orphan Principle — Draft implies a principle not yet in design.md
  D6: Unanchored Binding — A Binding Decision lacks a reason (Experience item, external constraint, or stated preference) or a source (the user's words and date, or the approval of the report that listed it)
  D7: Binding Conflict — A Binding Decision contradicts the Experience or another Binding Decision, or contradicts the existing code and environment without a migration the user confirmed in Direction

For D7, present options: change the Binding Decision, change the Experience, or confirm a migration in Direction. Only the user chooses.

+++STOP: on D4
+++STOP: on D7

### Phase 3: REPORT

+++STOP: always

Present the draft to user for approval.

+++Report:
| Section | Draft | Open |
|---------|-------|------|
| Experience | {usage examples and states} | {questions} |
| Binding Decisions | {Decision, Why it binds, Source} | {Unbound items} |
| Direction | {stages, lanes, human gates} | {questions} |
| Acceptance Gates | {mechanical and human gates} | {questions} |
| Detection | {targets that fired} | {resolution needed} |

Omit the rows of sections the draft does not use.

### Phase 4: EXECUTE

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 3 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 3 and re-emit the report.

1. Save the approved draft to `design.md`: Experience, Binding Decisions, Direction, and Acceptance Gates under their own headings (omit the sections the draft does not use); principles from D5 go to the principles section. A Binding Decision row without quoted words takes Source `approved /draft report (<date>)`
2. Suggest: "Run `/realize` to implement this experience"

## Constraints

+++NEVER: Write implementation code during /draft
+++NEVER: Hardcode scopes — they come from design.md
+++NEVER: Save draft with unresolved principle conflict or Binding conflict
+++NEVER: Record a Binding Decision the user did not make — list it as Unbound instead (protocol §3)
