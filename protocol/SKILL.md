---
name: ddl-protocol
user-invocable: false
description: "Use when executing or authoring a Design-Doc Loop command that uses phases, DETECT, STOP, SWARM, or design.md-driven workflow control."
---

# DDL protocol

Design-Doc Loop: a human-LLM workflow protocol. A command describes its work
in phases; this protocol holds the shared rules.

## Start

1. Links resolve relative to the selected protocol file (Phase 0 selects it).
2. A missing, unreadable or version-uncertain protocol file stops the
   affected operation: say what is unconfirmed, never fill it from another
   installation.
3. Read the host's start implementation, [{Host}](hosts/{host}/start.md);
   another host uses its documented capabilities. Never invent a tool.
4. Only implementations and the adapter name tools; commands and operations
   state meaning.

## Instruction set

Commands are programs and this protocol is their instruction set: the
processor (the LLM) runs each `+++` directive by the operation defined here,
and the host harness implements the processor as described under `hosts/`.

| Directive | Syntax | Count | Placement | Rule |
|---|---|---|---|---|
| `# header` | `# command-name` and a one-line intent | 1 | command file | The first heading names the command, the next line states its purpose. |
| `## Usage` | `## Usage` and a dash list of invocations | 1+ | command file | One item per form, `/command` or `/command <arg>`, each with its behavior. |
| `### Phase` | `### Phase N: NAME` | 3+ | command file | N from 0, ascending by one; at least INIT, a work phase and REPORT. Phase 0 reads only what is not in context, in the order of its shared lines (Command authoring Example); roles: Command authoring Operands. |
| `+++DETECT` | `+++DETECT:` then indented `D1: name — trigger` lines | 1+ | phase body; `G<n>` in the guidance file binds every command | D from 1, unique and ascending per command; each trigger operationally verifiable; check a phase's targets in parallel. |
| `+++STOP` | `+++STOP: always` / `+++STOP: on D<n>` | 1+ | phase body | `always` is required at REPORT; `on D<n>` halts when that detection fires. A STOP is an executable halt: run Approval, never auto-proceed; the phase after `always` opens with the `**Pre-condition.**` line (Command authoring Formats). |
| `+++SWARM` | `+++SWARM: <condition>` then a fenced operand block (Parallel work Syntax) | 0+ | phase body | Fan `each` out to workers, one per unit or batch. The condition counts scopes in `design.md` or the units the command names; Scale decides inline, skip and batches. |
| `+++NEVER` | `+++NEVER: <prohibition in the imperative>` | 1+ | command `## Constraints`; global in the guidance file | Binds this command, or every command from the guidance file; refuse the prohibited action in every phase. |
| `+++Report` | `+++Report:` then labeled lines (labels: Approval Formats) | 0+ | body of a phase with `+++STOP: always` (REPORT, or a REVIEW filling its role: Command authoring Operands) | Content contract at a STOP: the command says what the user reviews; Approval says how to present and ask. |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` | 0+ | output | Output marker on the first line of a mutating phase, paired with its heading; `hosts/{host}/start.md` says whether it is required. |
| `+++DDL_REPORT` | `+++DDL_REPORT` alone on a line, then the report | 0+ | output | Output heading before the decision report at every STOP, in every host. |

- Markdown headings mark document structure and are never instructions.
- A `+++` line in a phase body is an instruction; the fenced block after
  `+++SWARM:` holds its operands.
- `+++DDL_PHASE` and `+++DDL_REPORT` are output markers: a command file writes
  them only inside a rule, never as output lines.

## Pending STOP

- While a decision STOP is pending, call no tool that mutates the work (an MCP
  or connector tool that creates, updates, sends, publishes or deletes included)
  and start or continue no worker.
- The native question is the sole exception; opening it grants no work
  permission. Before it, or after an actual request for clarification,
  read-only tools may clarify the report, never begin the next phase.

## Reading map

| Operation | Read before | Implementation |
|---|---|---|
| [Approval](approval.md) | A decision report or a human gate at a STOP | [{Host}](hosts/{host}/approval.md) |
| [Parallel work](parallel-work.md) | A `+++SWARM` selecting two or more units | [{Host}](hosts/{host}/parallel-work.md) |
| [Notebook](notebook.md) | Notebook sections, decisions, plans, gates, marks | [{Host}](hosts/{host}/start.md) (at Start) |
| [Close](close.md) | The Close stage or scan | Git review's: [{Host}](hosts/{host}/git-review.md) |
| [Git review](git-review.md) | An ordinary commit or push, in any command | [{Host}](hosts/{host}/git-review.md) |
| [Command authoring](command-authoring.md) | Creating or changing a command | [{Host}](hosts/{host}/start.md) (at Start) |

Read the operation before the action, then its implementation for the current
host.

## Interruption

- After compaction or restart, reconstruct the phase and durable state from
  the notebook, passed marks, git and the current files; reload operations no
  longer in context, and rebuild a pending report not present verbatim before
  presenting it again.
- An adapter that does not enforce a rule, or cannot be used, leaves the rule
  an instruction; claim no broader coverage.
