# Project Name

## Skills

| Skill | Intent |
|-------|--------|
| `$draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `$realize` | Write code based on design principles and Binding Decisions |
| `$reflect` | Update documents based on implementation |
| `$validate` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |
| `$commit` | Git commit |
| `$docs` | Audit and fix documentation |
| `$refactoring` | Audit and fix code quality |

## Structure

- `design.md` - Design Document (scopes, principles, validation; Experience, Binding Decisions, Direction, Acceptance Gates when drafted — see design.md Sections)

## Directive Reference

| Directive | Syntax | Count | Rule |
|-----------|--------|-------|------|
| `# header` | `# skill-name` followed by one-line intent | 1 | Required |
| `## usage` | `## Usage` followed by dash-list of invocations | 1+ lines | Required |
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | 3+ | N starts at 0, ascending. At least INIT, one work phase, and REPORT. Phase 0 INIT is required: load AGENTS.md (the protocol and the project guidance) and any applicable command overlay (`commands/<name>.md`, which adds project facts to a skill unless it declares itself a full override), then design.md, reading only what is not already in context: Codex reads the AGENTS.md chain before any work and design.md stays in context from session start, so a compacted session reads again only what is no longer in context, and a fresh agent reads the sections its prompt names (see +++SWARM Execution). Recommended role names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY. Skills may use domain-specific names (e.g. SCAN, COMPARE, COMMIT) that map to these roles |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | 1+ | `always` required at REPORT phase. `on D{n}` halts when that DETECT fires. A STOP is an executable halt (see Codex Runtime Contract below). A phase that follows a `+++STOP: always` opens with a **Pre-condition** line: enter only after explicit approval at that STOP, otherwise return and re-emit the report. Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 1+ | D starts at 1, ascending, unique per skill. Global targets in AGENTS.md use `G{n}` (Detection Targets below). Trigger must be operationally verifiable. All targets run in parallel within their phase |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block | 0+ | Instruction: fan the `each:` task out to agents, one per scope or batch. The condition is on the same line as `+++SWARM:` and is evaluated against design.md scopes or the units the skill names. If false or single scope: execute inline. If true with 2+ scopes: spawn one subagent per assignment (`explorer` or `worker`, by `type:`), or use the fallback when subagents are unavailable (see +++SWARM Execution below) |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | 1+ | Global constraints in AGENTS.md (Constraints below). Local constraints in the skill file |
| `+++Report` | `+++Report:` followed by markdown table rows | 0–1 | Output template presented to the human at a STOP gate |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` (emitted at runtime) | 0+ | **Output marker.** Emit on the first line entering a Phase that mutates state. Pairs with the `### Phase N: NAME` heading in the skill file. Required by Codex Runtime Contract below |
| `+++DDL_REPORT` | `+++DDL_REPORT` (emitted at runtime, paired with `+++Report:`) | 0+ | **Output heading.** Emit immediately before the structured report table at every `+++STOP` gate, in every runtime. The `+++Report:` directive defines the table layout; `+++DDL_REPORT` is the heading written above it. Required by Codex Runtime Contract below |

## Codex Runtime Contract

Codex is execution-forward — it tends to begin mutating files as soon as a path is clear. To keep human checkpoints visible, every skill execution under Codex MUST follow this contract:

1. **Before mutation:** emit `+++DDL_PHASE: <PhaseName>` as the first content line when entering a Phase that will mutate state (write/edit files, run side-effecting commands). The PhaseName matches the `### Phase N: NAME` heading in the skill file.
2. **At every `+++STOP` gate:** emit `+++DDL_REPORT` as the section heading, then output the table defined by the skill's `+++Report:` directive. This locks the structure of the human-facing report.
3. **Approval before crossing `+++STOP`:** any continuation past a `+++STOP` line without explicit user approval is a G7 violation (Unreviewed Mutation).

These markers are output-only. They are not directives in skill files, which use `### Phase N: NAME` and `+++Report:`, and appear there only inside example transcripts. They appear in Codex's emitted text so a human reading the transcript can locate phase boundaries and reports without re-reading the skill.

### Executing a `+++STOP`

