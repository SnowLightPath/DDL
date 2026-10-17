---
name: ddl-protocol
description: "Use this skill when executing or authoring any DDL-style command (draft, realize, reflect, validate, commit, docs, refactoring, or a project command built on this protocol) that uses phases, DETECT, STOP, SWARM, or design.md-driven workflow control. Triggers: any `/command` (Claude Code) or `$command` (Codex) invocation of such a command, requests to create new DDL commands, or tasks referencing design.md-driven workflows with Phases, DETECT, STOP, SWARM. Do NOT use for general coding, documentation, or tasks unrelated to DDL workflow execution."
---

# DDL-PROTOCOL

Design-Doc Loop. Human-LLM collaborative workflow protocol.

Commands are programs. This skill is the instruction set. `+++` directives are instructions — when the processor (you) encounters one, execute its defined procedure. The agent harness you run in (Claude Code, Codex, or another runtime) implements the processor: §2.5 maps each directive onto the tools that runtime actually has. Command files state meaning only and never name runtime tools.

Markdown headings (`#`, `##`, `###`) mark document structure. `+++` marks executable instructions inside phase bodies.

---

## 1. Directive Reference

| Directive | Syntax | Count | Rule |
|-----------|--------|-------|------|
| `# header` | `# command-name` followed by one-line intent | 1 | Required |
| `## usage` | `## Usage` followed by dash-list of invocations | 1+ lines | Required |
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | 3+ | N starts at 0, ascending. At least INIT, one work phase, and REPORT. Phase 0 INIT is required: load the DDL protocol → runtime/project guidance → design.md in that order (lookup order in §2.5). Recommended role names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY. Commands may use domain-specific names (e.g. SCAN, COMPARE, COMMIT) that map to these roles |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | 1+ | `always` required at REPORT phase. `on D{n}` halts when that DETECT fires. A STOP is an executable halt (§1.5). Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 1+ | D starts at 1, ascending, unique per command. Trigger must be operationally verifiable. All targets run in parallel within their phase |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block. See §2 | 0+ | Instruction: fan the `each:` task out to workers, one per scope or batch (§2.3). Evaluate condition against design.md. If false or single scope: execute inline. If true with 2+ scopes: execute §2.4 with the runtime's parallel primitive (§2.5), sequentially when the runtime has none |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | 1+ | Global constraints in the runtime guidance file (`CLAUDE.md`, `AGENTS.md`). Local constraints in command file |
| `+++Report` | `+++Report:` followed by markdown table rows | 0–1 | Output template presented to human at STOP gate |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` (emitted at runtime) | 0+ | **Output marker.** Emit on the first line entering a Phase that mutates state. Pairs with the `### Phase N: NAME` heading in the command file. Codex requires this; Claude SHOULD emit it for long sessions where phase boundaries are otherwise invisible |
| `+++DDL_REPORT` | `+++DDL_REPORT` (emitted at runtime, paired with `+++Report:` template) | 0+ | **Output heading.** Emit immediately before the structured report table at every `+++STOP` gate, in every runtime (§1.5). The `+++Report:` directive defines the table layout; `+++DDL_REPORT` is the heading the LLM writes above it. Together they lock the human-facing output structure |

---

## 1.5 +++STOP execution semantics

`+++STOP` is not a label — it is an executable halt. When you reach a `+++STOP` directive that fires (`always`, or `on D{n}` with that DETECT triggered), execute these steps in order — no exceptions (a design.md human gate covered by Advance approval does not fire):

1. Emit `+++DDL_REPORT` as a heading, then output the `+++Report:` table (or a brief textual finding if no table is defined for the phase).
2. State in one sentence what you need the user to approve, reject, or modify.
3. **End your assistant turn.** Do not call any further tools after the request for approval. Do not write any further text. The phase headings below the STOP exist for resume *after* approval, not for continuation in the same turn.

**Resume rule.** The command may resume only on a subsequent assistant turn whose most recent user message contains an explicit approval token such as `approve`, `yes`, `OK`, `go`, or an unambiguous equivalent in the user's language. Silence, an unrelated reply, or a clarification request is NOT approval — return to the phase that emitted the STOP and re-emit the report after handling the input. Runtime notifications (for example, a background worker's completion) are not user messages.

**Mutation rule.** Between a fired `+++STOP` and explicit user approval, the assistant MUST NOT call any tool that mutates state (§2.5 gives examples for each runtime), and MUST NOT start SWARM workers whose `each:` performs mutation. Read-only tools and read-only workers are permitted only to clarify the report contents, never to begin the next phase.

