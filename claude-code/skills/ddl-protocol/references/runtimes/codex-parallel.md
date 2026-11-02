# Codex: parallel work

Read this before starting workers under [parallel work](../parallel-work.md).
Use the host's subagent primitive, mapping `Explore` to the adapter's
`explorer` role and `general-purpose` to `worker` when exposed. Supply the
resolved assignment as a self-contained prompt and use `fork_turns = "none"`.
If a custom role is unavailable, use an available `default` agent and put the
same read-only or writer contract in its prompt. Do not invent an unavailable
agent type or drop parallel work merely because a custom role is missing. If no
usable parallel primitive is available, follow the shared sequential fallback.

Subagents inherit the parent sandbox and approval settings. Their role files
cannot enforce a narrower sandbox, so read-only work and no nested workers are
instructions in every prompt. Only the lead fans out. If no explicit team
primitive exists, treat the workers as an implicit team.

The project adapter sets `[agents] max_concurrent_threads_per_session = 5`;
the user-level install does not write `config.toml`. Set that cap in the user
configuration if desired; respect a smaller host limit. Without subagents,
parallel shell reads may be used for read-only work, otherwise work one by one.
