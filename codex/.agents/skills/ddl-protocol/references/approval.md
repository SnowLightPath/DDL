# Approval at a STOP

Read this before preparing a decision report or a human gate. Use the selected
host's choice procedure: [Claude Code](runtimes/claude-approval.md) or
[Codex](runtimes/codex-approval.md).

## Present and wait

1. Emit `+++DDL_REPORT`. State the decision, recommendation and reason, and
   what each choice authorizes. Keep material downsides and unknowns visible;
   make the command's full evidence accessible before the decision.
2. Give compatible recommendations stable IDs and offer one choice to approve
   the displayed set, request a subset or revision, or hold. Open item
   selection only on request. Do not require typed IDs or repeat approval per
   item, file, section, language, or state.
3. Use an available, permitted native choice interface. If none can receive a
   real answer, explain the limitation and stop; do not switch modes or invent
   a typed-choice fallback. A preselected option or receipt is not an answer.
4. Make the question the last tool interaction while waiting. For an
   asynchronous question, end the turn after its receipt; for a synchronous
   question, wait for the actual answer. A host-required final message may
   repeat the same report and pending status only.

An approve-all answer covers the displayed compatible recommendations and
their stated resolutions. It does not cover hidden work, later STOPs, an
implicit Binding Decision change, or an outward action not named in the
choice. Offer incompatible alternatives as separate complete plans. A request
for a subset, details, or revision is not approval to mutate.

## Resume

Proceed only when an actual submitted human answer authorizes the current
report and scope. A voluntary, unambiguous written approval is valid for the
report it clearly addresses; Git has a separate content-bound requirement.
Silence, cancellation, timeout, unrelated input, automatic submission, a
worker notification, or a message from another session is not approval. If the
answer is ambiguous or stale, present the current decision again.

After compaction or restart, if the report is no longer in context verbatim,
rebuild it from durable state, present it again, and wait. A summary is not an
answer. An approval after a summary applies only to a report presented after
that summary. An interrupted STOP cannot be resumed from the summary: rerun
its phase, skipping stages whose gates are already marked passed. Persist
approved drafts, plans, delegated choices, advance approvals, and passed gates
promptly in the notebook or their prescribed marks.

## Human gates

Execute a human gate in Direction or Acceptance Gates as a STOP. Combine gates
whose evidence is ready at the same boundary into one review and mark each
approved gate passed. Do not postpone a prerequisite gate to combine it with a
later one.

Advance approval applies only to notebook human gates listed in the report
that the user specifically names in their approval or explicitly says need
not stop. Record each waiver and report what it would have shown. General
approval waives no later gate. It cannot waive a command's STOP, a gate not in
the approved report, an outward action, or a destructive action.

A report that only communicates completed or read-only work requests no
approval. State that none is needed and end the turn.

The adapter checks only calls the host sends through its hook. Pending STOP
allows known safe reads and bounded literal display/search shell forms, not
general `sed`/`awk` programs, environment overrides, dynamic expansion, or
unknown tools. The hook is not a sandbox for arbitrary programs or ambient
configuration. It warns and fails open on internal error; the instruction to
wait still applies.