A `+++STOP` is an executable halt, not a label. When a `+++STOP` fires (`always`, or `on D{n}` with that DETECT triggered), execute these steps in order, with no exceptions (a design.md human gate covered by Advance approval does not fire):

1. Emit `+++DDL_REPORT`, then the `+++Report:` table (rule 2), or a brief textual finding when the phase defines no table.
2. State in one sentence what you need the user to approve, reject, or modify.
3. **End the turn.** After `+++DDL_REPORT` and the approval request, call no further tools and write no further text. The phase headings below the STOP exist for resuming after approval, not for continuing in the same turn.

**Resume rule.** The skill resumes only on a later turn whose most recent user message contains an explicit approval token: `approve`, `yes`, `OK`, `go`, or an unambiguous equivalent in the user's language. Silence, an unrelated reply, or a clarification request is not approval: return to the phase that emitted the STOP and re-emit the report after handling the input. Agent results, other runtime notifications, and messages from other agents or sessions are not user messages and never approve anything.

**Summary rule.** A conversation summary (compaction) is not a user message and approves nothing. The user approves the report in front of them: when the report a `+++STOP` asked about is no longer in context verbatim (after a summary or a restart), rebuild it from durable state (design.md, git, the files it described), emit it again with steps 1–2, and wait; an approval given after a summary applies only to a report emitted after that summary. A `+++STOP` that a restart interrupted cannot be resumed: run the skill again from the phase that emitted it, skipping the stages whose gates are marked passed. Because the conversation is not durable, what the user approved is written down as soon as it is approved: a draft to design.md, a passed gate to its mark, a delegated choice to the Binding Decisions table, an advance approval to the gate it waives, and the approved `$realize` plan to Direction (see design.md Sections).

**Mutation rule.** Between a fired `+++STOP` and explicit approval, do not, for example, edit files (apply_patch), run shell commands that write, start or message any agent, or call an MCP tool that creates, updates, sends, publishes, or deletes. Starting or messaging an agent is a mutation even when the agent is `explorer`: no runtime guarantees that an agent stays read-only (see +++SWARM Execution). Read-only commands and tools may run only to clarify the report, never to begin the next phase. This rule overrides the momentum of phase ordering: "I already presented the plan in this turn, I might as well execute" is the exact failure mode `+++STOP` exists to prevent.

**Human gates from design.md.** A human gate written in design.md (the `Gate` column of Direction, or a human gate in Acceptance Gates; see design.md Sections) runs as a `+++STOP` in the skill that reaches it, with the same three steps.

**Advance approval.** Applies only to human gates written in design.md. When the user's approval names such gates listed in the report being approved, or says explicitly that they need not stop (for example "approve; don't stop at S1 and S4"), they do not fire: pass them without ending the turn, and list each one, with what it would have shown, in the skill's REPORT. A general approval ("approve", "OK", "approve all") approves the report and waives no gate. Advance approval never covers a `+++STOP` written in a skill file (`always` or `on D{n}`), outward-facing actions (push, publish, send, deploy), destructive actions, or gates that were not in the approved report.

## +++SWARM Execution

When a skill defines `+++SWARM: condition`:

1. Evaluate the condition against `design.md` scopes or the units the skill names
2. If condition is false or single scope → execute `each:` task inline
3. If condition is true with 2+ scopes → fan out with subagents (below). When subagents are available, running the assignments inline instead is not allowed

Skills may fan out over other units, which count like scopes, for example the lanes of the current Direction stage in `$realize` or files in `$docs`.

When a skill is given a scope or path argument, only the scopes it selects count.

### Fields

- **condition**: the text after `+++SWARM:` on the same line. It is evaluated against design.md scopes or against the units the skill names (lanes, files, document pairs, approved changes)
- `team:`: a label for the agent set
- `spawn:`: the agent's label in reports, with `{scope}` resolved
- `type:`: `Explore` (read-only) or `general-purpose` (may write). Default: `general-purpose`
- `max:`: maximum concurrent agents. Default: 5
- `batch:`: how to group scopes when they exceed `max:`. Default: `auto`
- `each:`: the prompt template, with `{scope}` or `{scopes}` resolved. It must tell the agent to report to the lead, and the resolved prompt is self-contained (step 4 below)
- `collect:`: how the lead integrates the results. Default: synthesize and present in the next phase

