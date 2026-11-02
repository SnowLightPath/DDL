# Codex: parallel work

## Read when

Read before step 3 (Spawn) of [parallel work](../parallel-work.md); it maps `type`, `spawn`, background and completion onto Codex subagents (`agent_type`, `task_name`, `fork_turns`) and the adapter's agent files.

## Mapping

| Concern | Procedure |
|---|---|
| Team primitive | None; the session's subagents form one implicit team. |
| `type: Explore` | `agent_type: explorer` when `.codex/agents/explorer.toml` (`name`, `description`, `developer_instructions`) is installed, else an available `default` agent with the read-only contract in its prompt. |
| `type: general-purpose` | `agent_type: worker` when `.codex/agents/worker.toml` is installed, else an available `default` agent with the writer contract in its prompt; a missing custom role is no reason to drop parallel work. |
| `spawn` | One spawn per worker with the label as `task_name` and `fork_turns = "none"`. |
| Background | Separate threads (`agents.enabled`, on by default) inheriting the session's sandbox and approval settings; a subagent may fork the lead's conversation (`fork_turns`) and spawn agents of its own. |
| Completion | The agent result; wait for it with `wait_agent`, not by polling with input. |
| Nesting | No mechanism; the roles' `developer_instructions` repeat the no-workers rule. |
| Concurrency | `[agents] max_concurrent_threads_per_session = 5` in `.codex/config.toml` matches `max: 5` (by hand in `~/.codex/config.toml`; doctor reports it missing); respect a smaller host limit. |
| Fallback | No subagents: parallel shell reads for read-only work, otherwise one assignment at a time. |

## Observed

| Fact | Version | Date |
|---|---|---|
| `fork_turns` was accepted on spawn; `"none"` started the subagent without the lead's conversation | codex-cli 0.160.1 | 2026-10-17 |
| A persistent run confirmed two default workers' exit 0 after the custom `explorer` symlink failed with `ELOOP`; ephemeral JSON output did not establish the child results | Codex 0.166.0 | 2026-11-02 |

## Coverage

- The adapter supplies the two roles as agent files and the concurrency cap; it enforces nothing inside a subagent, as an agent file cannot remove a tool, narrow the sandbox or block nesting.
- A symlinked custom agent file can fail to load, so confirm the `agent_type` actually used; only a persistent run shows the child results.
