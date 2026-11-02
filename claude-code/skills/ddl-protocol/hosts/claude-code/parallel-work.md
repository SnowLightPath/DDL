# Claude Code: parallel work

## Read when

Read before step 3 (Spawn) of [parallel work](../../parallel-work.md); it maps `type`, `spawn`, background and completion onto the `Agent` tool and the adapter's `explorer` and `worker`.

## Mapping

| Concern | Implementation |
|---|---|
| Team primitive | `TeamCreate` / `TeamDelete` where provided, else the session's workers are one implicit team; with a team, spawn with `team_name` and queue work in `TaskCreate` / `TaskList` (`batch: none`). |
| `type: Explore` | `Agent`, `subagent_type: explorer` when `.claude/agents/explorer.md` is installed (`disallowedTools`: Edit, Write, NotebookEdit, Agent, SendMessage, TaskCreate, TaskUpdate; `omitClaudeMd: true`), else the built-in `Explore`. |
| `type: general-purpose` | `Agent`, `subagent_type: worker` when `.claude/agents/worker.md` is installed (`disallowedTools`: Agent, SendMessage, TaskCreate, TaskUpdate; `omitClaudeMd: true`), else the built-in `general-purpose`. |
| `spawn` | One `Agent` call per worker; the label goes in `name` only for writers or workers to continue with `SendMessage`, since a named spawn is a teammate with write tools even under `subagent_type: Explore` (the adapter roles keep `disallowedTools` whatever the name). |
| Background | `run_in_background` where the tool accepts it; a `fork` worker inherits the lead's conversation, the others start fresh; definitions added mid-session load only after a reload. |
| Completion | The background completion notification; `SendMessage` to a worker only when needed. |
| Nesting | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in the settings `env`, and both roles disallow `Agent`. |
| Concurrency | No host cap; hold at `max`, the rest start as workers finish or from the team queue. |
| Fallback | No `Agent` tool: the lead runs the assignments inline, one at a time. |

## Observed

| Fact | Version | Date |
|---|---|---|
| A named spawn with `subagent_type: Explore` ran as a teammate with write tools; an unnamed `Explore` worker could not edit but had Bash; a `general-purpose` worker had `Agent` itself | Claude Code (version not recorded) | 2026-10-17 |
| In a fresh session `explorer` had no Edit, Write or Agent tool and `worker` no Agent tool ("No such tool available"); neither received `CLAUDE.md` or design.md; both saw the depth variable; Bash stayed | Claude Code 2.1.302 | 2026-10-18 |

## Coverage

- Enforced: the `disallowedTools`, `omitClaudeMd` and depth settings above, once `.claude/agents/` and the settings `env` are installed and loaded.
- Bash stays in both roles, so read-only shell use is an instruction, and a built-in `Explore` or `general-purpose` worker has no mechanical read-only guarantee.
