---
name: ddl-protocol
user-invocable: false
description: "Use when executing or authoring a Design-Doc Loop command that uses phases, DETECT, STOP, SWARM, or design.md-driven workflow control."
---

# DDL protocol

Design-Doc Loop: a human-LLM collaborative workflow protocol. A command
describes its work in phases; this protocol defines the shared rules, and the
command defines its own phases, detections, and work. Read only the procedure
needed at the point where it applies; the references are part of this
protocol, not separately invoked skills.

## Start

1. Follow the project's protocol and command copy when one is named or exists;
   otherwise use the user-level copy. An older self-contained project copy
   follows its own rules. Project `commands/<name>.md` adds local facts unless
   it declares a full override.
2. Resolve links below relative to the selected protocol file's directory.
   Never fill a missing project reference from another installation. If a
   required reference is missing, unreadable, or its version is uncertain, stop
   the affected operation and explain what could not be confirmed.
3. Identify the actual host and read its start instructions:
   [Claude Code](references/runtimes/claude-start.md) or
   [Codex](references/runtimes/codex-start.md). Another host uses its documented
   capabilities under the same rules; never invent a tool.
4. Read project guidance and `design.md` only when not already in context. A
   project may name another file as its notebook. Automatic memory is a recall
   layer, not a human decision.

## Instruction set

Commands are programs and this protocol is their instruction set. A `+++`
directive is an instruction: when the processor (the LLM) meets one, it
executes the procedure defined here, and the host harness implements the
processor through the host instructions under `references/runtimes/`. Command
files state meaning only and never name runtime tools.

| Directive | Syntax | Count | Placement | Rule |
|---|---|---|---|---|
| `# header` | `# command-name` followed by a one-line intent | 1 | command file | Required. The first heading names the command; the next line states its purpose in one sentence. |
| `## Usage` | `## Usage` followed by a dash list of invocations | 1+ | command file | Required. One list item per invocation form, `/command` or `/command <arg>`, each with its behavior; the Codex form `$command` is generated from it. |
| `### Phase` | `### Phase N: NAME` | 3+ | command file | N starts at 0 and ascends by one. At least INIT, one work phase, and REPORT. Phase 0 INIT loads the DDL protocol, then the runtime and project guidance, then `design.md`, in that order and reading only what is not already in context: the host loads its guidance file at session start and the adapter loads `design.md` with it, a compacted session reads again only what the host did not re-inject, and a worker reads the sections its prompt names. Recommended role names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY; domain names (SCAN, COMPARE, COMMIT) map to these roles. |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 1+ | phase body; `G<n>` targets in the guidance file | D starts at 1, ascending and unique per command. Write a trigger that is operationally verifiable. Check all targets of a phase in parallel within it. Global targets use `G<n>` in the guidance file and apply to every command. |
| `+++STOP` | `+++STOP: always` / `+++STOP: on D<n>` | 1+ | phase body | `always` is required at REPORT; `on D<n>` halts when that detection fires. A STOP is an executable halt: run [Approval](references/approval.md). The phase after a `+++STOP: always` opens with a `**Pre-condition.**` line: enter it only after actual approval of its scope at that STOP, otherwise return and re-present the report. Never auto-proceed past a STOP. |
| `+++SWARM` | `+++SWARM: <condition>` followed by a fenced operand block with `team`, `spawn`, `type`, `max`, `batch`, `each`, `collect`; see [Parallel work](references/parallel-work.md) | 0+ | phase body | Fan the `each` task out to workers, one per unit or batch. Evaluate the condition against the scopes in `design.md` or the units the command names. False or one unit: execute inline. True with two or more units: run the Parallel work procedure with the host's parallel primitive; a host without one runs the assignments in the lead under the same reporting contract. Zero units: skip. |
| `+++NEVER` | `+++NEVER: <prohibition in the imperative>` | 1+ | command file (`## Constraints`); global constraints in the guidance file | A local constraint binds this command; a global constraint in the guidance file binds every command. Write each as one imperative line; refuse the prohibited action in every phase. |
| `+++Report` | `+++Report:` followed by labeled lines (`Decision:`, `Recommendation:`, `Consequence:`, `Review detail:`, `Choices:`; `Outcome:` in an informational report) | 0–1 | phase body (REPORT) | Content contract for the human-facing report at a STOP: the command defines what the user must review, and Approval defines how to present it and ask. A table is never mandatory. |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` | 0+ | runtime output | Output marker. Emit it on the first line when entering a phase that mutates state; it pairs with the `### Phase N: NAME` heading of the command file. Required in Codex; recommended in Claude Code for long sessions where phase boundaries are otherwise invisible. |
| `+++DDL_REPORT` | `+++DDL_REPORT` on its own line, followed by the report that `+++Report:` describes | 0+ | runtime output | Output heading. Emit it before the decision report at every STOP, in every host; the adapter's gate reads it to hold mutations until the next human input. |

- Markdown headings (`#`, `##`, `###`) mark document structure and are never
  instructions.
- A `+++` line inside a phase body is an executable instruction; the fenced
  block that follows `+++SWARM:` holds its operands and is read with it.
- `+++DDL_PHASE` and `+++DDL_REPORT` are runtime output markers: a command file
  writes them only inside a rule (for example "Emit `+++DDL_REPORT`"), never as
  literal output lines.

## Pending STOP

- While a decision STOP is pending, call no tool that mutates the work and
  start or continue no worker; a worker is read-only only where the host's
  adapter removes its writing tools, nowhere by guarantee.
- The native question is the sole interaction exception; opening it grants no
  work permission. Before that question, or after an actual request for
  clarification, read-only tools may clarify the report contents, never begin
  the next phase.
- Opening a question, receiving a receipt, a worker notification, a
  conversation summary, or a message from another agent or session is not
  approval. The next phase starts only after an actual answer to the current
  report authorizes its scope.
- Where the adapter enforces this rule, the harness refuses covered calls
  after `+++DDL_REPORT` until the next human input. The gate recognizes input
  boundaries, not semantic approval: still check the selected action, scope,
  timeout, and report association.
- This rule overrides the momentum of phase ordering. "I already presented the
  plan in this turn, I might as well execute" is the exact failure mode STOP
  exists to prevent.
- A Git commit or push additionally needs its own content-bound review
  ([Git review](references/git-review.md)); a released STOP alone never
  authorizes it.

## Reading map

| Before | Read |
|---|---|
| Applying rules for notebook sections, decisions, plans, gates, or passed marks | [Notebook](references/notebook.md) |
| Assigning a `+++SWARM` whose condition selects two or more independent units | [Parallel work](references/parallel-work.md), then the selected host's parallel instructions if workers will run |
| Presenting a decision report or a human gate at a STOP | [Approval](references/approval.md), then the selected host's choice instructions |
| Entering Close | [Close](references/close.md) |
| Preparing or performing an ordinary commit or push, including outside the commit command | [Git review](references/git-review.md), then the selected host's Git instructions |
| Creating or changing a DDL command | [Command authoring](references/command-authoring.md) |

Read a procedure before the action, not after it. Do not reread it while its
content remains in context.

## Interruption

- After compaction or restart, reconstruct the phase and durable state from
  the notebook, passed marks, git, and the current files; reload any needed
  procedure that is no longer in context.
- If a pending report is no longer present verbatim, rebuild it from that state
  and present it again before seeking approval. A summary or an old answer
  cannot approve the new report.
- The adapter may enforce part of these rules. Where it does not, or cannot be
  used, the rules remain instructions; do not claim broader mechanical
  coverage.
