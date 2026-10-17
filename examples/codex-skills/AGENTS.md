# Project Name

## Skills

| Skill | Intent |
|-------|--------|
| `$draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `$realize` | Write code based on design principles |
| `$reflect` | Update documents based on implementation |
| `$validate` | Run mechanical validation per scope |
| `$commit` | Git commit |
| `$docs` | Audit and fix documentation |
| `$refactoring` | Audit and fix code quality |

## Structure

- `DESIGN.md` - Design Document (scopes, principles, validation; Experience, Binding Decisions, Direction, Acceptance Gates when drafted — see DESIGN.md Sections)

## Directive Reference

| Directive | Syntax | Rule |
|-----------|--------|------|
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | N starts at 0, ascending. 3+ phases per skill: at least INIT, one work phase, and REPORT. Phase 0 INIT is required: load AGENTS.md → DESIGN.md in that order. Recommended role names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY; skills may use domain-specific names (e.g. SCAN, COMPARE, COMMIT) that map to these roles |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | `always` required at REPORT phase. `on D{n}` halts when that DETECT fires. A STOP is an executable halt (see Codex Runtime Contract below). Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | D starts at 1, ascending, unique per skill. Trigger must be operationally verifiable. All targets run in parallel within their phase |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block | Instruction: fan the `each:` task out to agents, one per scope or batch. Evaluate the condition against DESIGN.md. If false or single scope: execute inline. If true with 2+ scopes: spawn agents with the `[agents]` roles, or use the fallback when multi-agent is not enabled (see +++SWARM Execution below) |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | Global constraints in AGENTS.md (Constraints below). Local constraints in the skill file |
| `+++Report` | `+++Report:` followed by markdown table rows | Output template presented to the human at a STOP gate |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` (emitted at runtime) | **Output marker.** Emit on the first line entering a Phase that mutates state. Required by Codex Runtime Contract below |
| `+++DDL_REPORT` | `+++DDL_REPORT` (emitted at runtime, paired with `+++Report:`) | **Output heading.** Emit immediately before the structured report table at every `+++STOP` gate, in every runtime. Required by Codex Runtime Contract below |

## Codex Runtime Contract

Codex is execution-forward — it tends to begin mutating files as soon as a path is clear. To keep human checkpoints visible, every skill execution under Codex MUST follow this contract:

1. **Before mutation:** emit `+++DDL_PHASE: <PhaseName>` as the first content line when entering a Phase that will mutate state (write/edit files, run side-effecting commands). The PhaseName matches the `### Phase N: NAME` heading in the skill file.
2. **At every `+++STOP` gate:** emit `+++DDL_REPORT` as the section heading, then output the table defined by the skill's `+++Report:` directive. This locks the structure of the human-facing report.
3. **Approval before crossing `+++STOP`:** any continuation past a `+++STOP` line without explicit user approval is a G7 violation (Unreviewed Mutation).

These markers are output-only. They do not appear in skill files (skill files use `### Phase N: NAME` and `+++Report:`). They appear in Codex's emitted text so a human reading the transcript can locate phase boundaries and reports without re-reading the skill.

### Executing a `+++STOP`

A `+++STOP` is an executable halt, not a label. When a `+++STOP` fires (`always`, or `on D{n}` with that DETECT triggered), execute these steps in order, with no exceptions (a DESIGN.md human gate covered by Advance approval does not fire):

1. Emit `+++DDL_REPORT`, then the `+++Report:` table (rule 2), or a brief textual finding when the phase defines no table.
2. State in one sentence what you need the user to approve, reject, or modify.
3. **End the turn.** After the approval request, call no further tools and write no further text. The phase headings below the STOP exist for resuming after approval, not for continuing in the same turn.

**Resume rule.** The skill resumes only on a later turn whose most recent user message contains an explicit approval token: `approve`, `yes`, `OK`, `go`, or an unambiguous equivalent in the user's language. Silence, an unrelated reply, or a clarification request is not approval: return to the phase that emitted the STOP and re-emit the report after handling the input. Runtime notifications (for example, a background worker's completion) are not user messages.