This rule overrides the momentum of phase ordering. "I already presented the plan in this turn, I might as well execute" is the exact failure mode `+++STOP` exists to prevent.

**Human gates from design.md.** A human gate declared in design.md (the `Gate` column of Direction, or a human gate in Acceptance Gates, §3) is executed as a `+++STOP` by the command that reaches it, with the same three steps.

**Advance approval.** Applies only to human gates declared in design.md. When the user's approval names such gates listed in the report being approved, or says explicitly that they need not stop (for example "approve; don't stop at S1 and S4"), they do not fire: pass them without ending the turn, and list each one, with what it would have shown, in the command's REPORT. A general approval ("approve", "OK", "approve all") approves the report and waives no gate. Advance approval never covers a `+++STOP` written in a command file (`always` or `on D{n}`), outward-facing actions (push, publish, send, deploy), destructive actions, or gates that were not in the approved report.

---

## 2. +++SWARM Instruction

When you encounter `+++SWARM` in a phase and its condition evaluates to true with 2+ scopes, execute the procedure defined in §2.4 with the runtime's parallel primitive (§2.5). The operand block (`team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:`) provides parameters for each step.

### 2.1 Syntax

+++SWARM: 2+ scopes in design.md

```
  team: command-phase
  spawn: role-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Task description per worker.
    {scope} resolves to actual scope name at runtime.
    Report findings to the lead when done.
  collect: lead synthesizes all worker results
```

### 2.2 Fields

| Field | Position | Required | Description |
|-------|----------|----------|-------------|
| condition | first line after `+++SWARM:` | yes | Predicate evaluated against design.md. If false, skip SWARM and execute inline |
| `team` | block body | yes | Fan-out name. Convention: `command-phase` (e.g. `reflect-survey`, `realize-execute`). Used as the team name when the runtime has an explicit team primitive, otherwise as a label for the worker set |
| `spawn` | block body | yes | Worker name pattern. `{scope}` expands per matching scope in design.md |
| `type` | block body | no | Worker role. `Explore` is a read-only worker; `general-purpose` is a worker that may write. Default: `general-purpose`. Extensible to other agent types as needed. §2.5 maps each role to the runtime's agent types |
| `max` | block body | no | Maximum concurrent workers. Default: 5. Controls cost and resource usage |
| `batch` | block body | no | How to group scopes when scope count exceeds `max`. Default: `auto`. See §2.3 |
| `each` | block body | yes | Prompt template for each worker. `{scope}` or `{scopes}` (when batched) resolve at runtime. Must instruct the worker to report results to the lead. Workers do not inherit the lead's conversation, so the resolved prompt must be self-contained (§2.4 Step 3) |
| `collect` | block body | no | How the lead integrates results after all workers complete. Default: synthesize and present in next phase |

### 2.3 Dynamic Scaling

The lead evaluates scope count against `max` and `batch` to determine worker allocation:

```
scope_count = number of design.md scopes matching condition

if scope_count == 0:
    skip SWARM entirely
elif scope_count == 1:
    execute inline, no fan-out
elif scope_count <= max:
    1 worker per scope
elif batch == "auto":
    lead groups related scopes by proximity/dependency
    ceil(scope_count / max) scopes per worker
    {scope} in prompt becomes {scopes} (comma-separated list)
elif batch == "none":
    first `max` scopes run in parallel
    remaining scopes are queued, claimed when a worker finishes
```

| scope_count | max | batch | Result |
|-------------|-----|-------|--------|
| 0 | — | — | Skip SWARM |
| 1 | — | — | Inline, no fan-out |
| 3 | 5 | any | 3 workers, 1 scope each |
| 8 | 5 | `auto` | 5 workers, lead groups 8 scopes into 5 batches |
| 8 | 5 | `none` | 5 workers start, 3 scopes queued |

Scopes whose changes depend on each other (for example, commands that must share one new vocabulary) are not independent: the lead handles them together instead of splitting them across workers, and names the merged scopes and their dependency in its report.

### 2.4 Execution Procedure

When the +++SWARM condition evaluates to true, execute the following procedure in order. Each step says what to do; §2.5 says which tool does it in your runtime. If a tool listed there is missing in the current environment, use the next option in the same cell, or run the assignments sequentially. Never invent a tool.

**Step 1 — Create team**

When the runtime has an explicit team primitive, create a team named `{team}`. Otherwise record the scope assignment locally and continue.

**Step 2 — Scale**

