# Claude Code: approval

## Read when

Read this before presenting a decision STOP or a design.md human gate, together with the shared [approval procedure](../approval.md). It names the Claude Code choice tool, the mutating tools, and what the gate hook checks.

## Mapping

| Concern | Procedure |
|---|---|
| Choice tool | Ask with `AskUserQuestion`: one question covering the complete compatible set, concrete action options (approve all, subset or changes, hold) and optional free text. Make it the final tool interaction and wait for the actual submitted answer. |
| Subset | When the user asks for a subset, use `multiSelect` only when the exposed schema supports it; otherwise offer compatible subsets as options. Do not ask one question per item. |
| Receipt | An empty result, a dismissal or an auto-resolved result is not approval even when an option is returned; verify explicit human submission. |
| Timeout | Idle auto-resolution returns a result that carries the host-only field `afkTimeoutMs`, with or without selected answers; the gate excludes such a result from human-input boundaries, and the assistant treats it as no answer. An ordinary submission omits that field. |
| Mutating tools | While a STOP is pending, do not call Edit, Write, NotebookEdit, non-read-only Bash, TaskCreate, TaskUpdate, start a worker (`Agent`), continue one with `SendMessage`, or any MCP or connector tool that creates, updates, sends, publishes or deletes. |
| Human input boundary | An answered `AskUserQuestion` and an approved plan count as the human speaking; background worker notifications and messages from teammates or other sessions never do. Whether the answer approves the current report and scope stays the assistant's judgment (Resume rule). A genuine synchronous answer resumes the approved scope; do not ask the user to retype it. |
| Hook | `.claude/hooks/ddl_gate.py`, wired in `.claude/settings.json`: PreToolUse with `matcher: "*"` (`pre-tool-use --runtime claude`), Stop (records a line-initial `+++DDL_REPORT`), UserPromptSubmit (clears the pending marker), SessionStart on startup, resume, compact, fork and clear (re-states a pending report); each `timeout: 10`. While pending it permits Read, Grep, Glob, LS, NotebookRead, WebFetch, WebSearch, ToolSearch, ListAgents, ReadNotifications, TaskGet, TaskList, `AskUserQuestion`, and bounded literal shell reads through Bash (`cat`, `head`, `tail`, `rg`, `grep`, `sed -n '1,10p' file`, Git reads such as `git status`); it denies every other call it receives. State files: `$TMPDIR/ddl-gate` (overridden by `DDL_GATE_STATE_DIR`) holding `<session>.pending`, `<session>.warned` (the unreadable-record warning once per session) and `<session>.git-epoch`. |

## Observed

| Fact | Version | Date |
|---|---|---|
| Against this repository's live transcript the gate denied a covered call after a report and allowed it after the plan approval, 0.04 s per call | Claude Code 2.1.302 | 2026-10-18 |
| Selecting an `AskUserQuestion` option and cancelling the question were confirmed as distinct results | Claude Code 2.1.312 | 2026-11-01 |
| Idle auto-resolution after the 60-second timeout returned the selected answers together with the host-only `afkTimeoutMs` field; an explicit submission under the same setting omitted it; the timer did not run while Remote Control was connected | Claude Code 2.1.316 | 2026-11-01 |
| With the native choice unavailable, Fable 5.1 at xhigh effort explained the limitation and left the work unapproved instead of using a typed fallback | Claude Code 2.1.316 | 2026-11-02 |

## Coverage

- The hook classifies only the tool calls Claude Code dispatches through PreToolUse; running processes, hook-bypassing transports and hosted operations are outside it. Shell checks accept literal arguments and explicit display or search option profiles; general `sed` or `awk` programs, environment overrides, expansions, unknown options and execution helpers are denied while pending. Unknown syntax is a policy denial.
- The transcript is written asynchronously, so a same-turn continuation can escape the gate; the Stop and UserPromptSubmit markers are the fallback for an unreadable transcript. Unexpected internal errors warn and fail open. The guard is not a sandbox: it inspects no arbitrary programs, aliases or ambient configuration.
- The hook recognizes an input boundary, not the meaning of an answer. Approval of the current report and scope, turn termination and the rule to wait are instructions, unchanged where the adapter is absent or not trusted.
- The Observed rows come from live transcripts; hook regressions are checked by isolated simulated dispatch, which proves neither the live choice UI nor hook trust in a new host.