### With subagents

Subagents are on by default: `agents.enabled` defaults to `true`, and the `multi_agent` feature is stable and on by default.

1. Map the `type:` field to a custom agent in `.codex/agents/`:
   - `Explore` → `explorer` (read-only work)
   - `general-purpose` → `worker` (work that may write)

   Each custom agent is a standalone TOML file that defines `name`, `description`, and `developer_instructions`. A custom agent named like a built-in agent (`explorer`, `worker`) takes precedence over the built-in one.
2. Subagents inherit the parent session's sandbox and approval settings, and an agent file cannot replace them: agent instructions can ask an agent to avoid edits, but they do not create a separate read-only sandbox. Read-only work is therefore enforced by the `explorer` instructions and stated in the prompt. Set the sandbox and approval policy on the parent session.
3. Scale by scope count against `max:` and `batch:` (defaults in Fields above):
   - 0 scopes: skip SWARM
   - 1 scope: run inline, no fan-out
   - 2 up to `max:` scopes: one agent per scope
   - More than `max:` with `batch: auto`: the lead groups related scopes into at most `max:` batches, and `{scope}` in the prompt becomes `{scopes}`
   - More than `max:` with `batch: none`: the first `max:` assignments start and the rest are queued; the lead starts a queued assignment each time an agent finishes
   - Once an agent reports a STOP condition, start no queued assignment: collect the running agents, then execute the STOP (step 6)
   - Scopes whose changes depend on each other are merged into one assignment (see In both modes below)
4. Spawn one agent per scope (or batch when scope count exceeds `max:`). Each spawn sets `agent_type` to `explorer` or `worker` (step 1), passes the `spawn:` label as `task_name`, and sets `fork_turns = "none"`, because the prompt is self-contained and the agent does not need the lead's conversation (verified in codex-cli 0.160.1). The `spawn:` value, with the scope resolved, is a label that identifies the agent in reports. Do not rely on an agent inheriting the lead's conversation (a Codex subagent may fork it via `fork_turns`), so each prompt is the `each:` task with `{scope}` (or `{scopes}`) resolved, plus the scope's paths from `design.md`, the Experience items the scope serves, the principles that apply, the Binding Decisions for the scope, the Direction stage it works on, the scope's validation commands, the rows the user approved for this phase (verbatim, in an apply or fix phase), and in `$realize` the approved plan. The prompt names the files and the design.md sections the agent reads; the agent does not reload AGENTS.md or design.md in full, because the prompt is its context. The prompt also states that the agent starts no agents of its own (only the lead fans out) and, for an `explorer` agent, that the work is read-only (see In both modes below). A Codex subagent may spawn agents of its own and inherits the parent session's sandbox (step 2), so the agent file instructions and the prompt are what keep it read-only and non-nesting
5. Each agent executes the `each:` task for its assigned scope(s); the lead waits for every agent result before collecting, without polling. With `batch: none`, the lead starts a queued assignment when an agent finishes, unless an agent has reported a STOP condition (step 3)
6. Lead collects results per the `collect:` field. An agent that failed or returned nothing is reported as such, never dropped silently. An agent cannot end the user's turn: an agent that meets a STOP condition (a DETECT with `+++STOP: on D{n}`, or a human gate) stops its work and reports it, and after collecting, the lead executes that STOP (see Codex Runtime Contract)
7. After collecting, close any agent that is still open

### Without subagents (fallback)

When subagents are unavailable (turned off in the configuration with `agents.enabled = false`, or not provided by the environment):

1. For read-only work (`type: Explore`), run the shell reads in parallel; otherwise execute the `each:` task for each assignment one by one
2. Lead integrates the results per the `collect:` field, under the same reporting contract as with subagents
3. The `team:`, `spawn:`, `max:`, `batch:` fields are metadata only — they document what would be parallelized

### In both modes