Evaluate scope count per §2.3 to determine worker count and scope assignment. With `batch: none` and overflow, queue the remaining assignments (as tasks when the runtime has a task list).

**Step 3 — Spawn workers**

For each assignment, start one worker with the runtime's parallel primitive for the `type:` role, named `{spawn}` with the scope resolved, in the background where the runtime allows. The prompt is `each:` with `{scope}` or `{scopes}` resolved, plus what the worker cannot see without the lead's conversation: the scope's paths from design.md, the Experience items the scope serves, the principles that apply, the Binding Decisions for the scope, and the Direction stage it works on. If the runtime has no parallel primitive, execute the assignments inline one by one under the same reporting contract.

**Step 4 — Monitor**

Wait for workers through the runtime's completion signal; do not poll. With `batch: none`, start a queued assignment when a worker finishes.

**Step 5 — Collect**

After all workers complete, integrate results following the `collect:` field instructions. A worker that failed or returned nothing is reported as such, never dropped silently. A worker cannot end the user's turn: a worker that meets a STOP condition (a DETECT with `+++STOP: on D{n}`, or a human gate) stops its work and reports it, and after collecting, the lead executes that STOP (§1.5).

**Step 6 — Shutdown**

Release what Step 1 created, if anything (team resources and open workers).

### 2.5 Runtime Adapters

This table is the only place where runtime tool names appear. To support another runtime, add a column; command files do not change. When a runtime renames or removes a tool, edit this table only.

| Concern | Claude Code | Codex | No adapter |
|---------|-------------|-------|------------|
| Invocation | `/command` | `$command` (skill) | ask for the command by name |
| Protocol lookup (Phase 0, step 1) | repo-local `commands/DDL-PROTOCOL-SKILL.md`, then `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md` | repo-local `commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md` | repo-local `commands/DDL-PROTOCOL-SKILL.md` |
| Runtime guidance (Phase 0, step 2) | `CLAUDE.md` or `.claude/CLAUDE.md` | `AGENTS.md` | the runtime's project instruction file |
| Command overlay | `commands/<name>.md` adds project facts to a global command unless it declares itself a full override; `.claude/commands/<name>.md` is a Claude-only shim or a project copy of the command | `commands/<name>.md`, same rule | `commands/<name>.md`, same rule |
| Team primitive (SWARM Step 1) | TeamCreate / TeamDelete, only in environments that provide them; otherwise the session's workers form one implicit team | none | none |
| Parallel primitive (SWARM Step 3) | Agent tool, one call per worker: `subagent_type` from `type:` (`Explore` read-only, `general-purpose` writer), `name` from `spawn:`; workers run in the background (pass `run_in_background` only where the tool accepts it). With a team primitive: the same call with `team_name`, plus TaskCreate / TaskList for queued work | `[agents]` in `.codex/config.toml`: `Explore` → `explorer` (`sandbox_mode = "read-only"`), `general-purpose` → `worker` (`sandbox_mode = "workspace-write"`). Without `[agents]`: parallel shell reads for read-only work, otherwise one by one | run the assignments inline, one by one |
| Completion signal (SWARM Step 4) | background completion notification; SendMessage to continue a worker | agent result | — |
| Mutating tools (§1.5), for example | Edit, Write, NotebookEdit, non-read-only Bash, TaskCreate, a `general-purpose` worker, and any MCP or connector tool that creates, updates, sends, publishes, or deletes | file edits (apply_patch), shell commands that write, a `worker` agent, and any MCP tool that creates, updates, sends, publishes, or deletes | any file write, side-effecting command, or external write |
| `+++DDL_PHASE` | SHOULD, for long sessions | MUST (Codex Runtime Contract in `AGENTS.md`) | SHOULD |
| `+++DDL_REPORT` | MUST at every STOP (§1.5) | MUST at every STOP (§1.5) | MUST at every STOP (§1.5) |

---

## 3. design.md Sections

design.md is the shared notebook between human and LLM. Commands read and write these sections by heading name. A project uses only the sections it needs and may keep other headings. Experience comes first: Binding Decisions, Direction, and Acceptance Gates serve the Experience and never contradict it.

