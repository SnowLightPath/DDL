# Claude Code: approval

Read this before presenting a decision STOP, together with the shared
[approval procedure](../approval.md).

Use `AskUserQuestion` for one choice covering the complete compatible set.
When a subset is requested, use `multiSelect` only if the exposed schema
supports it; otherwise offer compatible subsets. Wait for an actual submitted
answer. Empty, dismissed, and timeout results are not approval even when an
option is returned. In Claude Code 2.1.316, idle auto-resolution included the
host-only `afkTimeoutMs` field (observed 2026-11-01); do not treat it as a
human submission.

The adapter's catch-all PreToolUse hook checks calls it receives after a
report. It permits known safe reads and bounded read-only shell forms, and
denies other covered calls until human input. Transcript writes are
asynchronous, so a same-turn continuation can escape detection. The hook
recognizes an input boundary, not the meaning of approval; the assistant still
checks the current decision and scope. Internal hook errors warn and fail open.
The instruction to wait applies even when the hook does not enforce it.
