# Authoring a DDL command

Read this when creating or changing a command. A command owns its phases,
work, detection targets, and local constraints; the protocol owns shared
STOP, parallel, notebook, Close, and Git semantics. Do not name runtime tools
in command files.

Every command has INIT, at least one work phase, and REPORT. Number phases from
0. Define operationally verifiable `+++DETECT` targets, numbered uniquely and
in ascending order from D1, and at least one `+++NEVER` constraint. Check the
targets in parallel within their phase. Global targets in runtime guidance use
G numbers. REPORT has `+++STOP: always`. A phase following that STOP starts
with a precondition requiring actual approval of its scope.

## Shared Phase 0

Use these first three lines exactly. Read project-specific guidance, the
notebook, and an applicable overlay only when needed and not already in
context.

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Complete its Start procedure before continuing.
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context; extract relevant items.
4. State the fallback when no notebook exists.

## Work and report

Use `+++SWARM: <condition>` followed by a block with `team`, `spawn`, and
`each`; optional `type`, `max`, `batch`, and `collect` have the defaults in
[parallel work](parallel-work.md). State what each worker must do and report.

Use `+++STOP: on D<n>` for a detection that needs a human decision, and
`+++STOP: always` in REPORT. Describe the decision, evidence and consequences
that the command requires; follow [approval](approval.md) for presentation and
waiting. A read-only report needs no invented approval.

After approval, apply only the approved scope. Verify the result. Name another
command only for work this command cannot do, with the reason. A Close stage
ends with the final Git review, not a command chain.
