# Codex: approval

Read this before presenting a decision STOP, together with the shared
[approval procedure](../approval.md).

Prioritize the GUI. Use `request_user_input_async` only when the actual host
contract permits this decision and keeps the question answerable after the
turn ends. Its `accepted: true` is a receipt, not an answer. End the turn and
wait for the user's reply. For a requested subset, use only the exposed schema;
the observed async schema has no multi-select field. Do not switch modes or
invent a parameter to obtain approval.

In Codex CLI 0.166.0 Default mode, the async selector was cleared at turn
completion before a reply could be delivered (observed 2026-11-01). That path
is not approval-capable: explain the limitation and stop. The desktop host
observed on that date retained replies; do not generalize to every host.

The adapter's catch-all hook checks covered calls, permits known safe reads,
and denies other calls while STOP is pending. A question or receipt does not
clear it. `UserPromptSubmit` marks an input boundary, not semantic approval;
the assistant must check the actual answer and scope. Internal hook errors warn
and fail open. The instruction to wait applies outside hook coverage too.
