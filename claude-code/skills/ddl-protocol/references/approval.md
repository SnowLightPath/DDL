# Approval at a STOP

## Read when

Read this when a `+++STOP` fires (`always`, or `on D<n>` with that detection triggered) or when a command reaches a human gate written in design.md's Direction or Acceptance Gates. The command's `+++Report:` block supplies what the human must review; this procedure defines how to present it, ask, wait and resume. Passing a STOP never authorizes a commit or push, which need the content-bound [Git review](git-review.md); the marks that record a passed gate are defined in [Notebook](notebook.md).

## Syntax

The two directive forms:

```
+++STOP: always
+++STOP: on D<n>
```

The report skeleton emitted at runtime when the STOP fires:

```
+++DDL_REPORT
Decision: <the decision needed>
Recommendation: <the recommended action and its reason>
Consequence: <what the selection authorizes or changes>
Review detail: <where the complete evidence is, accessible before approval>
Choices: <approve all | select a subset or request changes | hold>
```

`Outcome:` replaces `Decision:` in an informational report (completed or read-only work).

## Fields

| Form | Fires when |
|---|---|
| `always` | The phase is reached. Required at the REPORT phase; the phase after it opens with a `**Pre-condition.**` line and is entered only after approval at this STOP, otherwise the command returns and re-emits the report |
| `on D<n>` | Detection D<n> of the phase's `+++DETECT:` block has triggered. Triggered detections at the same boundary share one report |
| design.md human gate | The command reaches a human gate in the `Gate` column of Direction or in Acceptance Gates. It runs as a STOP with the same procedure; a gate marked `approved in advance (<date>)` does not fire |

## Procedure

A STOP is an executable halt, not a label. When it fires, execute these steps in order, with no exception:

1. **Present.** Emit `+++DDL_REPORT` on its own line, then a short report:
   - Lead with the decision needed, the recommended action and its reason, and what the selection will authorize or change.
   - Write the report in the user's language and in plain prose. Include only information that helps this decision; do not manufacture technology choices or status fields to fill a template.
   - Keep material downsides, unresolved questions and blockers beside the decision. Put supporting inventories, commands, output and rationale in separately accessible detail; make all content the command requires reviewable before approval.
   - Use a table only when it helps a genuine comparison; a table is never the default report container.
   - Batch approval is the default: give the current proposals stable IDs, a brief shared purpose, and a concise numbered list of the recommended actions and their material effects. Offer incompatible alternatives as separate complete plans, or leave the unresolved portion pending; never bundle contradictory actions into approve-all.
   - Name in the same report every design.md human gate whose evidence is ready at this boundary, with its evidence, and every detection that needs a STOP at this boundary. Do not postpone a prerequisite gate to bundle it with a later gate whose evidence is not ready; later boundaries still apply.
