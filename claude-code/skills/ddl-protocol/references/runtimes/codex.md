# Codex: start

Read this for Codex. Project `.agents/skills/<name>/SKILL.md`, or the file
named by project guidance, takes precedence over `$HOME/.codex/skills/`.
The project may add `commands/<name>.md` as an overlay.

Codex loads the `AGENTS.md` chain at session start. The trusted and enabled
adapter's SessionStart hook injects the notebook at start and after compaction.
The conversation is summarized at compaction; reload what is no longer in
context. A command skill is invoked by the user. Emit `+++DDL_PHASE` on entry
to a mutating phase.

The adapter is `.codex/` and project `AGENTS.md`; user-level hooks live under
`$HOME/.codex/`. Project-local configuration needs project trust; user-level
hooks are independent of that trust. If an adapter is missing or untrusted,
the protocol's rules still apply as instructions.

When needed, read [approval](codex-approval.md),
[parallel work](codex-parallel.md), or [Git review](codex-git.md).