- Scopes whose changes depend on each other (for example, skills that must share one new vocabulary) are not independent: the lead handles them together instead of splitting them across agents, and names the merged scopes and their dependency in its report.
- Agents do not start agents of their own; only the lead fans out.
- When an agent or tool named in this section is missing in the current environment, use the fallback above. Never invent a tool.
- An `explorer` agent is read-only: it edits no files and starts no agents, and the only writes it may cause are the caches and build output of commands its task names (for example the validation commands in `$validate`), inside its scope. The same holds when the lead runs read-only work itself in the fallback.

## design.md Sections

design.md is the shared notebook between human and LLM, in context from session start, so it carries what the human agreed to and nothing else: agent progress and memories stay out of it. Skills read and write these sections by heading name. A project may keep its notebook in other files (for example a library whose README and guides are its living specification) when its runtime guidance (`AGENTS.md`) names them; skills then read and write those files wherever this file or a skill says design.md. A project uses only the sections it needs and may keep other headings. Experience comes first: Binding Decisions, Direction, and Acceptance Gates serve the Experience and never contradict it.

| Section | Holds | Written by | Read by |
|---------|-------|------------|---------|
| `## Intent` | Why the project exists | human | every session, because design.md is in context from session start; no skill extracts it |
| `## Scopes` | Scope table; drives SWARM | human, `$reflect` | every skill whose units are scopes; a skill that fans out over other units (for example document pairs) reads none |
| `## Principles` (or `## Core Principles`) | Design principles | `$draft` (D5), `$reflect` | `$draft`, `$realize`, `$reflect` |
| `## Experience` | Consumer-side usage: inputs, outputs, and error / empty / boundary states | `$draft`, `$reflect` (additions found in code) | `$draft`, `$realize`, `$reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) because the Experience depends on them, an external constraint requires them, or the human prefers them and says so | the human, through `$draft`; `$realize` records a delegated choice after the human approves it in the plan; a change the human approves in `$realize` or `$reflect` (D6) | `$draft`, `$realize` (honors), `$reflect` (checks), `$refactoring` (keeps) |
| `## Direction` | Non-binding outlook on the path to implementation | `$draft`; `$realize` writes the `Approved plan` lines and the gate marks (`approved in advance`, `passed`); `$reflect` replaces passed stages and deletes their `Approved plan` lines | `$draft`, `$realize` (follows), `$reflect` (retires) |
| `## Acceptance Gates` | What must hold when done: mechanical gates and human gates | `$draft`; `$realize` marks gates passed; `$reflect` retires it after acceptance | `$draft`, `$realize`, `$validate`, `$reflect` (retires) |
| `## Validation` | Per-scope mechanical checks | human, `$reflect` | `$validate`, `$realize`, `$commit`, `$refactoring` |

**Binding Decisions.** One row per decision:

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: Language — options TypeScript / JavaScript (delegated to $realize)
```

- `Why it binds` names an Experience item, an external constraint (organization standard, existing system, hosting), or a stated preference. A row without a reason or a source is incomplete.
- `Source` quotes the human's words with the date. When the human approves a report that listed the row, that approval is the source (for example `approved $draft report (2026-10-17)`).
- Technology already present in the code is an existing premise: skills show it in their reports, and design.md does not record it, because the code already does. It becomes a row only when the human gives a reason. A decision found only in the harness's memories is at most such a premise: skills show it in their reports, and it binds nothing until the human records it here.
- Only the human creates or changes a row. The LLM may propose a technology; a proposal, a technology named without a reason, and a choice the human delegates are listed under the table as `Unbound: <topic> — options A / B (delegated to $realize | awaiting choice)`. An `Unbound:` line binds nothing.
- A delegated choice is stated in the `$realize` plan; when the human approves the plan, `$realize` moves it into the table with Source `approved in $realize plan (<date>)`.
- Record the granularity the human stated. Exact versions belong to code (manifests and lockfiles).
- Add a `Scope` column when scopes bind different technologies.
- After approval, design.md wins over later skill arguments: a different technology named in an argument is a change to a Binding Decision and halts.
- For documents and slides, the output format is the Binding Decision.

**Direction.** A table of stages:

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Settle the search API as a CLI | sample CLI output | `npm test` |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval |
```

