# Parallel work

Read this when a `+++SWARM` condition selects two or more independent units,
before assigning them. If workers will run, read the selected host's
instructions: [Claude Code](runtimes/claude-parallel.md) or
[Codex](runtimes/codex-parallel.md).

## Select units

The directive supplies a condition and an operand block: `team`, `spawn`,
`type`, `max`, `batch`, `each`, and `collect`. Units may be scopes, selected
paths, Direction lanes, document pairs, or approved changes. A scope or path
argument limits the units to those selected. `team`, `spawn`, and `each` are
required; `type` defaults to `general-purpose`, `batch` to `auto`, and
`collect` to synthesis by the lead.

- Zero units: skip. One unit or a false condition: work inline.
- Two or more independent units: use the host's parallel primitive when it is
  available. Do not replace it with inline work. If none exists, work
  sequentially under the same reporting contract.
- `max` defaults to 5. With more units than `max`, `batch: auto` groups related
  units into at most `max` assignments; `batch: none` queues overflow.
- The lead handles interdependent changes together and names the dependency in
  the report. Do not assign conflicting edits to different workers.

## Assign and collect

1. Create a team only if the host has that primitive. Scale the assignments as
   above and resolve `spawn`, `each`, and the unit names.
2. Give each worker a self-contained prompt: relevant paths, Experience,
   principles, Binding Decisions, Direction, validation, and the approved
   rows verbatim when applying changes. Include the approved plan for realize.
   Name only the notebook sections the worker must read. Never assume it has
   inherited the lead's conversation.
3. `Explore` is read-only: no file edits or workers of its own; only task-named
   validation may create caches or build output inside its scope.
   `general-purpose` may write. Only the lead fans out; every worker reports
   its result to the lead. The adapter may enforce part of this contract, but
   the prompt states it in every host.
4. Wait for completion. With queued work, start the next assignment when a
   worker finishes. If a worker encounters a STOP, start no further queued
   work, collect running workers, and have the lead execute the STOP.
5. Integrate results as `collect` specifies. A failed launch, empty response,
   or missing result is not completed work. If no available worker can run an
   assignment, carry it out in the lead under the same scope and report the
   host limitation, or report it as not run. Never infer success from an
   attempted spawn or wait. Release any team resources.

The command's `each` and `collect` fields state the actual work and result;
this procedure does not authorize work beyond an approved scope.
