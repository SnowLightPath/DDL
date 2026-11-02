# Claude Code: parallel work

Read this before starting workers under [parallel work](../parallel-work.md).
Use the `Agent` tool and the adapter's `explorer` for read-only work or `worker`
for writing when those roles are installed. Otherwise use available built-in
roles and state the same contracts in the prompt. Start workers in the
background where supported; wait for completion notifications.

Use `TeamCreate` / `TeamDelete` and task tools only if the host exposes them;
otherwise the worker set is an implicit team. The lead alone fans out.

The adapter's role definitions disallow worker spawning; `explorer` also
disallows editing tools. Both omit the instruction file and imported notebook,
so provide the needed context in the prompt. Bash remains available: read-only
shell behavior is an instruction. In the built-in `Explore` fallback, a named
teammate was observed to have write tools (2026-10-17); do not rely on the role
name alone for a mechanical read-only guarantee. Pass a name only when
needed for a writer or continued worker.