- Non-binding. `$realize` follows it by default and reports every deviation (merged, reordered, or skipped stage).
- The lanes of a stage are the units `$realize` fans out (see +++SWARM Execution).
- When the user approves the `$realize` plan, `$realize` writes its durable parts under the table as `Approved plan (<date>): files to touch, approach, Unbound choices made`, so a later or compacted session rebuilds agent prompts from it instead of from a summary. `$reflect` deletes these lines with the stages they served.
- Gates in the `Gate` column run at the end of their stage: a mechanical gate is a validation command, and a human gate is executed as `+++STOP` unless the human approved it in advance (see Codex Runtime Contract). Gates are never dropped: a merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates.
- `$reflect` replaces stages whose gates are all marked passed with their outcome, and deletes the section when every stage is done. When design.md is under version control, the history stays there; otherwise `$reflect` quotes the removed stages in its REPORT.
- Direction is the most temporary part of design.md. Retiring it, like retiring Acceptance Gates, also shrinks what every later session loads.

**Acceptance Gates.** A list of conditions for done:

- Mechanical gates are commands, each with the expected result when the command does not fail by exit code alone. `$realize` runs them in VALIDATE, and `$validate` runs them with the Validation block.
- Human gates are approvals. `$realize` executes them as `+++STOP` (see Codex Runtime Contract) at the end of the work.
- The work is accepted when every gate is marked passed. `$reflect` then retires the section: mechanical gates that should keep running move into the Validation block first.

**Passed marks.** A gate passes when its command gives the expected result, or when the human approves it at the gate or in advance (see Codex Runtime Contract). `$realize` appends `passed <date>` to each gate that passes, in the stage's Gate cell for Direction (for example `human approval, passed 2026-10-20`) and after the gate for Acceptance Gates. An advance approval is written in the same place the moment the user gives it, as `approved in advance (<date>)`; when the stage or the work ends, `passed <date>` follows it, so a waived gate reads `human approval, approved in advance (2026-10-20), passed 2026-10-21`. These marks are the record of progress and acceptance: `$reflect` reads them and never infers a pass from conversation memory.

**Existing headings.** A project may keep its own headings (for example `Stack` or `Execution plan`). `$reflect` proposes one mapping onto these sections and never forces a rename.

## Detection Targets

Every skill defines its own D-targets (D1, D2, …). Cross-cutting targets below apply **globally**.

+++DETECT:
  G1: Vague Intent — Task description lacks measurable outcome
  G2: Scope Creep — Change touches files outside stated scope
  G3: Principle Violation — Action contradicts `design.md` principles
  G4: Missing Validation — No verification step after mutation
  G5: Leaked Specifics — Project-specific paths/commands hardcoded in framework files
  G6: Silent Failure — Error swallowed without user notification
  G7: Unreviewed Mutation — Shared artifact changed without +++STOP

## Behavior

### On session start

1. This file is already in context: Codex reads the `AGENTS.md` chain before any work. Read it again only when it is no longer in context (after a compaction)
2. Read `design.md` if it exists — extract scopes, principles, validation commands, and the Experience, Binding Decisions, Direction, and Acceptance Gates when present. It stays in context; skills re-read it only after a compaction, and an agent reads only the sections its prompt names
3. Memories are a recall layer: a decision found only there is a proposal until design.md records it

### On any task

1. Identify which scopes (from `design.md`) are affected
2. Run the skill's Phase sequence
3. Scan for Detection Targets at each phase boundary
4. Never skip a STOP gate

### On completion

1. Summarize what changed (files, lines, scopes)
2. List any Detection Targets that fired
3. Suggest next skill if applicable (`$draft` → `$realize` → `$reflect`)

## Constraints

+++NEVER: Hardcode paths or commands — scopes and validation come from design.md
+++NEVER: Auto-proceed past a +++STOP
+++NEVER: Add AI attribution to commits or generated code
+++NEVER: Skip emitting +++DDL_PHASE before mutation — Codex's execution-forward bias must be visibly checkpointed
+++NEVER: Output a +++STOP gate without +++DDL_REPORT followed by the +++Report: table, or a brief finding when the phase defines none
+++NEVER: Spawn agents when a SWARM has fewer than 2 units (scopes, Direction lanes, files, document pairs, approved changes) — for 2+, follow +++SWARM semantics (mandatory when condition is true; only the lead fans out; see +++SWARM Execution)
