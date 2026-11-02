# Claude Code: start

Read this for Claude Code. Project `.claude/skills/<name>/SKILL.md`, or the
file named by project guidance, takes precedence over `$HOME/.claude/skills/`.
The project may add `commands/<name>.md` as an overlay.

Claude loads `CLAUDE.md` or `.claude/CLAUDE.md` at session start. The adapter
imports the notebook from that guidance file. After compaction, guidance and
automatic memory are re-injected; early conversation instructions may still
be lost. Re-read only what is no longer in context. The protocol loads when a
command needs it; command skills are invoked by the user.

The adapter is `.claude/settings.json`, `.claude/agents/`, and
`.claude/hooks/`, plus the notebook import. The user-level install uses the
corresponding paths under `$HOME/.claude/`. If an adapter is missing or
untrusted, the protocol's rules still apply as instructions.

When needed, read [approval](claude-approval.md),
[parallel work](claude-parallel.md), or [Git review](claude-git.md).
