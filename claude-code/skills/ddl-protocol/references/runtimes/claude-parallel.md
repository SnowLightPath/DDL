# Claude Code: parallel work

## Read when

Read this before step 3 (Spawn) of the shared [parallel work](../parallel-work.md) procedure. It maps the `+++SWARM` operands to the Claude Code primitives and the adapter's roles.

## Mapping

| Concern | Procedure |
|---|---|
| Team primitive | `TeamCreate` / `TeamDelete` only in environments that provide them; otherwise the session's workers form one implicit team. With a team: the same spawn call with `team_name`, plus `TaskCreate` / `TaskList` for queued work (`batch: none`). Only the lead fans out. |
| `type: Explore` | `Agent` with `subagent_type: explorer` when `.claude/agents/explorer.md` is installed (`disallowedTools`: Edit, Write, NotebookEdit, Agent, SendMessage, TaskCreate, TaskUpdate; `omitClaudeMd: true`); otherwise the built-in `Explore`. State read-only work in the prompt in every case. |
| `type: general-purpose` | `Agent` with `subagent_type: worker` when `.claude/agents/worker.md` is installed (`disallowedTools`: Agent, SendMessage, TaskCreate, TaskUpdate; `omitClaudeMd: true`); otherwise the built-in `general-purpose`. |
| `spawn` | One `Agent` call per worker; the `spawn:` label identifies the worker in the report. Pass it as `name` only to writers or to workers you will continue with `SendMessage`: a named spawn runs as a teammate with write tools even when `subagent_type` is `Explore`, while the adapter's `explorer` and `worker` keep their `disallowedTools` whatever the name. Both adapter roles omit `CLAUDE.md` and the imported design.md, so the prompt names the files and sections to read. |
| Background | Pass `run_in_background` where the tool accepts it. A `fork` worker inherits the lead's conversation; the others start fresh, so the prompt carries the whole assignment. Definitions added while a session runs appear only after the session reloads them. |
| Completion | Wait for the background completion notification; do not poll. Continue a worker with `SendMessage` only when needed. A worker's message never ends the user's turn or approves anything. |
| Nesting | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in the settings `env` disables nested spawning, and both role definitions disallow `Agent`. State "no workers of your own" in the prompt anyway. |
| Concurrency | At most `max` workers at once (default 5); queue the rest with `TaskCreate` under a team, otherwise start them as workers finish. |
| Fallback | Without the `Agent` tool, the lead runs the assignments inline one by one under the same reporting contract. |

## Observed

| Fact | Version | Date |
|---|---|---|
| A named spawn with `subagent_type: Explore` ran as a teammate with write tools; an unnamed `Explore` worker could not edit files but had Bash; a `general-purpose` worker had the `Agent` tool itself | Claude Code (version not recorded) | 2026-10-17 |
| In a fresh session `explorer` had no Edit, Write or Agent tool and `worker` no Agent tool (a call fails with "No such tool available"); neither received `CLAUDE.md` or the imported design.md; both saw the depth variable; Bash stayed | Claude Code 2.1.302 | 2026-10-18 |

## Coverage

- The adapter removes the editing and agent tools from `explorer` and the agent tools from `worker` (`disallowedTools`), withholds guidance and the notebook (`omitClaudeMd`), and blocks nested spawning (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`), when `.claude/agents/` and the settings `env` are installed and loaded.
- Bash stays in both roles, so read-only shell use is an instruction. A built-in `Explore` or `general-purpose` worker has no mechanical read-only guarantee, and a named built-in teammate has write tools; the role name alone proves nothing.
- A pending STOP in the lead denies worker starts and `SendMessage` through the gate hook (see [approval](claude-approval.md)); collecting a failed, empty or missing result is the lead's instruction, not a mechanism.
