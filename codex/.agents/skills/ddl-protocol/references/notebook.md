# The shared notebook

Read this before applying rules for notebook sections, decisions, plans, or
gates. The notebook is `design.md` unless project guidance names another
file. It records human agreement, not automatic memory or agent progress.
Projects use the sections they need; existing alternative headings may be
mapped once by reflect and need not be renamed.

| Section | Purpose and authority |
|---|---|
| Intent | Why the project exists; written by the human. |
| Scopes | Paths and units used by commands and parallel work. |
| Principles | Project principles; draft and reflect may propose changes. |
| Experience | Consumer inputs, outputs, and boundary states. Experience comes first. |
| Binding Decisions | Means fixed by the human, with a reason and source. |
| Direction | A non-binding outlook: stages, parallel lanes, what the human sees, and gates. |
| Acceptance Gates | Mechanical and human conditions for completion. |
| Validation | Continuing per-scope mechanical checks. |

The human owns Intent and Binding Decisions. Draft saves approved design;
realize records the approved plan, delegated choices and gate marks, and may
align equivalent check references included in that plan. Standalone reflect
applies approved updates; Close reflects within the approved realize plan or
the standalone commit batch. Other commands do not patch the notebook.

## Binding Decisions

Each row records the decision, why it binds, and its source: the human's dated
words or approval of a report containing it. The reason may be the Experience,
an external constraint, or a stated preference. Add a scope column when
different scopes bind different means. Record the granularity the human gave;
exact versions belong to manifests and lockfiles. For documents and slides,
the output format can be binding.

Only the human creates or changes a Binding Decision. Existing code and
automatic memory are premises, not binding decisions. A proposal, a named
technology without a reason, or a delegated choice remains `Unbound:` until
the human decides. State a delegated choice in the realize plan; on approval,
record it with the plan approval as its source. After approval, a conflicting
command argument is a proposed change, not permission to replace the decision.

## Direction and gates

Direction is an outlook, not a Binding Decision. Realize follows it by default
and reports merged, reordered, or skipped stages. Its lanes are parallel units;
its gate runs at the end of the stage. A merged stage keeps its gates; a
skipped stage's gates move to the next stage or the end of the work; reordered
stages keep their gates. Do not drop a gate.

Every Direction ends in Close. Draft writes the row; realize adds it to its
plan if it is absent. When the human approves the realize plan, promptly record
its durable files, approach, and delegated choices as `Approved plan (<date>)`
under Direction. A later session reconstructs work from that record, not a
conversation summary.

Mechanical gates are commands with expected results when an exit status alone
is insufficient. Execute human gates using [approval](approval.md). Realize
records `passed <date>` after each gate actually passes. Record a named advance
approval promptly as `approved in advance (<date>)`, then append the pass mark
when the stage or work ends. A general approval waives no future gate.

If the approved plan moves a validation target or reference, align Scopes and
Validation before running that stage's check. Preserve the check's purpose,
expected result's meaning, and coverage; show the old and new mapping in the change set.
This does not change Acceptance Gates, Binding Decisions, Experience, or human
gates. An actual check failure still stops the work.

Reflect compares the passed marks with the implementation. Retire each
Direction stage once all of that stage's gates pass; later stages may remain.
Retire Acceptance Gates only when every acceptance gate passes, first moving
continuing mechanical checks to Validation. Close performs the same comparison. If the
notebook is not version controlled, reflect quotes removed stages and gates in
its report; otherwise the history remains in git.
