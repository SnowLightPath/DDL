# Close

## Read when

Read this on entry to the Close stage of `/realize` (its CLOSE phase) and before the Close scan of `/commit`. The command supplies the change set, the approved plan or the `remote` argument, and the detections that stop on a Binding Drift or a failed validation. Close brings the implementation, design.md and the documentation into one reviewed change set; its decisions follow [Approval](approval.md), its last step is the [Git review](git-review.md), and the sections it writes are defined in [Notebook](notebook.md).

## Syntax

The Close stage is the last row of Direction:

```
| Close | reflect, docs, resonate, validate, Git review of the whole change set | <the final diff with a summary of the design.md and documentation changes> | Git review |
```

Work ends in Close, not in a chain of follow-up commands: `/draft` writes this row last; when a Direction lacks it, `/realize` adds it to the plan and records it in `Approved plan (<date>)`; a project without Direction treats the work as one stage followed by Close.

## Fields

| Command | Authority for steps 1–3 | Git review |
|---|---|---|
| `/realize` | The approved plan's Close stage authorizes writing steps 1–3 to the working tree, in the same way the plan authorizes the implementation | The user sees and approves the result at the Git review; a hold or revision leaves everything uncommitted, with the edits in the working tree for revision |
| `/commit` | No plan: the findings of steps 1–3 form one batch review (Approval) before they are applied; when the scan finds nothing, report that in one progress line without `+++DDL_REPORT` and continue | That batch approval is not the Git approval; the Git review follows with the whole change set |

design.md is written only by `/draft` (the approved draft), `/realize` (`Approved plan` lines and passed marks) and the Reflect step of this stage; no command patches it elsewhere.

## Procedure

Run Close after the last implementation stage's gates are marked passed, in this order:

1. **Reflect:** Compare the code with design.md the way `/reflect` does in its COMPARE phase. Add the Experience the code revealed; check every Binding Decision; replace the Direction stages whose gates are all marked passed with their outcome and delete the `Approved plan` lines that served them; retire Acceptance Gates whose gates are all marked passed after moving the mechanical gates that should keep running into Validation; correct the Scopes and Validation entries that no longer match the repository. Write design.md as it will read after the commit. A Binding Drift stops here (the running command's Binding detection); only the user resolves it.
2. **Docs:** Audit the documentation the change set touches the way `/docs` does (stale versions, broken references, missing sections, stale examples, wrong names) and fix it.
3. **Resonate:** For every changed document that has a language counterpart, align the pair the way `/resonate` does, including dated Changelog rows where the project keeps them.
4. **Validate:** Run the Validation block and the mechanical gates of Acceptance Gates after the Close edits; a failure stops (the running command's validation detection), and after the fix run them again.
5. **Git review:** Read [Git review](git-review.md). Stage the whole change set (implementation, design.md, documents). Prepare the review for the commit, and for the push only when the plan or the command argument names `remote`, with the commit before its push. Show its report with a summary of the design.md and documentation changes and the link to the full diff. One native submission records, and when named sends, the set in one commit; no command chain follows it.

## Formats

- The final report after the commit ends with `nothing remains`, or names each item left as `left: <item> — <reason>` (for example a Binding Drift awaiting the user's choice). It suggests no next command.
- The progress line of a Close scan that found nothing (`/commit`): one line such as `Close scan: nothing to change`, in the user's language, without `+++DDL_REPORT`; the command continues to the Git review.
- The Direction Close row: Stage `Close`; Work `reflect, docs, resonate, validate, Git review of the whole change set`; Human sees the final diff with the summary of the design.md and documentation changes; Gate `Git review`. Its Gate cell takes `passed <date>` only after the actual Git approval.
- `remote` — the word in the approved plan or in the `/commit` argument that puts the push into the review; without it, no push.

## Example

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|---|---|---|---|
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval, passed 2026-10-21 |
| Close | reflect, docs, resonate, validate, Git review of the whole change set | final diff; summary of the design.md and documentation changes | Git review |
```

The final report of `/realize` after the commit:

```
+++DDL_REPORT
Outcome: recorded 4f2c9e1 on feature/search-states: the three screen states,
the S0–S1 outcomes in design.md, the README section "States" and its Japanese
counterpart. Nothing remains.
Recommendation: none after a Close.
Consequence: no further action; the branch holds the reviewed set, unpushed.
Review detail: src/states/* implemented; every Binding Decision honored, none
changed; S0 and S1 retired with their outcome and their Approved plan lines
deleted; `npm test` passed; S1 passed 2026-10-21 by human approval; the Close
changes are in the same commit; no detection fired.
```

## Boundaries

| Situation | Behavior |
|---|---|
| A Binding Drift is found in Reflect | Stop with the running command's Binding detection; only the user resolves it. Present the drift as a decision in the STOP report, never as a silent edit to the row |
| The Close scan finds no change (`/commit`) | One progress line without `+++DDL_REPORT`; continue to the Git review |
| Direction has no Close row | `/realize` adds the Close stage as the final stage of its plan and records it in `Approved plan (<date>)`; `/draft` always writes it as the last row |
| Hold or revision at the Git review | Nothing is recorded; the Close edits stay in the working tree for revision; the Close Git gate stays pending |
| The project has no Direction | Treat the work as one stage followed by Close |
| The user says "commit yourself" or asks to skip the review | The Git review still runs: a prior plan, a STOP release, a permission mode or an assistant assertion is not Git approval |
| The plan declares a human gate to review the Close changes first ("review first") | Run it through Approval when its evidence is ready and before preparing the Git review; it does not approve Git. Without such a gate, the normal path asks only at the Git review; a triggered detection STOP still applies |
| Compaction or a restart during Close | Reconstruct the stage, the passed marks and any pending report from design.md, git and the files; rebuild the Git review, because the preparation is invalidated; a summary or an old answer approves nothing |
| Validate fails | Stop (the validation detection); after the fix return to Validate, and run the commands again after every further Close edit |
| The plan or the argument names `remote` | The Git review covers the push with the commit; the commit precedes the push; one answer covers both. Without `remote`, no push |
| The change set is documentation only | Close runs unchanged: Reflect may find nothing; Docs and Resonate carry the work; Validate runs the Validation block; one Git review records it |
| The assistant cannot reconstruct the approved scope or the pending state after an interruption | Report the uncertainty and stop; do not claim a gate passed and do not retire any unfinished gate |
| What the Git review shows (the final candidate) | The notebook as it will read after the commit: after the other gates pass, its diff may retire Close's own row and plan. The Close Git gate stays pending until the actual approval; do not claim it passed |
| After the commit | State `nothing remains`, or name what was left with its reason; suggest no next command. Any command names a next command only when work it cannot do itself remains, with the reason; `/draft` still ends by naming `/realize`, because a draft is never an implementation |
| Where the human stops | At the plan approval, at the human gates written in design.md, and at the Git review; nowhere else. A plan may add a human gate to its Close stage. `/reflect`, `/docs` and `/resonate` remain available as standalone commands; Close fixes their order and approval inside `/realize` and `/commit` and does not replace them |

## Runtime

The Git review step uses the selected host's procedure: [Claude Code](runtimes/claude-git.md) or [Codex](runtimes/codex-git.md). Close itself is an instruction: no adapter enforces the order of steps 1–4 or the content of the Reflect edits. The gate hook enforces only the pending-STOP denial after `+++DDL_REPORT` and the content-bound check on the commit and push of step 5, within the limits those host files state.
