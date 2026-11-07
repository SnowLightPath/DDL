# Close

## Read when

Read on entry to the Close stage of `/realize` and before the Close scan of `/commit`; the command supplies the change set, the approved plan or the `remote` argument, and its Binding Drift and validation detections.

## Syntax

The last row of Direction (writer: Notebook):

```
| Close | reflect, docs, resonate, validate, Git review of the whole change set | <the final diff with a summary of the design.md and documentation changes> | Git review |
```

## Operands

| Command | Authority for steps 1–3 | Git review |
|---|---|---|
| `/realize` | The approved plan's Close stage authorizes steps 1–3 in the working tree, as it authorizes the implementation | The user sees and approves the result there (hold: Exceptions) |
| `/commit` | No plan: the findings of steps 1–3 form one batch review (Approval) before being applied (none: Exceptions) | That batch approval is not the Git approval; the Git review follows with the whole change set |

## Operation

Run Close after the last implementation stage's gates are marked passed, in this order:

1. **Reflect:** Compare the code with design.md as `/reflect` does in COMPARE: add the Experience the code revealed; check every Binding Decision; retire the Direction stages and Acceptance Gates whose gates are all passed, with their `Approved plan` lines (Notebook); correct Scopes and Validation entries that no longer match the repository. Write design.md as it will read after the commit. A Binding Drift stops here (the command's Binding detection) for the user to resolve.
2. **Docs:** Audit the documentation the change set touches as `/docs` does (stale versions, references, sections, examples, names) and fix it.
3. **Resonate:** Align every changed document with its language counterpart as `/resonate` does, dated Changelog rows included where the project keeps them.
4. **Validate:** Run the Validation block and the mechanical Acceptance Gates after the Close edits; a failure stops (the command's validation detection).
5. **Git review:** Stage the whole change set (implementation, design.md, documents); prepare the review for the commit and, only with `remote` (Formats), the push after it; show its report with a summary of the design.md and documentation changes; its question names the report file, which holds the full diff. One native submission records, and when named sends, the set in one commit; no command chain follows.

## Formats

- The final report after the commit ends with `nothing remains`, or names each item left as `left: <item> — <reason>`; it suggests no next command.
- The progress line of a Close scan that found nothing (`/commit`): `Close scan: nothing to change`, in the user's language, without `+++DDL_REPORT`.
- The Close row's Gate cell takes `passed <date>` only after the actual Git approval.
- `remote` — the word in the approved plan or the `/commit` argument that puts the push into the review; without it, no push.

## Example

The final report of `/realize` after the commit:

```
+++DDL_REPORT
Outcome: recorded 4f2c9e1 on feature/search-states: the three screen states,
the S0–S1 outcomes in design.md, the README section "States".
Consequence: none; the branch holds the reviewed set, unpushed.
Review detail: every Binding Decision honored; S0 and S1 retired with their
Approved plan lines; `npm test` passed; no detection fired. Nothing remains.
```

## Exceptions

| Situation | Behavior |
|---|---|
| A Binding Drift is found in Reflect | A decision in the STOP report, never a silent edit to the row |
| The Close scan finds no change (`/commit`) | The progress line (Formats); continue to the Git review |
| Direction has no Close row, or the project has no Direction | `/realize` adds Close last in its plan and records it in `Approved plan (<date>)`; without Direction the work is one stage, then Close |
| Hold or revision at the Git review (its candidate may already retire Close's own row and plan) | Git review Exceptions (hold, revision); the Close row's Gate cell stays unmarked (Formats) |
| "commit yourself" or a request to skip the review | The Git review still runs (Git review step 3) |
| A plan gate to see the Close changes first ("review first") | Run it through Approval when its evidence is ready, before preparing the Git review; it approves no Git. Without it the path asks only at the Git review; a detection STOP still applies |
| Compaction or a restart during Close | Reconstruct (the entry's Interruption); rebuild the invalid Git preparation |
| Validate fails | Step 4 stops; rerun after every further Close edit |
| The plan or the argument names `remote` | The commit precedes the push; one answer covers both |
| The change set is documentation only | Close runs unchanged: Reflect may find nothing, Docs and Resonate carry the work |
| The assistant cannot reconstruct the approved scope or the pending state | Report the uncertainty and stop; claim no gate passed, retire no unfinished gate |
| After the commit | The final report (Formats); `/draft` alone still ends by naming `/realize` |
| Where the human stops | Plan approval, the human gates in design.md, the Git review; nowhere else. `/reflect`, `/docs` and `/resonate` stay standalone; Close fixes their order and approval inside `/realize` and `/commit` |

## Implementation

Step 5 uses the Git review implementation: [{Host}](hosts/{host}/git-review.md). No adapter enforces steps 1–4 or the Reflect edits' content; the gate covers only the pending-STOP denial (Approval) and step 5's commit and push (Git review).
