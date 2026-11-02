# Parallel work

## Read when

Read when a `+++SWARM` condition is true for two or more units, before assigning work; the command supplies the condition and the operand block, and inline work is not allowed when the host has a parallel primitive.

## Syntax

````
+++SWARM: 2+ scopes in design.md

```
  team: command-phase
  spawn: role-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Task per worker; {scope} resolves at runtime.
    Report findings to the lead when done.
  collect: lead synthesizes the results
```
````

## Operands

| Operand | Position | Required | Default | Meaning |
|---|---|---|---|---|
| `condition` | after `+++SWARM:` | yes | none | Predicate over the scopes in design.md or the units the command names (Direction lanes, files, document pairs, approved changes); a scope or path argument selects the units that count |
| `team` | block | yes | none | Fan-out name, `command-phase` (Formats): the team name where the host has a team primitive, else the worker set's label |
| `spawn` | block | yes | none | Worker label pattern, `role-{scope}` (Formats); identifies the worker in reports; the implementation says when it is also the worker's name |
| `type` | block | no | `general-purpose` | `Explore` is read-only: no edits, no workers, and only the caches and build output of the commands its task names, inside its scope; `general-purpose` may write |
| `max` | block | no | 5 | Maximum concurrent workers |
| `batch` | block | no | `auto` | When the units exceed `max`: `auto` batches them, `none` queues the overflow (step 2) |
| `each` | block | yes | none | Prompt template per worker, `{scope}` or `{scopes}` (Formats) resolved at runtime; contents and contract: step 3 |
| `collect` | block | no | synthesize | How the lead integrates the results (default: synthesize, present in the next phase) |

## Operation

Execute the steps in order; the implementation names each step's tool; when a listed tool is missing, use the next option in the same cell or run sequentially.

1. **Create team:** Where the host has a team primitive, create a team named `{team}`; otherwise record the unit assignment locally.
2. **Scale:** Count the units that match the condition:
   ```
   count = units matching the condition
   0            skip the SWARM
   1            inline in the lead, no fan-out
   ≤ max        one worker per unit
   > max, auto  at most `max` batches by proximity or dependency, about
                ceil(count / max) units each; {scope} becomes {scopes}
   > max, none  the first `max` units start; the rest queue (as tasks where
                the host has a task list) and are claimed as workers finish
   ```
   Units whose changes depend on each other go in one assignment; name the merged units and the dependency in the report.
3. **Spawn:** Per assignment, start one worker of the `type` role with the host's parallel primitive, labeled `{spawn}` resolved, in the background where the host allows. The prompt is `each` resolved plus what a worker without the lead's conversation cannot see: the unit's paths from design.md, the Experience items it serves, the principles that apply, its Binding Decisions, the Direction stage, its validation commands, the rows the user approved for this phase (verbatim, in an apply or fix phase) and, in `/realize`, the approved plan. It names the files and design.md sections the worker reads (no reload of the guidance file or design.md in full) and states the contract: the worker starts no workers of its own, reports its results to the lead and, for `Explore`, works read-only.
4. **Monitor:** Wait for the host's completion signal; do not poll. With `batch: none`, start a queued assignment when a worker finishes. Once a worker reports a STOP condition, start no queued assignment: collect the running workers, then step 5.
5. **Collect:** Integrate the results as `collect` instructs. A worker that failed, returned nothing or was never launched is not done; never infer success from an attempted spawn or wait. A worker never ends the user's turn or approves anything: one that meets a STOP condition stops and reports it, and the lead executes that STOP after collecting ([Approval](approval.md)).
6. **Shutdown:** Release what step 1 created (team, workers).

## Formats

- `{scope}`: in `spawn` and `each`, the unit's name at runtime (scope `api`: `reader-api`).
- `{scopes}`: replaces `{scope}` in `each` when units are batched: the batch's unit names, comma-separated.
- `team`: `command-phase`, command and phase names joined by a hyphen (`realize-implement`).
- `spawn`: `role-{scope}`, a role word and the unit (`reader-{scope}`, `writer-{scope}`).

## Example

The READ fan-out of `/realize`, resolved:

```
+++SWARM: 2+ scopes in design.md   → api, web, docs: 3 units, one worker each
  team: realize-read
  spawn: reader-api, reader-web, reader-docs
  type: Explore
  each: Read api (web, docs) for what this phase needs; report to the lead.
  collect: the lead merges the three findings before the plan STOP
```

## Exceptions

| Situation | Behavior |
|---|---|
| `0 units`; `1 unit` or a false condition; two or more `up to max`; more than `max` with `batch: auto` or `batch: none` | Step 2 decides each case |
| `dependent` units | One assignment (step 2); never give conflicting edits to different workers |
| A worker meets a `STOP` | Steps 4 and 5; no queued assignment starts |
| A worker `failed` or returned nothing | Not done (step 5); when no worker can run it, do it in the lead under the same scope and report the host limitation, or report it as not run |
| `no primitive` for parallel work | The lead runs the assignments itself under the same reporting contract, sequentially or with the parallel reads the implementation allows |
| A scope or path `argument` | Only the units it selects count (Operands `condition`) |

## Implementation

Read the implementation before step 1: [{Host}](hosts/{host}/parallel-work.md); it maps `type` onto the host's agent types and the adapter's `explorer` and `worker` roles. Read-only is enforced only where the adapter removes a worker's tools; where it cannot narrow a worker's permissions, the prompt contract alone holds. `each` and `collect` state the actual work; this operation authorizes nothing beyond an approved scope.
