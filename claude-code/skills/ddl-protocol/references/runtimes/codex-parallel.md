# Codex: parallel work

## Read when

Read this before step 3 (Spawn) of the shared [parallel work](../parallel-work.md) procedure. It maps the `+++SWARM` operands to Codex subagents and the adapter's agent files.

## Mapping

| Concern | Procedure |
|---|---|
| Team primitive | None. The session's subagents form one implicit team; only the lead fans out. |
| `type: Explore` | Spawn with `agent_type: explorer` when `.codex/agents/explorer.toml` (`name`, `description`, `developer_instructions`) is installed; otherwise an available `default` agent with the same read-only contract in its prompt. State read-only work in the prompt in every case: an agent file cannot narrow the sandbox. |
| `type: general-purpose` | Spawn with `agent_type: worker` when `.codex/agents/worker.toml` is installed; otherwise an available `default` agent with the writer contract in its prompt. Do not invent an unavailable agent type and do not drop parallel work because a custom role is missing. |
| `spawn` | One spawn per worker with the `spawn:` label as `task_name` and the resolved assignment as a self-contained prompt; pass `fork_turns = "none"` because the prompt carries the whole assignment. The label identifies the worker in the report. |
| Background | Subagents run as separate threads (`agents.enabled`, on by default) and inherit the parent session's sandbox and approval settings. A subagent may fork the lead's conversation (`fork_turns`) and may spawn agents of its own; DDL workers do neither. |
| Completion | The agent result is the completion signal; wait for it (`wait_agent`) instead of polling with input. A result never ends the user's turn or approves anything. |
| Nesting | No mechanism: state "no workers of your own" in every prompt; the adapter's `developer_instructions` repeat it. |
| Concurrency | `[agents] max_concurrent_threads_per_session = 5` in the project `.codex/config.toml` matches `max: 5`; the user-level install does not write `config.toml`, so set the same cap in `~/.codex/config.toml` by hand (doctor reports when it is missing). Respect a smaller host limit. |
| Fallback | Without subagents, use parallel shell reads for read-only work; otherwise run the assignments one by one under the same reporting contract. |

## Observed

| Fact | Version | Date |
|---|---|---|
| `fork_turns` was accepted on spawn; `"none"` started the subagent without the lead's conversation | codex-cli 0.160.1 | 2026-10-17 |
| A persistent run confirmed two default workers' exit 0 after the custom `explorer` symlink failed with `ELOOP`; ephemeral JSON output did not establish the child results | Codex 0.166.0 | 2026-11-02 |

## Coverage

- The adapter supplies the two roles as agent files and the concurrency cap; it enforces nothing inside a subagent: sandbox and approval are inherited from the session, and an agent file cannot remove a tool, narrow the sandbox or block nesting.
- Read-only work, no nested workers and the self-contained prompt are instructions in every prompt (the `developer_instructions` repeat them). A symlinked custom agent file can fail to load; confirm the `agent_type` actually used before trusting a role.
- Collecting a failed, empty or missing result is the lead's instruction, not a mechanism; only a persistent run shows the child results, ephemeral JSON output does not.
