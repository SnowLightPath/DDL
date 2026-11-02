# Close

Read this before the Close stage of realize or commit. It brings the design,
documentation, and implementation into one reviewed change set.

## Order

After the implementation stages and their gates pass:

1. **Reflect:** compare the implementation and notebook. Add Experience found
   in the work, check every Binding Decision, retire passed Direction stages
   and accepted gates, and correct stale Scopes and Validation. A Binding
   Drift stops for the human to resolve.
2. **Docs:** audit and fix the documentation touched by the change.
3. **Resonate:** align every changed document with its language counterparts.
4. **Validate:** run the notebook's Validation and applicable mechanical
   Acceptance Gates. A failure stops.
5. **Git review:** read [Git review](git-review.md), stage the complete change
   set, and prepare one final review. Include a push only if the approved plan
   or commit argument explicitly names it.

In realize, the approved plan authorizes the first three steps in the working
tree. In standalone commit, scan them first: if changes are needed, obtain one
batch approval before applying them; otherwise report that the scan found no
changes and proceed. That approval is not the final Git approval.

If the approved plan includes a human gate to review the Close changes first,
use [approval](approval.md) when its evidence is ready and before preparing the
Git review. That gate does not approve Git. Without such a gate, the normal
Close path asks only for the final Git review; any other triggered STOP still
applies.

The final candidate shows the notebook as it will read if the reviewed commit
is recorded: after other gates pass, its proposed diff may retire Close's own
row and plan. Close's Git gate remains pending until actual approval; do not
claim it passed or retire any other unfinished gate. On hold or revision, leave
the changes uncommitted. If the approved scope or pending state cannot be
reconstructed after an interruption, report the uncertainty and stop.

After recording, state that nothing remains or name the remaining work and its
reason. Do not suggest a chain of follow-up commands. Standalone reflect,
docs, and resonate remain available.
