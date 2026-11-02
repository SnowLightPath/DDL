# Codex: approval

## Read when

Read this before presenting a decision STOP or a design.md human gate, together with the shared [approval procedure](../approval.md). It names the Codex choice tool, the mutating tools, and what the gate hook checks.

## Mapping

| Concern | Procedure |
|---|---|
| Choice tool | Prioritize the GUI; the known CLI limits stay prominent in the Codex README notice. Use a tool whose actual contract permits the decision: `request_user_input_async` in hosts that expose it for approval, with one whole-set question (schema `questions`, `title`, `options`; approve all, subset or changes, hold). `request_user_input` is Plan-only in some hosts and disallowed for permission requests in Default; do not use it outside its declared purpose. Never switch modes to obtain a question. |
| Subset | Use only the exposed capabilities: the async schema has no multi-select field, so offer compatible subsets as choices, or a grouped form when a permitted interface supports it. Do not invent a `multiSelect` parameter and do not default to per-item approval turns. |
| Receipt | `accepted: true` from the async call is a receipt, not an answer. End the turn after the receipt and wait for the actual reply to this question; agent results and request acknowledgments are not approvals. |
| Timeout | A host that clears the pending question at turn completion is not approval-capable for this decision: explain the limitation, state that the work remains unapproved and stop, without a typed fallback. |
| Mutating tools | While a STOP is pending, do not call `apply_patch`, shell commands that write, starting, messaging or resuming any agent, or any MCP tool that creates, updates, sends, publishes or deletes. |
| Human input boundary | The configured `UserPromptSubmit` clears the pending marker; a question invocation or its receipt does not. The reply arrives as a `UserMessage` and the hook recognizes that boundary; whether the reply approves the current report and scope stays the assistant's judgment (Resume rule). |
| Hook | `.codex/hooks/ddl_gate.py`, wired in `.codex/hooks.json`: PreToolUse with `matcher: "*"` (`pre-tool-use --runtime codex`), Stop (records a line-initial `+++DDL_REPORT`, because `transcript_path` may be null), UserPromptSubmit (clears), SessionStart on startup, resume, compact, fork and clear (re-states a pending report); each `timeout: 10`. While pending it permits `view_image`, `list_agents`, `request_user_input`, `request_user_input_async`, input-free polling (`wait`, `wait_agent`, `write_stdin` with empty `chars` and no `terminate`), and bounded literal shell reads through `shell`, `exec_command`, `local_shell`, `shell_command` or `Bash` (`cat`, `head`, `tail`, `rg`, `grep`, `sed -n '1,10p' file`, Git reads such as `git status --short`); unknown tools, code wrappers and starting, messaging or resuming workers are denied. State files: `$TMPDIR/ddl-gate` (overridden by `DDL_GATE_STATE_DIR`) holding `<session>.pending`, `<session>.warned` and `<session>.git-epoch`. |

## Observed

| Fact | Version | Date |
|---|---|---|
| In `codex exec` the same-turn `apply_patch` and `echo hi > file` were denied with the reason shown to the model, `git status --short` passed, and `transcript_path` was set | codex-cli 0.163.0 | 2026-10-18 |
| In Default mode the async question, its receipt and the selector were real, but the selector was cleared at turn completion before a reply could be delivered | Codex CLI 0.166.0 | 2026-11-01 |
| The GUI host of the same chat delivered actual click replies after turn completion; the reply's `send_user_message_question_reply` envelope carried the question ID, the question and the answer, and the rollout recorded a `UserMessage` boundary the gate already recognizes | Codex GUI host (app version not recorded) | 2026-11-01 |
| The hook configuration documentation at `https://learn.chatgpt.com/docs/config-file/config-advanced#hooks` was checked against `.codex/hooks.json` | Codex docs (config-advanced) | 2026-11-01 |

## Coverage

- The hook classifies only the tool calls Codex dispatches through the tool hooks; running processes, hook-bypassing transports and hosted operations are outside it. Shell checks accept literal arguments and explicit display or search option profiles; general `sed` or `awk` programs, environment overrides, expansions, unknown options and execution helpers are denied while pending. Unknown syntax is a policy denial.
- The Stop and UserPromptSubmit markers replace a null or unreadable transcript; a same-turn continuation can still escape when the record is asynchronous. Unexpected internal errors warn and fail open. The guard is not a sandbox and inspects no arbitrary programs or aliases.
- Project-local hooks run only under project trust; user-level hooks run independently of it; a host may ask to review new or changed hooks in `/hooks`. Where neither is active, the rule to wait holds as an instruction.
- The hook recognizes an input boundary, not the meaning of an answer. The CLI route that clears the selector is not approval-capable; the 2026-11-01 GUI result is one host on one day and does not generalize. Hook regressions are checked by isolated simulated dispatch, which proves neither the live question UI nor hook trust.
