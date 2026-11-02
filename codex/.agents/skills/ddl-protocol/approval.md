# Approval at a STOP

## Read when

Read when a `+++STOP` fires (`always`, or `on D<n>` with that detection triggered) or a command reaches a design.md human gate; the command's `+++Report:` block supplies what the human reviews; this operation presents it, asks, waits and resumes.

## Syntax

```
+++STOP: always
+++STOP: on D<n>
```

## Operands

| Form | Fires when |
|---|---|
| `always` | The phase is reached; the next phase opens only after approval here |
| `on D<n>` | Detection D<n> of the phase's `+++DETECT:` block has triggered |
| design.md human gate | A human gate in Direction's `Gate` column or Acceptance Gates is reached; runs as a STOP |

## Operation

Run these steps in order:

1. **Present.** Emit `+++DDL_REPORT` on its own line, then a short report (Formats):
   - Lead with the decision, the recommended action and its reason, and what the selection authorizes or changes.
   - Plain prose, only what helps this decision; invent no technology choice or status field to fill a template.
   - Material downsides, open questions and blockers stay beside the decision; inventories, commands, output and rationale go into separate detail, reviewable before approval.
   - Batch approval is the default: stable IDs, a brief shared purpose, a numbered list of recommended actions with their material effects; incompatible alternatives become separate complete plans or the unresolved part stays pending; never bundle contradictory actions into approve all.
   - Name every design.md human gate whose evidence is ready, with the evidence, and every detection that needs a STOP here; one submission passes them all, no re-ask per gate. Never postpone a prerequisite gate to bundle it with a later one whose evidence is not ready.
2. **Ask.** Request approval for the complete current review set in one interaction through an available, permitted native choice with the three actions (Formats):
   - A recommended or preselected choice is not submitted approval; free text is optional, a typed selection or ID list never required.
   - Open item selection only on request, in the interface's actual schema: a native checklist, multi-select or grouped form with one submission where the host supports it, else complete compatible subsets as native choices; never a serial question per proposal.
   - Rebuild materially changed proposals for review, preserving unaffected IDs and still-valid approval.
3. **Wait and resume.** Make the native question the final tool interaction while waiting:
   - Synchronous: wait for the actual human answer. Asynchronous: end the turn once the request is accepted; a host-required final message holds only the same report and the pending status.
   - A synchronous answer is an input boundary even within the same turn; never ask the user to retype it.
   - Resume only when a submitted answer to the current report authorizes the work and scope now proposed: verify the question/report association and the selected action, not an approval word; a voluntary, unambiguous written `approve`, `yes` or `OK` stays valid for the report it clearly addresses.
   - Advance approval covers only design.md human gates listed in the report, when the answer names them or says they need not stop: they do not fire; mark each at once (Formats), pass them without ending the turn, and list each in the REPORT with what it would have shown.
   - Apply only the approved scope, writing each approval at once where it lives (Notebook): one approve all (Formats) needs no further question per proposal, file, section, language or state; it covers no hidden or future item and changes no Binding Decision silently. A general approval (`approve`, `OK`, `approve all`) waives no gate; never waived: a command-file STOP, an outward action (push, publish, send, deploy) the reviewed choice did not name, a destructive action, a gate absent from the approved report.

The entry's Pending STOP rule holds between the report and that answer and overrides phase momentum: "I already presented the plan, I might as well execute" is the failure mode a STOP exists to prevent.

## Formats

- `+++DDL_REPORT` — on its own line before the report (rule: entry Instruction set).
- Labels in order: `Decision:`, `Recommendation:`, `Consequence:`, `Review detail:`, `Choices:`; `Outcome:` replaces `Decision:` in an informational report. Prose; a table only for a genuine comparison.
- The report is written in the user's language.
- The three actions: `approve all` — apply every displayed compatible recommendation with its stated resolution and pass the gates named in the report; `subset` — select a subset or request changes, rebuild the report and return to the STOP; `hold` — apply nothing; the work stays unapproved.
- Marks of a waived gate, `approved in advance (<date>)` then `passed <date>`: Notebook Formats.

