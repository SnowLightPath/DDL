---
name: ddl-protocol
description: "Use when executing or authoring a Design-Doc Loop command that uses phases, DETECT, STOP, SWARM, or design.md-driven workflow control."
---

# DDL protocol

DDL commands describe work in phases. This protocol defines the shared rules;
the command defines its own phases, detections, and work. Read only the
procedures needed at the point where they apply. References are part of this
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
3. Identify the actual host and read its initial guidance: [Claude Code](references/runtimes/claude.md)
   or [Codex](references/runtimes/codex.md). For another host, use its documented
   capabilities and the same rules; never invent a tool.
4. Read project guidance and `design.md` only when not already in context. A
   project may name another file as its notebook. Automatic memory is a recall
   layer, not a human decision.

## Directives

| Directive | Meaning |
|---|---|
| `+++DETECT` | Check the named, operationally verifiable conditions in the current phase. |
| `+++STOP` | Stop when `always` or the named detection fires. A decision requires actual approval of the current report and scope; an informational report ends without requesting approval. |
| `+++SWARM` | When its condition selects two or more independent units, read [parallel work](references/parallel-work.md) before assigning them. If the condition is false or selects one unit, work inline; with zero units, skip. |
| `+++NEVER` | A prohibition from the command or runtime guidance. |
| `+++Report` | The command's content contract for a human-facing STOP report. |
| `+++DDL_REPORT` | Emit this heading before every STOP report. |
| `+++DDL_PHASE` | Emit at the start of a mutating phase: required in Codex, recommended in long Claude sessions. |

While a decision STOP is pending, do not mutate work or start or continue a
worker. Read-only clarification is allowed; opening a question, receiving a
receipt, a worker notification, or a conversation summary is not approval.
The next phase starts only after an actual answer authorizes its scope.

## Read when needed

| Before | Read |
|---|---|
| Applying rules for notebook sections, decisions, plans, or gates | [Notebook](references/notebook.md) |
| Assigning a `+++SWARM` whose condition selects two or more independent units | [Parallel work](references/parallel-work.md), then the selected host's parallel instructions if workers will run |
| Preparing a decision report or human gate | [Approval](references/approval.md), then the selected host's choice instructions |
| Entering Close | [Close](references/close.md) |
| Preparing or performing an ordinary commit or push, including outside the commit command | [Git review](references/git-review.md), then the selected host's Git instructions |
| Creating or changing a DDL command | [Command authoring](references/command-authoring.md) |

Read a required procedure before the action, not after it. Do not reread it
while its needed content remains in context. After compaction or restart,
reconstruct the phase and durable state from the notebook, passed marks, git,
and current files; reload any needed procedure that is no longer in context.
If a pending report is no longer present verbatim, rebuild and present it again
before seeking approval. A summary or old answer cannot approve the new report.

The adapter may enforce part of these rules. Where it does not, or cannot be
used, the rules remain instructions; do not claim broader mechanical coverage.
