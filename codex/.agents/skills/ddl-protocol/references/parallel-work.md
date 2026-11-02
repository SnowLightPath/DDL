# Parallel work

## Read when

Read this when a `+++SWARM` directive's condition is true for two or more units, before assigning work; the command supplies the condition and the operand block (`team`, `spawn`, `type`, `max`, `batch`, `each`, `collect`) that parameterize every step of the Procedure. When the host has a parallel primitive, running the assignments inline instead is not allowed. A worker that meets a STOP reports it and the lead executes it through [Approval](approval.md); the lanes of a Direction stage are units of this kind ([Notebook](notebook.md)).

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
    Task description per worker.
    {scope} resolves to the actual scope name at runtime.
    Report findings to the lead when done.
  collect: lead synthesizes all worker results
```
````

The condition is the text after `+++SWARM:` on the same line; the operands are the fenced block that follows it. `{scope}` resolves to the unit's name at runtime and becomes `{scopes}` when units are batched (Formats).

## Fields

| Field | Position | Required | Default | Meaning |
|---|---|---|---|---|
| `condition` | text after `+++SWARM:` on the same line | yes | none | Predicate evaluated against the scopes in design.md, or against the units the command names: the lanes of the current Direction stage, files, document pairs, and approved changes count like scopes. When the command was given a scope or path argument, only the units it selects count. When false, skip the SWARM and work inline |
| `team` | block body | yes | none | Fan-out name. Convention: `command-phase` (for example `reflect-read`, `realize-implement`). Used as the team name when the host has an explicit team primitive, otherwise as the label of the worker set |
| `spawn` | block body | yes | none | Worker label pattern. `{scope}` expands per matching unit. The label identifies the worker in reports; the host file says when it is also passed as the worker's name |
| `type` | block body | no | `general-purpose` | Worker role, `Explore` or `general-purpose`. `Explore` is read-only: it edits no files and starts no workers, and the only writes it may cause are the caches and build output of the commands its task names (for example the validation commands in `/validate`), inside its scope. `general-purpose` may write. The host file maps each role to the host's agent types and to the adapter's role definitions (`explorer`, `worker`) |
| `max` | block body | no | 5 | Maximum concurrent workers. Controls cost and resource use |
| `batch` | block body | no | `auto` | How to group units when their count exceeds `max`: `auto` groups them into batches, `none` queues the overflow (Boundaries) |
| `each` | block body | yes | none | Prompt template for each worker. `{scope}`, or `{scopes}` when batched, resolves at runtime. Must instruct the worker to report its results to the lead. Do not rely on a worker inheriting the lead's conversation (some hosts fork it, others start fresh): the resolved prompt is self-contained (Procedure step 3) |
| `collect` | block body | no | synthesize | How the lead integrates the results after all workers complete. Default: synthesize and present in the next phase |

## Procedure

Execute the steps in order. The selected host file names the tool for each step; when a tool it lists is missing, use the next option in the same cell or run the assignments sequentially. Never invent a tool.

1. **Create team:** When the host has an explicit team primitive, create a team named `{team}`. Otherwise record the unit assignment locally and continue.
2. **Scale:** Count the units that match the condition and evaluate the count against `max` and `batch`:
   ```
   scope_count = number of design.md scopes (or command units) matching condition

   if scope_count == 0:
       skip SWARM entirely
   elif scope_count == 1:
       execute inline, no fan-out
   elif scope_count <= max:
       1 worker per scope
   elif batch == "auto":
       lead groups related scopes by proximity/dependency
       into at most `max` batches (about ceil(scope_count / max) scopes each)
       {scope} in prompt becomes {scopes} (comma-separated list)
   elif batch == "none":
       first `max` scopes run in parallel
       remaining scopes are queued, claimed when a worker finishes
   ```
   Units whose changes depend on each other (for example commands that must share one new vocabulary) are not independent: handle them together in one assignment instead of splitting them across workers, and name the merged units and their dependency in the report. With `batch: none` and overflow, queue the remaining assignments (as tasks when the host has a task list).
3. **Spawn:** For each assignment, start one worker with the host's parallel primitive for the `type` role, labeled `{spawn}` with the unit resolved, in the background where the host allows. The prompt is `each` with `{scope}` or `{scopes}` resolved, plus what a worker without the lead's conversation cannot see:
   - the unit's paths from design.md;
   - the Experience items the unit serves;
   - the principles that apply;
   - the Binding Decisions for the unit;
   - the Direction stage it works on;
   - the unit's validation commands;
   - the rows the user approved for this phase, verbatim, in an apply or fix phase;
   - in `/realize`, the approved plan.
   The prompt names the files and the design.md sections the worker reads; the worker does not reload the guidance file or design.md in full, because the prompt is its context. The prompt states that the worker starts no workers of its own (only the lead fans out) and, for an `Explore` worker, that the work is read-only (Fields). If the host has no parallel primitive, the lead executes the assignments itself under the same reporting contract, one by one or with the parallel reads the host file allows.
4. **Monitor:** Wait for the workers through the host's completion signal; do not poll. With `batch: none`, start a queued assignment when a worker finishes. Once a worker reports a STOP condition, start no queued assignment: collect the running workers, then execute the STOP (step 5).
5. **Collect:** After all workers complete, integrate the results as `collect` instructs. Report a worker that failed, returned nothing, or has no result as such; never drop it silently, and never infer success from an attempted spawn or wait. A worker cannot end the user's turn: a worker that meets a STOP condition (a DETECT with `+++STOP: on D<n>`, or a human gate) stops its work and reports it, and after collecting, the lead executes that STOP ([Approval](approval.md)).
6. **Shutdown:** Release what step 1 created, if anything (team resources and open workers).

## Formats

- `{scope}`: in `spawn` and `each`, replaced by the unit's name at runtime (for the scope `api`, `reader-{scope}` resolves to `reader-api`).
- `{scopes}`: replaces `{scope}` in `each` when units are batched; a comma-separated list of the unit names in the batch.
- `team` convention: `command-phase`, the command name and the phase name joined by a hyphen (for example `realize-implement`).
- `spawn` label form: `role-{scope}`, a role word and the unit (for example `reader-{scope}` in a read phase, `writer-{scope}` in an apply phase).

## Example

A read phase of a command, as it appears in the command file:

````
### Phase 1: READ

+++SWARM: 2+ scopes in design.md

```
  team: reflect-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for current implementation state,
    including the technology it actually uses (manifests, lockfiles, config, entry points).
    Report findings to the lead when done.
  collect: lead also inspects design.md for internal consistency, then integrates all results
