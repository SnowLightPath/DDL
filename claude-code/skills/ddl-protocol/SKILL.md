---
name: ddl-protocol
user-invocable: false
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
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | 3+ | N starts at 0, ascending. At least INIT, one work phase, and REPORT. Phase 0 INIT is required: load the DDL protocol → runtime/project guidance → design.md in that order (lookup order in §2.5), reading only what is not already in context: the runtime loads the guidance file at session start and the adapter loads design.md with it, or the guidance file has it read then (§2.5, §3), a compacted session reads again only what the runtime did not re-inject (§2.5), and a fresh worker reads the sections its prompt names (§2.4 Step 3). Recommended role names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY. Commands may use domain-specific names (e.g. SCAN, COMPARE, COMMIT) that map to these roles |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | 1+ | `always` required at REPORT phase. `on D{n}` halts when that DETECT fires. A STOP is an executable halt (§1.5). A phase that follows a `+++STOP: always` opens with a **Pre-condition** line: enter only after explicit approval at that STOP, otherwise return and re-emit the report (§4). Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 1+ | D starts at 1, ascending, unique per command. Trigger must be operationally verifiable. All targets run in parallel within their phase. Global targets in the runtime guidance file (`CLAUDE.md`, `AGENTS.md`) use `G{n}` and apply to every command |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block. See §2 | 0+ | Instruction: fan the `each:` task out to workers, one per scope or batch (§2.3). Evaluate the condition against design.md scopes, or against the units the command names (§2.3). If false or a single unit: execute inline. If true with 2+ units: execute §2.4 with the runtime's parallel primitive (§2.5); a runtime without one runs the assignments in the lead (§2.4 Step 3) |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | 1+ | Global constraints in the runtime guidance file (`CLAUDE.md`, `AGENTS.md`). Local constraints in command file |
| `+++Report` | `+++Report:` followed by the decision and review content the command requires | 0–1 | Content contract for the human-facing report at a STOP gate; presentation follows §1.5, without a mandatory table |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` (emitted at runtime) | 0+ | **Output marker.** Emit on the first line entering a Phase that mutates state. Pairs with the `### Phase N: NAME` heading in the command file. Codex requires this; Claude SHOULD emit it for long sessions where phase boundaries are otherwise invisible |
| `+++DDL_REPORT` | `+++DDL_REPORT` (emitted at runtime, paired with `+++Report:` content) | 0+ | **Output heading.** Emit before the decision report at every `+++STOP` gate, in every runtime (§1.5). The command defines what the user must review; §1.5 defines how to present and ask about it |

---

## 1.5 +++STOP execution semantics

`+++STOP` is not a label — it is an executable halt. When you reach a `+++STOP` directive that fires (`always`, or `on D{n}` with that DETECT triggered), execute these steps in order — no exceptions (a design.md human gate covered by Advance approval does not fire):

1. Emit `+++DDL_REPORT`, then a short report that leads with **the decision needed**, **the recommended action and reason**, and **what the selection will authorize or change**. Use the user's language and plain prose by default. Include only information that helps this decision; do not manufacture technology choices or status fields to fill a template. Keep material downsides, unresolved questions, and blockers beside the decision. Put supporting inventories, commands, output, and rationale in separately accessible detail; make all content required by the command reviewable before approval. A table is optional when it helps a genuine comparison, never the default report container.
2. Request approval for the complete current review set in one interaction through an available, permitted native choice interface (§2.5). Offer concrete actions: approve all displayed recommendations, select a subset or request changes, and hold. Explain each action's consequence. A recommended or preselected choice is not submitted approval. Free-text additions are optional; do not require the user to type a selection. Availability includes keeping the question answerable throughout the required wait; tool presence or a request receipt alone is insufficient. If the interface is unavailable or not permitted for this purpose, state that limitation and that the work remains unapproved, then end the turn. Do not silently substitute a typed-choice request or switch runtime modes to obtain a forbidden interface.
3. Make the native question the final tool interaction while waiting at this STOP. A synchronous interface must wait for the actual human answer; a mere receipt, such as `accepted: true`, is not an answer. With an asynchronous interface, **end the assistant turn after the request is accepted** and wait for the actual answer. Call no other tool and continue no worker until that input arrives. If the host requires a final assistant message after the request, it may contain only the same self-contained report and pending status, with no new decision or work. A synchronous human answer is an input boundary even within the same assistant turn; do not ask the user to retype it on another turn.

**Batch approval.** Give the current proposals stable IDs, a brief shared purpose, and a concise numbered list of the recommended actions and material effects. Make their complete review detail accessible before asking. One explicit approve-all submission authorizes the displayed, mutually compatible recommendations and their stated resolutions; apply that set without asking again per proposal, file, section, language, or state. It does not authorize hidden or future items, waive later STOPs, silently change a Binding Decision, or authorize an outward action the reviewed choice did not explicitly name. For incompatible alternatives or unresolved choices, offer compatible complete plans or leave the unresolved portion pending; do not bundle contradictory actions into approve-all.