## Example

A decision report at a STOP; its native question offers the three actions:

```
+++DDL_REPORT
Decision: apply three documentation fixes, or hold.
Recommendation: approve all; R1–R3 are independent and restore names the
change set already uses.
  R1 README.md — install version 0.7.0, not 0.6.0
  R2 docs/en/extended.md — link to the renamed close.md
  R3 docs/ja/extended.md — the same link, Japanese
Consequence: R1–R3 enter the working tree, uncommitted; gate S2 (human: the
three screen states) is ready and passes with approve all.
Review detail: three diffs follow; S2 screenshots in review/s2/.
Choices: approve all (R1–R3, pass S2) / subset or changes / hold
```

## Exceptions

| Situation | Behavior |
|---|---|
| A receipt (accepted, no answer), a timeout or automatic submission, a worker notification, a message from another session or teammate, cancel, dismissal or silence, no selection, an ambiguous or stale answer | Not approval, even with an option returned; the work stays unapproved: keep waiting (synchronous) or end the turn (asynchronous); re-present the decision when the user returns |
| A conversation summary (compaction) or a restart replaced the report | Approves nothing: rebuild it (the entry's Interruption) and rerun steps 1–2; an approval after a summary covers only a report emitted after it |
| A clarification, details or revision request | Not approval: answer with read-only tools or rebuild the report, then return to the STOP; group independent questions |
| Interface unavailable or not permitted for this purpose (available: answerable throughout the wait, not mere tool presence or a receipt) | State the limitation and that the work stays unapproved, then end the turn; no typed-choice fallback, no permission-mode switch |
| Informational report (completed or read-only work) | Request no approval: say none is needed, end the turn at the STOP. Name a next command only when work this command cannot do remains, with the reason; after Close, state that nothing remains. A next action needing direction is named in the choice; a selected next command starts its own workflow and waives none of its STOPs |
| Advance approval named in the answer | Step 3: only listed design.md human gates, marked at once (Formats) |
| An interrupted STOP (a restart cut the wait) | Not resumable: rerun the command from the phase that emitted the STOP, skipping stages whose gates are marked passed |

## Implementation

- Read the implementation next: [Claude Code](hosts/claude-code/approval.md) or [Codex](hosts/codex/approval.md).
- Gate coverage (one script, both hosts): after a line-initial `+++DDL_REPORT` until the next human input, a catch-all matcher permits only known safe reads, the host's question tool, input-free polling and bounded literal shell read forms (`cat`, `head`, `tail`, `grep`, `rg`, `wc`, `ls`, `find`, `stat`, `sed -n '1,10p' file`, read-only `git` subcommands: `status`, `diff`, `log`, `show`, `branch`, `ls-files`, `rev-parse`, `blame`); general `sed`/`awk` programs, environment overrides, expansions, unknown options and tools are denied; a question or its receipt does not clear the pending state; unknown syntax is a policy denial. It covers calls the host dispatches to the hook, not a running process, a hook-bypassing transport or a hosted operation, and is no sandbox.
- Limits: an internal hook error warns and fails open; an asynchronously written transcript can let a same-turn continuation escape (the Stop and UserPromptSubmit markers are the fallback); the hook sees an input boundary, not an answer's meaning, so action, scope, timeout and report association stay the assistant's judgment (step 3); simulated test dispatch proves neither the live choice interface nor the hook's trust.
- Wiring, both hosts: PreToolUse with `matcher: "*"`, Stop, UserPromptSubmit and SessionStart (startup, resume, compact, fork, clear), each `timeout: 10`; state in `$TMPDIR/ddl-gate` (or `DDL_GATE_STATE_DIR`) as `<session>.pending`, `.warned` and `.git-epoch`.