**Mutation rule.** Between a fired `+++STOP` and explicit approval, do not, for example, edit files (apply_patch), run shell commands that write, spawn a `worker` agent, or call an MCP tool that creates, updates, sends, publishes, or deletes. Read-only commands and `explorer` agents may run only to clarify the report, never to begin the next phase. This rule overrides the momentum of phase ordering: "I already presented the plan in this turn, I might as well execute" is the exact failure mode `+++STOP` exists to prevent.

**Human gates from DESIGN.md.** A human gate written in DESIGN.md (the `Gate` column of Direction, or a human gate in Acceptance Gates; see DESIGN.md Sections) runs as a `+++STOP` in the skill that reaches it, with the same three steps.

**Advance approval.** Applies only to human gates written in DESIGN.md. When the user's approval names such gates listed in the report being approved, or says explicitly that they need not stop (for example "approve; don't stop at S1 and S4"), they do not fire: pass them without ending the turn, and list each one, with what it would have shown, in the skill's REPORT. A general approval ("approve", "OK", "approve all") approves the report and waives no gate. Advance approval never covers a `+++STOP` written in a skill file (`always` or `on D{n}`), outward-facing actions (push, publish, send, deploy), destructive actions, or gates that were not in the approved report.

## +++SWARM Execution

When a skill defines `+++SWARM: condition`:

1. Evaluate the condition against `DESIGN.md`
2. If condition is false or single scope → execute `each:` task inline
3. If condition is true with 2+ scopes:

### With multi-agent enabled

When `[agents]` is configured in `.codex/config.toml`:

1. Map the `type:` field to a Codex agent role:
   - `Explore` → `explorer` role (`sandbox_mode = "read-only"`)
   - `general-purpose` → `worker` role (`sandbox_mode = "workspace-write"`)
2. Evaluate scope count against `max:` field to determine concurrency
3. Spawn one agent per scope (or batch when scope count exceeds `max:`). Agents do not inherit the lead's conversation, so each prompt is the `each:` task with `{scope}` (or `{scopes}`) resolved, plus the scope's paths from `DESIGN.md`, the Experience items the scope serves, the principles that apply, the Binding Decisions for the scope, and the Direction stage it works on
4. Each agent executes the `each:` task for its assigned scope(s)
5. Lead collects results per the `collect:` field. An agent that failed or returned nothing is reported as such, never dropped silently. An agent cannot end the user's turn: an agent that meets a STOP condition (a DETECT with `+++STOP: on D{n}`, or a human gate) stops its work and reports it, and after collecting, the lead executes that STOP (see Codex Runtime Contract)

### Without multi-agent (sequential fallback)

When multi-agent is not enabled:

1. Execute `each:` task **sequentially** for each matching scope; for read-only work (`type: Explore`), the shell reads may run in parallel
2. Lead integrates the results per the `collect:` field, as in multi-agent mode
3. The `team:`, `spawn:`, `max:`, `batch:` fields are metadata only — they document what would be parallelized

### In both modes

- Scopes whose changes depend on each other (for example, skills that must share one new vocabulary) are not independent: the lead handles them together instead of splitting them across agents, and names the merged scopes and their dependency in its report.
- When a role or tool named in this section is missing in the current environment, run the assignments sequentially. Never invent a tool.
- Explore work that must run commands writing caches or build output (tests, builds) runs in the lead when the `explorer` sandbox blocks writes.

## DESIGN.md Sections

DESIGN.md is the shared notebook between human and LLM. Skills read and write these sections by heading name. A project uses only the sections it needs and may keep other headings. Experience comes first: Binding Decisions, Direction, and Acceptance Gates serve the Experience and never contradict it.

| Section | Holds | Written by | Read by |
|---------|-------|------------|---------|
| `## Intent` | Why the project exists | human, `$draft` | all skills |
| `## Scopes` | Scope table; drives SWARM | human, `$reflect` | all skills |
| `## Principles` (or `## Core Principles`) | Design principles | `$draft` (D5), `$reflect` | all skills |
| `## Experience` | Consumer-side usage: inputs, outputs, and error / empty / boundary states | `$draft`, `$reflect` (additions found in code) | `$realize`, `$reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) because the Experience depends on them, an external constraint requires them, or the human prefers them and says so | the human, through `$draft`; `$realize` records a delegated choice after the human approves it in the plan; a change the human approves in `$realize` or `$reflect` (D6) | `$realize` (honors), `$reflect` (checks), `$refactoring` (keeps) |
| `## Direction` | Non-binding outlook on the path to implementation | `$draft`; `$reflect` replaces finished stages | `$realize` (follows), `$reflect` (retires) |
| `## Acceptance Gates` | What must hold when done: mechanical gates and human gates | `$draft` | `$realize`, `$validate` |
| `## Validation` | Per-scope mechanical checks | human, `$reflect` | `$validate`, `$realize`, `$commit`, `$refactoring` |