```
````

With three scopes the lead starts three `Explore` workers labeled `reader-<scope>`; with eight it forms at most five batches and `{scope}` becomes `{scopes}`.

## Boundaries

| Situation | Behavior |
|---|---|
| `0 units` match the condition | Skip the SWARM entirely |
| `1 unit` matches, or the condition is false | Work inline in the lead; no fan-out |
| Two or more units, `up to max` | One worker per unit (three units: three workers, one unit each) |
| More units than `max`, `batch: auto` | At most `max` batches, grouped by proximity or dependency, about ceil(count / max) units each; `{scope}` becomes `{scopes}` (eight units, `max` 5: up to five workers over at most five batches) |
| More units than `max`, `batch: none` | The first `max` units run in parallel; the rest are queued and claimed when a worker finishes (eight units, `max` 5: five workers start, three units queued) |
| Units are `dependent` on each other | Handle them in one assignment; name the merged units and the dependency in the report. Do not assign conflicting edits to different workers |
| A worker meets a `STOP` | It stops and reports; the lead starts no queued assignment, collects the running workers, and executes the STOP through [Approval](approval.md) |
| A worker `failed`, returned nothing, or was never launched | Report it as not done; never infer success from an attempted spawn or wait. When no available worker can run the assignment, carry it out in the lead under the same scope and report the host limitation, or report it as not run |
| The host has `no primitive` for parallel work | The lead executes the assignments itself under the same reporting contract, sequentially or with the parallel reads the host file allows. Inline work is not allowed when a primitive exists |
| The command was given a scope or path `argument` | Only the units it selects count toward the condition |

## Runtime

Read the selected host's instructions before step 1: [Claude Code](runtimes/claude-parallel.md) or [Codex](runtimes/codex-parallel.md). They name the team primitive, the parallel primitive, the mapping of `Explore` and `general-purpose` onto the host's agent types and the adapter's `explorer` and `worker` roles, the background and completion signals, the nesting limit, and the fallback. The Claude Code adapter may remove tools from a role (an `explorer` without write tools, a `worker` without spawning); the Codex adapter cannot narrow a subagent's permissions. In every host the prompt states the contract (read-only, no workers of its own, report to the lead), and this procedure remains an instruction where the adapter does not enforce it. The command's `each` and `collect` operands state the actual work; this procedure authorizes nothing beyond an approved scope.