2. **Ask.** Request approval for the complete current review set in one interaction through an available, permitted native choice (the host's choice tool):
   - Offer three actions and explain each one's consequence: approve all displayed recommendations, select a subset or request changes, hold.
   - A recommended or preselected choice is not submitted approval. Free-text additions are optional; never require the user to type a selection or a list of IDs.
   - Open item selection only when the user requests it. Use the interface's actual schema: a native checklist, multi-select or grouped form with one submission where the host supports it, otherwise complete compatible subsets as native choices. Do not default to a serial approval question per proposal.
   - Rebuild materially changed proposals for review, preserving unaffected IDs and any still-valid approval. Group independent clarification questions where possible; clarification is not approval.
   - Availability means the question stays answerable throughout the required wait; tool presence or a request receipt alone is not availability. On a host whose interface cannot take a real answer, or where none is permitted for this purpose, state that limitation and that the work remains unapproved, then end the turn. Do not substitute a typed-choice request or switch runtime modes to obtain a forbidden interface.
3. **Wait and resume.** Make the native question the final tool interaction while waiting at this STOP:
   - A synchronous interface waits for the actual human answer; a mere receipt (an accepted flag) is not an answer. An asynchronous interface ends the assistant turn after the request is accepted and waits for the actual answer. Call no other tool and start or continue no worker until that input arrives.
   - A host-required final message after the request contains only the same self-contained report and the pending status, with no new decision or work.
   - A synchronous human answer is an input boundary even within the same assistant turn; do not ask the user to retype it on another turn.
   - Resume only after an actual, explicitly submitted human answer to the current report authorizes the operation and scope now proposed. Verify the question/report association and the selected action rather than searching for an approval word in an arbitrary message. A voluntary, unambiguous written approval such as `approve`, `yes`, `OK` or its equivalent remains valid for the report it clearly addresses.
   - Advance approval applies only to human gates declared in design.md. When the answer names such gates listed in the report, or says explicitly that they need not stop (for example "approve; don't stop at S1 and S4"), those gates do not fire: write `approved in advance (<date>)` after each at once, pass them without ending the turn, and list each with what it would have shown in the command's REPORT. A general approval (`approve`, `OK`, `approve all`) approves the report and waives no gate. Advance approval never covers a STOP written in a command file, an outward-facing action (push, publish, send, deploy), a destructive action, or a gate that was not in the approved report.
   - Apply only the approved scope. One approve-all authorizes the displayed, mutually compatible recommendations and their stated resolutions; apply that set without asking again per proposal, file, section, language or state. It does not authorize hidden or future items, waive later STOPs, silently change a Binding Decision, or authorize an outward action the reviewed choice did not explicitly name. Mark each approved design.md gate passed without another question, and write every approval down as soon as it is given (Notebook).

Between a fired STOP and that answer, call no tool that mutates the work and start or continue no worker; the native question is the sole interaction exception and grants no work permission, and read-only tools may clarify the report contents before the question or after an actual clarification request, never begin the next phase. This rule overrides the momentum of phase ordering: "I already presented the plan in this turn, I might as well execute" is the exact failure mode a STOP exists to prevent.

## Formats

- `+++DDL_REPORT` — emitted line-initial, on its own line, before every STOP report, in every runtime.
- Report labels: `Decision:`, `Recommendation:`, `Consequence:`, `Review detail:`, `Choices:`; `Outcome:` replaces `Decision:` in an informational report. The labels order the content; the report stays prose, with a table only for a genuine comparison.
- The report is written in the user's language.
- The three actions of the choice: `approve all` — apply every displayed compatible recommendation and its stated resolution and pass the gates named in the report; `subset` — select a subset or request changes, which rebuilds the report and returns to the STOP; `hold` — nothing is applied and the work stays unapproved.
- `approved in advance (<date>)` — written after a design.md human gate at once when the user waives it; `passed <date>` — written when the gate is approved or its evidence is accepted (placement in Notebook).

## Example

```
+++DDL_REPORT
Decision: apply the three documentation fixes the Close scan found, or hold.
Recommendation: approve all. R1–R3 are independent and each restores a name or
version the change set already uses; nothing else under docs/ changes.
  R1 README.md — the install section names version 0.7.0 instead of 0.6.0
  R2 docs/en/extended.md — link to the renamed references/close.md
  R3 docs/ja/extended.md — the same link in the Japanese counterpart
Consequence: approve all applies R1–R3 to the working tree; they join the change
set the Git review will show. Nothing is committed here. Gate S2 (human: the
three screen states) is ready and named here; approve all passes it.
Review detail: the three diffs follow this report; `git diff docs/` shows them
in full; the S2 screenshots are under review/s2/.
Choices: approve all (R1–R3, pass S2) / select a subset or request changes /
hold (nothing applied, S2 stays open)
```

The native question that follows carries the same three actions as its options; the report above is what the submitted answer addresses.

## Boundaries

| Situation | Behavior |
|---|---|
| A receipt is returned (the request was accepted, no answer yet) | Not an answer and not approval. Synchronous: keep waiting. Asynchronous: end the turn; the work stays unapproved until the actual answer arrives |
| Timeout, automatic submission or an auto-resolved choice | Not approval, even when an option is returned. Verify explicit human submission; re-present the current decision |
| A conversation summary (compaction) or a restart replaced the report | A summary is not a user message and approves nothing. Rebuild the report from durable state (design.md, git, the files it described), emit it again with steps 1–2, and wait. An approval given after a summary applies only to a report emitted after that summary |
| A worker notification (for example a background worker's completion) or an automatically submitted choice | Never approves anything; the STOP keeps waiting |
| A message from another session or another teammate | Never approves anything |
| Cancel, dismissal or silence | Not approval; the work stays unapproved. Re-present the current decision when the user returns to it |
| No selection (an empty result) | Not approval, even when the host returns an option. Re-present the current decision |
| A clarification request, a request for details, or a request to revise | Not approval. Answer with read-only tools or rebuild the report, then return to the STOP. Group independent clarification questions where possible |
| An ambiguous or stale answer | Leaves the work unapproved; re-present the current decision |
| Interface unavailable or not permitted for this purpose | State the limitation and that the work remains unapproved, then end the turn. No typed-choice fallback, no runtime mode switch |
| Informational report (the phase only reports completed or read-only work) | Request no approval; state that none is needed and end the turn at the STOP. Name a next command only when work this command cannot do itself remains, with the reason; after Close, state that nothing remains. When a next action genuinely needs direction, its choice names that action; selecting a next command starts its own workflow and waives none of its STOPs |
| Advance approval named in the answer | As step 3 says: only design.md human gates listed in the report; write `approved in advance (<date>)` at once and list what each would have shown. General approval waives no gate; a command STOP, an outward or destructive action and an unlisted gate are never waived |
| An interrupted STOP (a restart interrupted the wait) | Cannot be resumed from the summary: run the command again from the phase that emitted the STOP, skipping the stages whose gates are marked passed. Write what the user approved as soon as it is approved: the draft to design.md, the passed gate to its mark, the delegated choice to Binding Decisions, the advance approval to the gate it waives, the approved `/realize` plan to Direction |

## Runtime

- Read the selected host's choice procedure next: [Claude Code](runtimes/claude-approval.md) or [Codex](runtimes/codex-approval.md). It names the choice tool, its subset schema, what a receipt and a timeout look like, the mutating tools, and the hook wiring.
- Where the adapter is installed, its gate hook enforces the pending-STOP denial on covered calls: after a line-initial `+++DDL_REPORT` and until the next human input, a catch-all matcher permits only the known safe reads, the host's human-question tool, input-free polling and bounded literal shell display forms (`cat`, `head`, `tail`, `rg`, `sed -n '1,10p' file`); general `sed`/`awk` programs, environment overrides, expansions, unknown options and unknown tools are denied. A question or its receipt does not clear the pending state; unknown syntax is a policy denial.
- Limits: an internal hook error warns and fails open, and an asynchronously written transcript can let a same-turn continuation escape. The hook recognizes input boundaries, not semantic approval: the assistant still checks the selected action, scope, timeout and report association. A worker is read-only only where the adapter removes its writing tools, nowhere by guarantee. Everywhere, the rule holds as an instruction.