**Binding Decisions.** One row per decision:

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: TypeScript — options TypeScript / JavaScript (delegated to $realize)
```

- `Why it binds` names an Experience item, an external constraint (organization standard, existing system, hosting), or a stated preference. A row without a reason or a source is incomplete.
- Only the human creates or changes a row. The LLM may propose a technology; a proposal, a technology named without a reason, and a choice the human delegates are listed under the table as `Unbound: <topic> — options A / B (delegated to $realize | awaiting choice)`. An `Unbound:` line binds nothing.
- A delegated choice is stated in the `$realize` plan; when the human approves the plan, `$realize` moves it into the table with Source `approved in $realize plan (<date>)`.
- Record the granularity the human stated. Exact versions belong to code (manifests and lockfiles).
- Add a `Scope` column when scopes bind different technologies.
- After approval, DESIGN.md wins over later skill arguments: a different technology named in an argument is a change to a Binding Decision and halts.
- For documents and slides, the output format is the Binding Decision.

**Direction.** A table of stages:

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Fix the search API as a CLI | sample CLI output | `npm test` |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval |
```

- Non-binding. `$realize` follows it by default and reports every deviation (merged, reordered, or skipped stage).
- The lanes of a stage are the units `$realize` fans out (see +++SWARM Execution).
- Gates in the `Gate` column run at the end of their stage: a mechanical gate is a validation command, and a human gate is executed as `+++STOP` (see Codex Runtime Contract) and never skipped. A merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates.
- `$reflect` replaces finished stages (work done, gate passed) with their outcome and deletes the section when every stage is done. When DESIGN.md is under version control, the history stays there; otherwise `$reflect` quotes the removed stages in its REPORT.
- Direction is the most temporary part of DESIGN.md.

**Acceptance Gates.** A list of conditions for done:

- Mechanical gates are commands, each with the expected result when the command does not fail by exit code alone. `$realize` runs them in VALIDATE, and `$validate` runs them with the Validation block.
- Human gates are approvals. `$realize` executes them as `+++STOP` (see Codex Runtime Contract).

**Existing headings.** A project may keep its own headings (for example `Stack` or `Execution plan`). `$reflect` proposes one mapping onto these sections and never forces a rename.

## Detection Targets

Every skill defines its own D-targets (D1, D2, …). Cross-cutting targets below apply **globally**.

+++DETECT:
  G1: Vague Intent — Task description lacks measurable outcome
  G2: Scope Creep — Change touches files outside stated scope
  G3: Principle Violation — Action contradicts `DESIGN.md` principles
  G4: Missing Validation — No verification step after mutation
  G5: Leaked Specifics — Project-specific paths/commands hardcoded in framework files
  G6: Silent Failure — Error swallowed without user notification
  G7: Unreviewed Mutation — Shared artifact changed without +++STOP

## Behavior

### On session start

1. Read `AGENTS.md` (this file)
2. Read `DESIGN.md` if it exists — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates when present

### On any task

1. Identify which scopes (from `DESIGN.md`) are affected
2. Run the skill's Phase sequence
3. Scan for Detection Targets at each phase boundary
4. Never skip a STOP gate

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next skill if applicable (`$draft` → `$realize` → `$reflect`)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from DESIGN.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Add AI attribution to commits or generated code
+++NEVER: Skip emitting +++DDL_PHASE before mutation — Codex's execution-forward bias must be visibly checkpointed
+++NEVER: Output a +++STOP gate without +++DDL_REPORT followed by the +++Report: table, or a brief finding when the phase defines none
+++NEVER: Spawn agents for single-scope tasks — for 2+ scopes, follow +++SWARM semantics (mandatory when condition is true; see +++SWARM Execution)