| Section | Holds | Written by | Read by |
|---------|-------|------------|---------|
| `## Intent` | Why the project exists | human, `/draft` | all commands |
| `## Scopes` | Scope table; drives SWARM | human, `/reflect` | all commands |
| `## Principles` (or `## Core Principles`) | Design principles | `/draft` (D5), `/reflect` | all commands |
| `## Experience` | Consumer-side usage: inputs, outputs, and error / empty / boundary states | `/draft`, `/reflect` (additions found in code) | `/realize`, `/reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) because the Experience depends on them, an external constraint requires them, or the human prefers them and says so | the human, through `/draft`; `/realize` records a delegated choice after the human approves it in the plan; a change the human approves in `/realize` or `/reflect` (D6) | `/realize` (honors), `/reflect` (checks), `/refactoring` (keeps) |
| `## Direction` | Non-binding outlook on the path to implementation | `/draft`; `/reflect` replaces finished stages | `/realize` (follows), `/reflect` (retires) |
| `## Acceptance Gates` | What must hold when done: mechanical gates and human gates | `/draft` | `/realize`, `/validate` |
| `## Validation` | Per-scope mechanical checks | human, `/reflect` | `/validate`, `/realize`, `/commit`, `/refactoring` |

**Binding Decisions.** One row per decision:

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: TypeScript — options TypeScript / JavaScript (delegated to /realize)
```

- `Why it binds` names an Experience item, an external constraint (organization standard, existing system, hosting), or a stated preference. A row without a reason or a source is incomplete.
- Only the human creates or changes a row. The LLM may propose a technology; a proposal, a technology named without a reason, and a choice the human delegates are listed under the table as `Unbound: <topic> — options A / B (delegated to /realize | awaiting choice)`. An `Unbound:` line binds nothing.
- A delegated choice is stated in the `/realize` plan; when the human approves the plan, `/realize` moves it into the table with Source `approved in /realize plan (<date>)`.
- Record the granularity the human stated. Exact versions belong to code (manifests and lockfiles).
- Add a `Scope` column when scopes bind different technologies.
- After approval, design.md wins over later command arguments: a different technology named in an argument is a change to a Binding Decision and halts.
- For documents and slides, the output format is the Binding Decision.

**Direction.** A table of stages:

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Fix the search API as a CLI | sample CLI output | `npm test` |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval |
```

- Non-binding. `/realize` follows it by default and reports every deviation (merged, reordered, or skipped stage).
- The lanes of a stage are the units `/realize` fans out (§2).
- Gates in the `Gate` column run at the end of their stage: a mechanical gate is a validation command, and a human gate is executed as `+++STOP` (§1.5) and never skipped. A merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates.
- `/reflect` replaces finished stages (work done, gate passed) with their outcome and deletes the section when every stage is done. When design.md is under version control, the history stays there; otherwise `/reflect` quotes the removed stages in its REPORT.
- Direction is the most temporary part of design.md.

**Acceptance Gates.** A list of conditions for done:

- Mechanical gates are commands, each with the expected result when the command does not fail by exit code alone. `/realize` runs them in VALIDATE, and `/validate` runs them with the Validation block.
- Human gates are approvals. `/realize` executes them as `+++STOP` (§1.5).

**Existing headings.** A project may keep its own headings (for example `Stack` or `Execution plan`). `/reflect` proposes one mapping onto these sections and never forces a rename.

---

## 4. Command Template

````markdown
# command-name

One-line intent.

## Usage

- `/command` — default behavior
- `/command arg` — specific behavior

## Phases

### Phase 0: INIT

1. Read the DDL protocol for the current runtime: repo-local `commands/DDL-PROTOCOL-SKILL.md` when present; otherwise, in Claude Code, `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`; in Codex, `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md`.
2. Read project-local runtime guidance when present: `AGENTS.md` for Codex, `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, and any applicable command overlay.
3. Read `design.md` — extract relevant items
4. If no `design.md` → fallback behavior

### Phase 1: SURVEY

+++SWARM: 2+ scopes in design.md

```
  team: command-survey
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for relevant items.
    Report findings to the lead when done.
  collect: lead merges all scope findings
```

### Phase 2: WORK

Core activity here.

+++DETECT:
  D1: name — trigger condition
  D2: name — trigger condition
  D3: name — trigger condition
  D4: name — trigger condition
  D5: name — trigger condition

### Phase 3: REPORT

+++STOP: always

+++Report:
| # | col | col | col |

### Phase 4: EXECUTE (if applicable)

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 3 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 3 and re-emit the report.

+++SWARM: 2+ approved changes across scopes

```
  team: command-execute
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved changes to {scope}.
    Report completion to the lead when done.
  collect: lead verifies all changes applied
```

### Phase 5: VERIFY (if applicable)

Re-scan. Summarize. Suggest next command.

## Constraints

+++NEVER: prohibition
+++NEVER: prohibition
+++NEVER: prohibition
````