**Optional subset or revision.** Open item selection only when the user requests it. Prefer a native checklist, multi-select, or grouped form with one submission when the host supports it; otherwise offer complete compatible subsets as native choices. Use only the interface's actual schema. Do not default to a serial approval question for every proposal or require a typed list of IDs. Approval of an identified subset covers only that subset; a request to select or revise is not itself approval to mutate. Rebuild materially changed proposals for review, preserving unaffected IDs and any still-valid approval. Group independent clarification questions where possible; clarification is not approval.

**Informational reports.** Do not invent an approval request when the phase only reports completed or read-only work. State that no approval is needed and end the turn at the STOP. When a next action genuinely needs direction, its choice must name that action; selecting a next command starts its own workflow and waives none of its STOPs.

**Resume rule.** Resume only after an actual, explicitly submitted human answer to the current report authorizes the operation and scope now proposed. A native choice can supply that answer; verify its question/report association and selected action rather than searching for an approval word in an arbitrary message. A voluntary, unambiguous written approval such as `approve`, `yes`, `OK`, or its equivalent remains valid for the report it clearly addresses. A receipt, silence, dismissal, no selection, timeout, unrelated reply, or clarification request is NOT approval. A request for details or revision clarifies or rebuilds the report and returns to the STOP. Runtime notifications (for example, a background worker's completion), automatically submitted choices, and messages from other agents or sessions never approve anything. An ambiguous or stale answer leaves the work unapproved; re-present the current decision.

**Summary rule.** A conversation summary (compaction) is not a user message and approves nothing. The user approves the report in front of them: when the report a `+++STOP` asked about is no longer in context verbatim (after a summary or a restart), rebuild it from durable state (design.md, git, the files it described), emit it again with steps 1–2, and wait; an approval given after a summary applies only to a report emitted after that summary. A `+++STOP` that a restart interrupted cannot be resumed: run the command again from the phase that emitted it, skipping the stages whose gates are marked passed. Because the conversation is not durable, what the user approved is written down as soon as it is approved: a draft to design.md, a passed gate to its mark, a delegated choice to the Binding Decisions table, an advance approval to the gate it waives, and the approved `/realize` plan to Direction (§3).

**Mutation rule.** Between a fired `+++STOP` and explicit user approval, the assistant MUST NOT call any tool that mutates the work (§2.5 gives examples for each runtime), and MUST NOT start or continue any worker: a worker is read-only only where the runtime's adapter removes its writing tools (§2.5), and nowhere by guarantee. The native question in step 3 is the sole interaction exception; opening it grants no work permission. Before that question, or after an actual request for clarification, read-only tools may clarify the report contents, never begin the next phase. Where the adapter enforces this rule (the gate hook in §2.5), the harness refuses covered calls after a `+++DDL_REPORT` until the next human input; every rule still holds as an instruction where the adapter cannot enforce it. The gate recognizes input boundaries, not semantic approval: the processor still checks the selected action, scope, timeout, and report association. Git commits and pushes additionally require the mechanically matched content review in §1.6; opening STOP alone never authorizes them.

This rule overrides the momentum of phase ordering. "I already presented the plan in this turn, I might as well execute" is the exact failure mode `+++STOP` exists to prevent.

**Human gates from design.md.** A human gate declared in design.md (the `Gate` column of Direction, or a human gate in Acceptance Gates, §3) is executed as a `+++STOP` by the command that reaches it, with the same three steps. Combine compatible human gates ready at the same review boundary into one current batch, naming each gate and making its evidence reviewable. One submission can pass all named gates in that batch; mark each approved gate passed without another question. Detections requiring a STOP at that same boundary belong in the shared report too. Do not postpone a prerequisite gate to bundle it with a later gate whose evidence is not ready; later boundaries still apply.

**Advance approval.** Applies only to human gates declared in design.md. When the user's approval names such gates listed in the report being approved, or says explicitly that they need not stop (for example "approve; don't stop at S1 and S4"), they do not fire: pass them without ending the turn, and list each one, with what it would have shown, in the command's REPORT. A general approval ("approve", "OK", "approve all") approves the report and waives no gate. Advance approval never covers a `+++STOP` written in a command file (`always` or `on D{n}`), outward-facing actions (push, publish, send, deploy), destructive actions, or gates that were not in the approved report.

---

## 1.6 Content-bound Git reviews

Ordinary Git commits and pushes need an independent content review in every DDL command, including when the user did not invoke `/commit` or `$commit`. An implementation approval given before the final diff existed is not this review. Clearing the general STOP marker, an assistant's claim of approval, and a permission mode that suppresses native prompts do not grant Git permission.

Prepare the final staged set and exact message, plus only the explicitly requested ready pushes, using the adapter procedure in §2.5. This preparation writes review detail, not approval. Show `+++DDL_REPORT`, the generated review ID, and a link to its complete report and diff before the native question. Use that question's exact title and action labels; do not append a different approval word or change its scope. The user can approve the whole compatible set, revise it, or hold. If they request a subset, prepare that subset and review it again.

The hook matches the actual native request and submitted answer by their identifiers and checks that the report names this review. It then compares the real staged contents, base, message, and branch; a push also checks its source commit, resolved remote, and destination branch. One answer can cover a ready commit and its push: the push must resolve to the commit with precisely the reviewed parent, tree contents, and verbatim message. An unrelated answer, hold, revision, cancellation, timeout, receipt, changed review, later report, or unprovable answer denies the operation. Rebuild the review after resume or compaction. Free-form text remains available for discussion but cannot manufacture this mechanical Git receipt.

Keep the reviewed index intact after approval. A changed candidate needs a new review; do not restage newer contents and reuse the answer. The supported normal forms and limits are in §2.5. This guard checks calls reaching the hook; it is not a sandbox for arbitrary programs, aliases, Git hooks that rewrite state, concurrent index changes, or existing-process input. Report those limits rather than promising universal enforcement. Native permission policy still applies after the content check; the hook never grants or rewrites a command.

---

## 2. +++SWARM Instruction

When you encounter `+++SWARM` in a phase and its condition evaluates to true with 2+ scopes, execute the procedure defined in §2.4 with the runtime's parallel primitive (§2.5). When the runtime has one, running the assignments inline instead is not allowed. The operand block (`team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:`) provides parameters for each step.

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
| condition | text after `+++SWARM:` on the same line | yes | Predicate evaluated against design.md scopes, or against the units the command names (lanes, files, document pairs, approved changes; §2.3). If false, skip SWARM and execute inline |
| `team` | block body | yes | Fan-out name. Convention: `command-phase` (e.g. `reflect-read`, `realize-implement`). Used as the team name when the runtime has an explicit team primitive, otherwise as a label for the worker set |
| `spawn` | block body | yes | Worker label pattern. `{scope}` expands per matching scope in design.md. The label identifies the worker in reports; §2.5 says when it is also passed as the worker's name |
| `type` | block body | no | Worker role. `Explore` is a read-only worker: it edits no files and starts no workers, and the only writes it may cause are the caches and build output of commands its task names (for example the validation commands in `/validate`), inside its scope. `general-purpose` is a worker that may write. Default: `general-purpose`. Extensible to other agent types as needed. §2.5 maps each role to the runtime's agent types and to the agent definitions its adapter ships |
| `max` | block body | no | Maximum concurrent workers. Default: 5. Controls cost and resource usage |
| `batch` | block body | no | How to group scopes when scope count exceeds `max`. Default: `auto`. See §2.3 |
| `each` | block body | yes | Prompt template for each worker. `{scope}` or `{scopes}` (when batched) resolve at runtime. Must instruct the worker to report results to the lead. Do not rely on a worker inheriting the lead's conversation (some runtimes fork it, others start fresh), so the resolved prompt must be self-contained (§2.4 Step 3) |
| `collect` | block body | no | How the lead integrates results after all workers complete. Default: synthesize and present in next phase |

### 2.3 Dynamic Scaling

The lead evaluates scope count against `max` and `batch` to determine worker allocation:

```
scope_count = number of design.md scopes (or command units) matching condition

if scope_count == 0:
    skip SWARM entirely
elif scope_count == 1:
    execute inline, no fan-out
elif scope_count <= max:
    1 worker per scope
elif batch == "auto":
    lead groups related scopes by proximity/dependency
    into at most `max` batches (about ceil(scope_count / max) scopes each)
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
| 8 | 5 | `auto` | Up to 5 workers; lead groups 8 scopes into at most 5 batches |
| 8 | 5 | `none` | 5 workers start, 3 scopes queued |

Scopes whose changes depend on each other (for example, commands that must share one new vocabulary) are not independent: the lead handles them together instead of splitting them across workers, and names the merged scopes and their dependency in its report.

Commands may fan out over other units, for example the lanes of the current Direction stage in `/realize` or files in `/docs`. These units count like scopes.

When a command is given a scope or path argument, only the scopes it selects count.

### 2.4 Execution Procedure

When the +++SWARM condition evaluates to true, execute the following procedure in order. Each step says what to do; §2.5 says which tool does it in your runtime. If a tool listed there is missing in the current environment, use the next option in the same cell, or run the assignments sequentially. Never invent a tool.

**Step 1 — Create team**

When the runtime has an explicit team primitive, create a team named `{team}`. Otherwise record the scope assignment locally and continue.

**Step 2 — Scale**

Evaluate scope count per §2.3 to determine worker count and scope assignment. With `batch: none` and overflow, queue the remaining assignments (as tasks when the runtime has a task list).

**Step 3 — Spawn workers**

For each assignment, start one worker with the runtime's parallel primitive for the `type:` role, labeled `{spawn}` with the scope resolved, in the background where the runtime allows. The prompt is `each:` with `{scope}` or `{scopes}` resolved, plus what a worker without the lead's conversation could not see: the scope's paths from design.md, the Experience items the scope serves, the principles that apply, the Binding Decisions for the scope, the Direction stage it works on, the scope's validation commands, the rows the user approved for this phase (verbatim, in an apply or fix phase), and in `/realize` the approved plan. The prompt names the files and the design.md sections the worker reads; the worker does not reload the guidance file or design.md in full, because the prompt is its context. The prompt also states that the worker starts no workers of its own (only the lead fans out) and, for an `Explore` worker, that the work is read-only (§2.2): an adapter that removes those tools enforces this, and the prompt states it in every runtime (§2.5). If the runtime has no parallel primitive, the lead executes the assignments itself under the same reporting contract, one by one or with the parallel reads §2.5 allows.

**Step 4 — Monitor**

Wait for workers through the runtime's completion signal; do not poll. With `batch: none`, start a queued assignment when a worker finishes. Once a worker reports a STOP condition, start no queued assignment: collect the running workers, then execute the STOP (Step 5).

**Step 5 — Collect**

After all workers complete, integrate results following the `collect:` field instructions. A worker that failed or returned nothing is reported as such, never dropped silently. A worker cannot end the user's turn: a worker that meets a STOP condition (a DETECT with `+++STOP: on D{n}`, or a human gate) stops its work and reports it, and after collecting, the lead executes that STOP (§1.5).

**Step 6 — Shutdown**

Release what Step 1 created, if anything (team resources and open workers).

### 2.5 Runtime Adapters

Among the protocol and the command files, this table is the only place where runtime tool names appear. Settings a runtime needs on its own side live in that runtime's adapter: for Claude Code, `.claude/settings.json`, `.claude/agents/`, and `.claude/hooks/`, plus the design.md import line in `.claude/CLAUDE.md`; for Codex, `.codex/` (`config.toml`, `agents/`, `hooks.json`, `hooks/`, `rules/`) plus the project `AGENTS.md`. The adapter is installed once at the user level (the same files under `$HOME/.claude/` and `$HOME/.codex/`, by DDL's `bin/install.sh`) or copied into a project; this table names the project paths, and the user-level paths are the same files under `$HOME`. Hooks, agent definitions, and permission rules name tools, which is allowed there and nowhere else. The adapter enforces what the harness can decide mechanically; where an adapter is absent or not trusted, every rule below holds as an instruction, unchanged. To support another runtime, add a column and its adapter; command files do not change. When a runtime renames or removes a tool, edit this table and that adapter only.

| Concern | Claude Code | Codex | No adapter |
|---------|-------------|-------|------------|
| Invocation | `/command` | `$command` (skill) | ask for the command by name |
| Protocol lookup (Phase 0, step 1) | the project's copy `.claude/skills/ddl-protocol/SKILL.md` (or the file the project's instruction file names as the protocol), then the user-level copy `$HOME/.claude/skills/ddl-protocol/SKILL.md` | the project's copy `.agents/skills/ddl-protocol/SKILL.md` (or the file the project's instruction file names as the protocol), then the user-level copy `$HOME/.codex/skills/ddl-protocol/SKILL.md`; the protocol skill is the same text as the Claude Code one | the file the project's instruction file names as the protocol |
| Runtime guidance (Phase 0, step 2) | `CLAUDE.md` or `.claude/CLAUDE.md` | `AGENTS.md` | the runtime's project instruction file |
| Loaded at session start / on invocation / after compaction | At start: the user `CLAUDE.md`, the project `CLAUDE.md` or `.claude/CLAUDE.md` (which imports design.md when the adapter is installed), and the automatic memory file; nested `CLAUDE.md` and path-scoped rules load on demand. A command skill loads its body on `/name`; its frontmatter keeps the model from starting it on its own (`disable-model-invocation`) and shows the user an argument hint; the protocol skill lists its name and description and loads its body when read or used. After compaction the project `CLAUDE.md` and the automatic memory are re-injected from disk, and the adapter's SessionStart hook re-states a pending report; the conversation is summarized, and early instructions may be lost (Claude Code docs, 2026) | At start: the `AGENTS.md` chain (global, then project root down to the working directory), read once per run before any work; the adapter's SessionStart hook injects design.md at start and after compaction when the applicable SessionStart hook is enabled and trusted; a skill lists its name and description and loads its body on `$name`, and `agents/openai.yaml` (`allow_implicit_invocation: false`) keeps Codex from starting a command skill on its own; memories are injected when `memories.use_memories` is on and are a recall layer, not a source of rules (Codex docs, 2026). Compaction summarizes the conversation | whatever the runtime documents; assume only the conversation summary survives |
| design.md loading (Phase 0, step 3) | `@../design.md` import in `.claude/CLAUDE.md` (`@design.md` from a root `CLAUDE.md`), loaded with the file at session start; subagents receive it unless their definition sets `omitClaudeMd`. Observed 2026-10-18 (Claude Code 2.1.302): a fresh session quoted design.md without reading a file, and an import whose file does not exist is skipped silently, so a project without design.md loses nothing | SessionStart hook injects design.md as additional context on startup, resume, compact, fork, and clear (`additionalContextLimit: 0`); observed 2026-10-18 in `codex exec` | Phase 0 reads it |
| Project copy and overlay | A project's own copy `.claude/skills/<name>/SKILL.md` runs even when a user-level copy `$HOME/.claude/skills/<name>/SKILL.md` exists: Claude Code lists the user-level skill first, and the command's Phase 0 follows the project's copy. `commands/<name>.md` at the project root adds project facts to the command unless it declares itself a full override | `.agents/skills/<name>/SKILL.md` and `$HOME/.codex/skills/<name>/SKILL.md`, same rule (Codex lists both under the same name); `commands/<name>.md`, same rule | `commands/<name>.md`, same rule |
| Team primitive (SWARM Step 1) | TeamCreate / TeamDelete, only in environments that provide them; otherwise the session's workers form one implicit team | none | none |
| Parallel primitive (SWARM Step 3) | Agent tool, one call per worker: `subagent_type` from `type:` (`explorer` for read-only work and `worker` for writers when the adapter's `.claude/agents/` definitions are installed; otherwise the built-in `Explore` and `general-purpose`); workers run in the background (pass `run_in_background` only where the tool accepts it). Pass `name` (the `spawn:` label) only to writers or to workers you will continue with SendMessage: a named spawn runs as a teammate with write tools even when `subagent_type` is `Explore` (observed 2026-10-17), while the adapter's `explorer` and `worker` keep their `disallowedTools` whatever the name. An unnamed `Explore` worker cannot edit files but still has Bash, and a `general-purpose` worker has the Agent tool itself (observed 2026-10-17); the adapter's definitions remove both, and the prompt states read-only work and no nesting in every case. A `fork` worker inherits the lead's conversation; the others start fresh. With a team primitive: the same call with `team_name`, plus TaskCreate / TaskList for queued work | Subagents (on by default; `agents.enabled`): `Explore` → custom agent `explorer`, `general-purpose` → custom agent `worker`, each a standalone file in `.codex/agents/` with `name`, `description`, `developer_instructions`. The lead spawns with `agent_type` set to that agent and the `spawn:` label as `task_name`, and passes `fork_turns = "none"` because the prompt is self-contained (codex-cli 0.160.1). Subagents inherit the parent session's sandbox and approval settings and an agent file cannot change them, so the instructions enforce read-only work. A subagent may fork the lead's conversation (`fork_turns`) and may spawn agents of its own; DDL workers keep the self-contained prompt and do not spawn. Without subagents: parallel shell reads for read-only work, otherwise one by one. The adapter's `.codex/config.toml` sets `[agents] max_concurrent_threads_per_session = 5` to match the blocks' `max: 5`; the user-level install does not write `config.toml`, so set the same cap in `~/.codex/config.toml` by hand (doctor reports when it is missing) | run the assignments inline, one by one |
| Worker roles (`type:`, §2.2) | `.claude/agents/explorer.md` (`disallowedTools`: Edit, Write, NotebookEdit, Agent, SendMessage, TaskCreate, TaskUpdate) and `.claude/agents/worker.md` (`disallowedTools`: Agent, SendMessage, TaskCreate, TaskUpdate), both with `omitClaudeMd: true` and the standing contract in the body; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in the settings `env` disables nesting. Observed 2026-10-18 (Claude Code 2.1.302, fresh session): `explorer` had no Edit, Write, or Agent tool and `worker` no Agent tool (a call fails with "No such tool available"), neither received CLAUDE.md or the imported design.md, and both saw the depth variable; Bash stays, so read-only shell use remains an instruction. Definitions added while a session runs appear only after the session reloads them | `.codex/agents/explorer.toml` and `worker.toml`; an agent file cannot change the sandbox or the approval policy, so read-only work and no nesting are kept by the instructions | the prompt states the role |
| Completion signal (SWARM Step 4) | background completion notification; SendMessage to continue a worker | agent result | — |
| Mutating tools (§1.5), for example | Edit, Write, NotebookEdit, non-read-only Bash, TaskCreate, TaskUpdate, starting any worker or continuing one with SendMessage, and any MCP or connector tool that creates, updates, sends, publishes, or deletes | file edits (apply_patch), shell commands that write, starting or messaging any agent, and any MCP tool that creates, updates, sends, publishes, or deletes | any file write, side-effecting command, external write, or worker start or message |
| Human choices (§1.5) | Use `AskUserQuestion` for one approval question covering the complete current review set, with concrete action options and optional free text. If the user requests a subset, use native `multiSelect` when the exposed schema supports it, or offer compatible subsets; do not ask an approval question for every item. Wait for the actual submitted answer. An empty result, dismissal, or auto-continue timeout is not approval even if an option is returned; verify explicit human submission. Observed 2026-11-01 in Claude Code 2.1.316: idle auto-resolution includes host-only `afkTimeoutMs`, including when selected answers are returned; the gate excludes this result from human-input boundaries. An ordinary submission under the same timeout setting omits that field. An answered question can be human input without approving its proposed action | Prioritize the GUI experience and make known CLI limitations prominent in the Codex README. Use an available tool whose actual contract permits the decision: `request_user_input_async` in hosts that expose it for approval, with one whole-set approval question. For a requested subset, use only the exposed capabilities: the async schema observed here has `questions`, `title`, and `options`, with no multi-select field. Offer compatible subsets as choices, or a grouped form when a permitted interface supports it; do not invent a `multiSelect` parameter or default to per-item approval turns. Its `accepted: true` return is only receipt; end the turn and wait for the user reply. Observed 2026-11-01: the reply's `send_user_message_question_reply` envelope carries the question ID, question, and answer, and the rollout records a `UserMessage` boundary already recognized by the gate. `request_user_input` is Plan-only in some hosts and disallowed for permission requests in Default; do not use it outside its declared purpose or switch modes to bypass that restriction. The host must keep the pending question answerable after the assistant turn ends. Observed 2026-11-01 in Codex CLI 0.166.0 Default: the async call and receipt were real, but the selector was cleared at turn completion before a reply could be delivered. This CLI route is not approval-capable: explain the limitation and stop rather than use it or switch modes. The desktop host observed here retained actual click replies; do not generalize this to all hosts | Use a permitted native choice interface when available; otherwise explain the missing capability and stop unapproved, without a typed-choice fallback |
| STOP and resume (§1.5) | Make the native question the final tool interaction while waiting. A genuine synchronous human answer can resume the approved scope; no repeated typed approval is needed. Background worker notifications and messages from teammates or other sessions never approve anything | After the report and asynchronous question receipt, end the turn and wait for the actual report-specific answer; agent results and request acknowledgments are not approvals. The configured `UserPromptSubmit` clears the pending marker; question invocation does not | Wait for actual human input; receipt is not an answer |
| +++STOP enforcement (§1.5, the gate) | The gate hook `.claude/hooks/ddl_gate.py`, wired in `.claude/settings.json`: after an assistant message with a line-initial `+++DDL_REPORT` and until the next human message, PreToolUse checks covered calls through a catch-all matcher (`matcher: "*"`), permitting only exact known safe reads, human-question tools, and the bounded read-only shell forms; other covered calls are denied; Stop records the report and UserPromptSubmit clears it, a fallback for an unreadable transcript; SessionStart (`compact`, `resume`) re-states that a report awaits approval. State files live under `$TMPDIR/ddl-gate` (`DDL_GATE_STATE_DIR` overrides it): `<session>.pending` and `<session>.warned`, the latter so the unreadable-record warning appears once per session. The transcript is written asynchronously (Claude Code docs), so a same-turn continuation can escape the gate; the rule then holds as an instruction. An answered AskUserQuestion and an approved plan count as the human speaking. Whether a reply is an approval stays the assistant's judgment (Resume rule). Ordinary Git commit/push also needs the content-bound native submission checked in the Git review row below. Checked against this repository's live transcript on 2026-10-18 (Claude Code 2.1.302): deny after a report, allow after the plan approval, 0.04 s per call | The same script, `.codex/hooks/ddl_gate.py`, wired in `.codex/hooks.json` with a catch-all tool-hook matcher (`matcher: "*"`); exact safe native reads and input-checked polling pass, while unknown tools, arbitrary code wrappers, and starting, messaging, or resuming workers do not; a Stop hook records the report and UserPromptSubmit clears it, because `transcript_path` may be null. Project-local configuration requires project trust; user-level hooks are independent of project trust. Review new or changed hooks in `/hooks` when the host requests it. See [Codex hook configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#hooks) (checked 2026-11-01). Observed 2026-10-18 (codex-cli 0.163.0, `codex exec`): `transcript_path` was set, the same-turn `apply_patch` and `echo hi > file` were denied with the reason shown to the model, `git status --short` passed, and design.md was injected at session start | instruction only |
| Git content review (§1.6) | The same Python hook independently denies unreviewed ordinary commit/push calls. It matches a prepared review with the actual `AskUserQuestion` request/result ID, exact labels, and human-source submission; timeout and unprovable results do not grant permission. Use the preparation procedure below | The same guard applies even under `never`, `bypassPermissions`, or `dontAsk`. It matches the actual `request_user_input_async` call ID to the submitted `UserMessage` reply, question, and selected action. Unsupported or unreadable reply formats deny the operation. Use the preparation procedure below | No mechanical guarantee without a supported adapter; preserve the same review rule as an instruction |
| Outward actions and attribution (+++NEVER) | `permissions.ask` rule `Bash(git push *)` in `.claude/settings.json` (asks in every permission mode) and `attribution` set to empty | `.codex/rules/ddl.rules`: `prefix_rule` with `decision = "prompt"` on `git push`. Independently of STOP state, the gate denies recognized static push forms that miss that prefix (for example Git global options or explicit wrappers), with an actionable canonical retry and no command rewriting or affirmative allow. Absolute host Git paths retain native executable resolution. Explicit `bypassPermissions`/`dontAsk` hook modes skip only this form guard; STOP still applies. A session whose approval policy never prompts shows nothing, and the approval in the `/commit` report still applies. Codex adds no attribution | instruction only |
| `+++DDL_PHASE` | SHOULD, for long sessions | MUST (Codex is execution-forward; the marker keeps the checkpoint visible) | SHOULD |
| `+++DDL_REPORT` | MUST at every STOP (§1.5) | MUST at every STOP (§1.5) | MUST at every STOP (§1.5) |


**Gate coverage and shell forms (2026-10-19, clarified 2026-11-01).** Both adapters use a catch-all matcher for tool hooks; classification covers the tool paths the runtime dispatches through those hooks, not every transport or hosted operation. Safe tool names are runtime-specific; polling is allowed only without input or termination on paths that reach the hook. A question tool or its receipt does not clear pending state. Shell checks accept literal arguments and explicit display/search option profiles, including `sed -n '1,10p' file`; general sed/awk programs, environment overrides, expansions, unknown options and execution helpers are denied while STOP is pending. Use `cat`, `head`, `tail`, `rg`, or a supported display form to clarify a report. Unknown syntax is a policy denial; unexpected internal errors retain fail-open behavior. This static guardrail does not sandbox ambient executable/configuration behavior or inspect arbitrary programs, aliases, or dynamically constructed pushes.

**Git review preparation (§1.6).** Run the installed gate with `prepare-git-review --runtime claude` or `--runtime codex`, passing JSON on stdin. The paths are `$HOME/.claude/hooks/ddl_gate.py` and `$HOME/.codex/hooks/ddl_gate.py`; in this repository the development source is `tools/ddl_gate.py`. For example:

```json
{"language":"en","operations":[{"cwd":"/path/to/repository","command":"git commit --cleanup=verbatim -F /path/to/message.txt"},{"cwd":"/path/to/repository","command":"git push origin main"}]}
```

Omit pushes unless explicitly requested. A batch supports one ready commit per repository and compatible pushes; a commit must precede its dependent push in the input. Preparation returns `reviewId`, `report`, `question`, and a runtime-specific `nativeRequest`. Show the ID and link the report before asking. Pass `nativeRequest` unchanged as the arguments to `AskUserQuestion` in Claude or `request_user_input_async` in Codex. The hook compares the complete request, including labels, descriptions, and selection mode. In Codex, end the turn and wait after the request receipt. A failed or unavailable native choice cannot be replaced by a fabricated receipt or typed approval.

The helper snapshots the real staged set, so staging is reversible review preparation before this STOP, with no discard of unrelated user changes. Ordinary commits use a named branch and `--cleanup=verbatim` with `-m` or a UTF-8 `-F` file. Ordinary pushes name one configured remote and one branch/refspec; use `--no-follow-tags` when follow-tags is enabled, and `--recurse-submodules=no` when configuration could push submodules. Forced, mirror, deletion, wildcard, multi-target, merge/rebase/cherry-pick/revert-in-progress, intent-to-add, stdin-message, alternate-executable, dynamic, and compound write forms are unsupported and must stop with the reason; do not silently drop required options. Use the shell tool's working directory for the intended repository. Git read commands keep working without a content approval.

Review JSON, a human-readable report, and diff files live under `<state dir>/git-reviews/<review-id>/`. These files contain no approval flag: the submitted native answer must still be proved from the current conversation record. Missing or altered detail denies recognized commit/push calls. An ordinary UserPromptSubmit immediately revokes older preparations even before the transcript flushes; a possible matching Codex native submission is preserved pending full request/result proof. Resume/compaction invalidates old preparations through the session epoch as well as the transcript boundary. General STOP failures still warn and fail open; an unprovable recognized Git review fails closed inside a running handler. Runtime-level hook failure/timeout can still fail open; verification uses a shorter internal time budget to leave timeout headroom. Installation diagnostics check unapproved commit/push rejection through both adapters, including OPEN/null records and no-confirmation modes. Simulated dispatch does not prove a new host's live choice or hook transport.

The push form guard does not implement confirmation: supported literal `git push ...` reaches native rules without a hook grant. Retry in the tool's intended working directory only when the original Git options/configuration keep the same meaning; otherwise explain the limitation. Deterministic tests execute configured hook commands and cover both installation layouts, but do not prove native hook trust or interactive approval UI behavior. The installed Codex 0.163.0 binary maps approval policy `never` to hook mode `bypassPermissions` and other policies to `default` (binary inspection, not a captured live payload); `dontAsk` is accepted as the documented explicit no-confirmation mode.

---

## 3. design.md Sections

design.md is the shared notebook between human and LLM, loaded at session start by the runtime adapter (§2.5) or, without one, read by Phase 0, so it carries what the human agreed to and nothing else: agent progress and automatic memory stay out of it. Commands read and write these sections by heading name. A project may keep its notebook in other files (for example a library whose README and guides are its living specification) when its runtime guidance names them; commands then read and write those files wherever this protocol or a command says design.md. A project uses only the sections it needs and may keep other headings. Experience comes first: Binding Decisions, Direction, and Acceptance Gates serve the Experience and never contradict it.

| Section | Holds | Written by | Read by |
|---------|-------|------------|---------|
| `## Intent` | Why the project exists | human | every session, because design.md loads at session start; no command extracts it |
| `## Scopes` | Scope table; drives SWARM | human, `/reflect` | every command whose units are scopes; a command that fans out over other units (for example document pairs) reads none |
| `## Principles` (or `## Core Principles`) | Design principles | `/draft` (D5), `/reflect` | `/draft`, `/realize`, `/reflect` |
| `## Experience` | Consumer-side usage: inputs, outputs, and error / empty / boundary states | `/draft`, `/reflect` (additions found in code) | `/draft`, `/realize`, `/reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) because the Experience depends on them, an external constraint requires them, or the human prefers them and says so | the human, through `/draft`; `/realize` records a delegated choice after the human approves it in the plan; a change the human approves in `/realize` or `/reflect` (D6) | `/draft`, `/realize` (honors), `/reflect` (checks), `/refactoring` (keeps) |
| `## Direction` | Non-binding outlook on the path to implementation | `/draft`; `/realize` writes the `Approved plan` lines and the gate marks (`approved in advance`, `passed`); `/reflect` replaces passed stages and deletes their `Approved plan` lines | `/draft`, `/realize` (follows), `/reflect` (retires) |
| `## Acceptance Gates` | What must hold when done: mechanical gates and human gates | `/draft`; `/realize` marks gates passed; `/reflect` retires it after acceptance | `/draft`, `/realize`, `/validate`, `/reflect` (retires) |
| `## Validation` | Per-scope mechanical checks | human, `/reflect` | `/validate`, `/realize`, `/commit`, `/refactoring` |

**Binding Decisions.** One row per decision:

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: Language — options TypeScript / JavaScript (delegated to /realize)
```

- `Why it binds` names an Experience item, an external constraint (organization standard, existing system, hosting), or a stated preference. A row without a reason or a source is incomplete.
- `Source` quotes the human's words with the date. When the human approves a report that listed the row, that approval is the source (for example `approved /draft report (2026-10-17)`).
- Technology already present in the code is an existing premise: commands show it in their reports, and design.md does not record it, because the code already does. It becomes a row only when the human gives a reason. A decision found only in the harness's automatic memory is at most such a premise: commands show it in their reports, and it binds nothing until the human records it here.
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
| S0 | Settle the search API as a CLI | sample CLI output | `npm test` |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval |
```

- Non-binding. `/realize` follows it by default and reports every deviation (merged, reordered, or skipped stage).
- The lanes of a stage are the units `/realize` fans out (§2).
- When the user approves the `/realize` plan, `/realize` writes its durable parts under the table as `Approved plan (<date>): files to touch, approach, Unbound choices made`, so a later or compacted session rebuilds worker prompts from it instead of from a summary. `/reflect` deletes these lines with the stages they served.
- Gates in the `Gate` column run at the end of their stage: a mechanical gate is a validation command, and a human gate is executed as `+++STOP` unless the human approved it in advance (§1.5). Compatible human gates ready at that boundary are reviewed in one batch, including the last stage's gates and final Acceptance Gates when all evidence is ready. Gates are never dropped: a merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates.
- `/reflect` replaces stages whose gates are all marked passed with their outcome, and deletes the section when every stage is done. When design.md is under version control, the history stays there; otherwise `/reflect` quotes the removed stages in its REPORT.
- Direction is the most temporary part of design.md. Retiring it, like retiring Acceptance Gates, also shrinks what every later session loads.

**Acceptance Gates.** A list of conditions for done:

- Mechanical gates are commands, each with the expected result when the command does not fail by exit code alone. `/realize` runs them in VALIDATE, and `/validate` runs them with the Validation block.
- Human gates are approvals. At the end of the work, `/realize` names all compatible ready human gates in one `+++STOP` review set (§1.5), collects one batch submission, and marks each approved gate passed. It does not ask again for each gate.
- The work is accepted when every gate is marked passed. `/reflect` then retires the section: mechanical gates that should keep running move into the Validation block first.

**Passed marks.** A gate passes when its command gives the expected result, or when the human approves it at the gate or in advance (§1.5). `/realize` appends `passed <date>` to each gate that passes, in the stage's Gate cell for Direction (for example `human approval, passed 2026-10-20`) and after the gate for Acceptance Gates. An advance approval is written in the same place the moment the user gives it, as `approved in advance (<date>)`; when the stage or the work ends, `passed <date>` follows it, so a waived gate reads `human approval, approved in advance (2026-10-20), passed 2026-10-21`. These marks are the record of progress and acceptance: `/reflect` reads them and never infers a pass from conversation memory.

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

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex).
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract relevant items
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
Decision: {approve the complete current review set, select or revise it, or hold}
Recommendation: {preferred action, reason, and any material downside or unknown}
Consequence: {what each selection authorizes or changes}
Review detail: {the complete evidence this command requires, accessible before approval}
Choices: {one batch approval interaction per §1.5; item selection only when requested}

### Phase 4: EXECUTE (if applicable)

**Pre-condition.** Enter this phase only after explicit user approval of its scope at the Phase 3 STOP gate (per §1.5 of the protocol). If the actual answer does not authorize this work, return to Phase 3 and re-present the current decision.

+++SWARM: 2+ approved changes across scopes

```
  team: command-execute
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to {scope} the approved changes listed in this prompt, and nothing else.
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
