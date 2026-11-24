# Design-Doc Loop (DDL)

## Intent

Human and LLM continue to share design principles across sessions, agents, and harnesses.

DDL collects desired designs in a flexible process. Its documents are temporary notes until the design is reflected in code.

For more background, examples, and guidelines, see the [extended guide](./design_philosophy_extended.md). Read only what you need, when you need it.

## Background: The Session Discontinuity Problem

Collaborative development with LLMs has a session discontinuity problem:

- What one agent remembers, the next session, agent, or harness does not see
- What the agent remembers is not what the human agreed to
- The more a session holds, the less of it the model recalls, so context is a budget, for the model as for us

So we share code design as memos with LLMs.

### In the Harness Era

Agent harnesses such as Claude Code and Codex now carry memory of their own: instruction files, automatic memory, summaries of long conversations. That memory helps the agent recall, but what the agent writes there is not a record the human has agreed to.

Parallel subagents usually start as new sessions, so the discontinuity grows with every worker. The shared memo tells each agent what the human has fixed and where the human wants to look before work begins.

The scarce resources are the human's attention and the context a session can hold. The shared memo keeps the design across sessions while giving each agent the context it needs.

The harness can also hold part of the loop. Where it offers hooks, agent definitions, and imports, DDL's adapters support STOPs, worker roles, and keeping the memo in context. Mechanical enforcement is limited to what the runtime exposes; the same rules apply as instructions where those mechanisms cannot enforce them.

## Core Principle

```
Human ←→ Document ←→ LLM
              ↓
            Code
```

Documents connect Human and LLM. Code is written based on them.

However, design issues may be discovered during implementation. When that happens, update the documents.

Ultimately, code becomes the source of truth. DDL documents get integrated into code or docs, and what they no longer need is deleted or moved to a history file. No need to be formal about it.

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

### Draft

**Intent:** Write the user-side experience first.

Write how the code will be used before implementing it. Verify the API is usable, then implement.

```python
# Draft: Write usage before implementation
async with Client(
    "https://api.example.com"
) as c:
    users = await c.get("/users")
```

Some decisions cannot be separated from the experience. A library's language is its usage; a streaming interface may depend on its framework; an organization may require a platform. Draft records these as **Binding Decisions**, with the reason each decision constrains implementation and its source.

For example, a streaming answer interface might have this decision:

> **Decision:** Next.js App Router.
>
> **Why it binds:** Answers stream in while they are written, and per-route loading and error states are the core of the experience.
>
> **Source:** "I want to build it with Next.js", "Yes, App Router" (2026-10-17).

The source is the human's words and date, or the human's approval of a report that listed the decision.

<details>
<summary>Copy this example into design.md</summary>

```markdown
## Binding Decisions
| Decision | Why it binds | Source |
|---|---|---|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |
```

</details>

When you already see the path to implementation, Draft records it as **Direction**: stages, parallel lanes, and the points where the human wants to look. Direction is an outlook, not a contract.

**Acceptance Gates** say what must hold when the work is done: commands that must pass, and approvals the human will give. They are retired once the work is accepted.

Only the human binds. The LLM may propose a technology; it stays unbound until the human chooses it.

Technology already present in the code is an existing premise: commands show it in their reports, and design.md does not record it. It becomes a Binding Decision only when the human gives a reason.

### Realize

**Intent:** Write code based on design principles.

Implement code following the documented principles and Binding Decisions. Follow Direction unless there is a reason not to, and say so when you deviate. Stop at the human gates.

### Reflect

**Intent:** Update documents based on implementation results.

If you learn something from implementation, update the documents. Check the code against Binding Decisions, and move finished Direction, with what actually happened, to the history file `design-history.md`, so that design.md keeps only the current design. In the tool-assisted loop, Reflect runs as the Close stage at the end of Realize, before the single commit that ends the work.

Sometimes your fingers fly across the keyboard so fast that code outpaces design. In the harness era, they are often the agent's fingers.

Realize and Reflect are roughly inverse functions.

## Roles: Human and LLM

In DDL, Human and LLM are equal partners.

|       | Human              | LLM                    |
|-------|--------------------|------------------------|
| Strengths | Initial intuition, long-term vision, patience | Technical knowledge, pattern recognition, articulation |
| Weaknesses | Comprehensiveness, implementation details | Short-term bias |

Human controls the pace and corrects LLM's short-term bias.

When agents run long and in parallel, the human's share becomes concrete: decide what binds, decide where to look, and approve at those gates. Agents work between the gates.

Human attention is a budget. The work waits longest on the human, and approval asked for again and again turns into a formality, so DDL removes questions by design rather than by asking the human to be careful. On the ordinary path, DDL asks the human when the design is decided (a draft, a change to a Binding Decision or a principle), when a plan is approved together with its grant, at the human gates design.md names, and before an exit such as a push, or a commit the grant does not cover; a detection, such as a failing check or a secret found in the change, also stops the work. Reversible local work inside the grant goes ahead without a question. A command called on its own, such as `/reflect` or `/docs`, makes a snapshot, applies its reversible changes and then reports them; it asks first about a change to a Binding Decision, a principle or a promised behavior. The final report of `/realize` carries count lines for the questions, the minutes the work waited for the human, the gate's denials and the grant, so questions and waiting are visible as numbers. The report also counts the questions by kind (plan, confirm, Git and other) and, for a Run, the commits and push reviews on a `Records` line.

A grant is the scope, budget and expiry that a `/realize` plan names for its work. The scope names the paths the work may edit, the classes of command it may run (build, test, check and the like), and the machines and services it may use with the kinds of data handed to them. The gate hook records the grant when the human submits the approving option of the plan's question. Until the expiry, the gate allows reads, edits of those paths and commands of those classes, so neither DDL nor the host asks about them, and it denies an edit, a command class or a machine outside the grant; widening a grant takes a revised plan. A grant does not end a STOP: only while a pending question names the items it holds does the other work inside the grant go on, and a question that names no items stops all the work. A grant never lets the work edit a protected file such as Git's files, an instruction file or the notebook, and never covers an exit such as a push. When the grant names the command class `commit`, a plain local commit whose staged files all lie inside the grant passes without a question, and the gate logs it in the ledger and counts it; a protected file can be included only when the grant names its path literally. Commits thus stay fine-grained while the approval comes once, at the push: the push stays the exit, and its one review lists every commit it sends. Inside a Run, the gate refuses a push until the plan's `close` item has its dependencies done.

Agents work on this machine; a remote machine only runs what it is handed. A grant names machines and services by the names of a resource table that each user keeps, whose format DDL defines, and the gate refuses a name the table does not declare or data a resource does not take. The handover gives a machine only the tracked files, or a named snapshot's files, without protected or secret-shaped ones, as one commit without history in a throwaway copy, and the gate brings back only the output lines, file hashes and exit status. No agent, key, conversation record or approval goes to a remote machine, and what comes back is data, never instructions. No grant covers a resource the table marks to confirm each run (for example a paid cluster or a cloud service): each run needs a confirmation the human gave for that exact command or prompt, and a confirmation is used once. Such a service, and any write to a service, goes only through the gate's `service`, which checks the confirmation; a plugin the agent calls directly is outside the gate, and there the rule binds as an instruction.

A question may name the Run's items it holds. While every pending question does, the gate lets only the in-grant edits, and the tests and checks that name their paths, go on outside those items and the items that depend on them. A question can also be queued without making a STOP pending, and the lead asks the queued questions together when the human is back or no unheld work is left. A provisional question lets the lead go ahead on the recommended option after a snapshot, though the recommendation itself is no approval. Until the answer comes, the gate denies the calls that leave this machine, and the lead undoes an overturned choice from the snapshot with the gate's `restore`. The final report of a Run lists the questions it still waits on, marked provisional, waiting or exit.

When a decision is needed, the agent recommends a course for the whole review and shows the compatible actions and their impacts as a short numbered list. Material risks and unknowns stay visible; detailed evidence is available separately.

One native interaction offers **Approve all**, **Select a subset or revise**, and **Hold**, with optional free text. Approve all covers exactly the displayed, ready recommendations and stated resolutions in the current batch. The agent applies that approved scope without asking again for each item, file, section, language, or state. Future STOPs, outward actions not explicitly named in the reviewed choice, and undisclosed Binding Decision changes remain unapproved.

Incompatible alternatives cannot both be approved. The agent presents compatible complete plans or leaves the unresolved part pending. Individual selection is available when the human requests it, preferably through one native checklist or grouped form submission; serial questions and typed ID lists are not the default.

Only an actual submitted answer approving the current report and scope permits work. Details, revisions, cancellation, dismissal, no answer, and timeout are not approval.

A report of completed or read-only work needs no approval by itself. If a next step needs direction, the agent asks about that specific action; choosing it does not waive its own approval gates.

Native approval UI depends on the host and mode. When it is unavailable or not permitted, the agent states the limitation and stops instead of automatically substituting typed choices. A request receipt is not the human's answer.

When the work runs long and in parallel, DDL holds to these principles, each in the form implemented today (the [detailed guide](./design_philosophy_extended.md#37-principles-of-a-run) gives the research behind them):

- **Keep no slot idle while work is ready.** As each worker finishes, the next ready item starts: on Codex the gate's `runner` refills, on Claude the lead does when a completion notice arrives. How the slots were used is shown, and full use is not a goal.
- **Agents work on this machine; remote machines only run what they are handed.** Conversations, approvals and keys stay here, and a remote machine keeps only a throwaway copy.
- **Saving, recording and sending are separate.** The human checks by content a push, whose review lists every commit it sends, and a commit outside the grant. Snapshots, commits inside the grant and handovers are checked by scope in the plan, and the gate records them.
- **Approval follows the kind of operation, not the stage.** The human is asked when the design is decided, when a plan and its grant are approved, and before work leaves this machine. Only the work that depends on an answer stops, and a timeout decides nothing.
- **design.md is in the present tense; the history is in the past.**
- **Human attention is a budget.** Questions are removed by design, not by care, and counted.
- **Reduce the serial part, not the head count.** The lead keeps writers to the independent items and gives spare slots to verifying and exploring.
- **Verification is independent of the writer.** The lead gives a verifier only the diff and the acceptance conditions, never the writer's conversation, and executable checks decide.
- **What not to do** is listed under Anti-Patterns below.

## Stay Flexible

DDL is not a strict procedure.

- Skip Draft and go straight to Realize if you want
- Finish code before writing documents if that works

When work flows, let it flow.

What matters is updating documents after the work (Reflect), before the commit that closes it.

## Anti-Patterns

| Pattern                      | Problem                          |
|------------------------------|----------------------------------|
| Writing code without documents | The next session starts without the design |
| Strictly following the process | DDL is not a strict procedure |
| Letting LLM do everything | Human judgment and long-term perspective missing |
| Human does everything | LLM's articulation and technical knowledge unused |
| Making tooling the goal | Intent comes first, tools are means |
| Trying to persist DDL documents | Delete when no longer needed |
| Getting caught up in formality | DDL is temporary notes |
| Letting the agent pick the stack silently | The code is bound by a decision nobody agreed to |
| Treating harness memory as the design | The agent remembers, but the human has not agreed |
| Treating Direction as a contract | The outlook hardens into a plan nobody revisits |
| Approving from a summary | A compacted conversation is not the report; the human approves what is in front of them |
| Asking about work inside the grant | Approval turns into a formality, and the work waits on a question that changes nothing |
| Confirming a reviewed exit twice | The human sees the same contents again; the Git review is the one confirmation |
| A grant without an expiry, or widened silently | The approval outlives or outgrows the plan it was given for |
| Going ahead provisionally on what cannot be undone | An overturned answer cannot be taken back; a provisional choice needs a snapshot, and nothing leaves the machine until it is answered |
| Stacking one provisional choice on another | One overturned answer would undo both; the gate refuses a provisional question over items another one holds |
| Asking a question that stops all work while the human is away | Everything waits on one answer; a question names the items it holds, and the rest of the grant's work goes on |
| Leaving a slot idle while items are ready, or waiting for a wave | The work waits for nothing it depends on; refilling as each worker finishes keeps the slots in use |
| Aiming at full utilization | The goal is no idle slot while work is ready, not slots that are always full |
| Adding writers beyond the independent items | More writers do not shorten the serial parts, and their errors multiply |
| Letting a writer verify its own work | A verifier that shares the writer's context is lenient; executable checks decide |
| Going around the exit gate (Git beyond ssh, Git inside a script, another transfer) | What leaves the machine skips the human's one confirmation |

## Summary

DDL uses temporary notes to help Human and LLM share purposes and designs across sessions, agents, and harnesses. The loop stays flexible as implementation teaches you more.

Ultimately, code becomes the source of truth. Delete DDL documents when no longer needed.

Saving, recording and sending are separate. A snapshot saves the work tree as a commit under `refs/ddl/snapshots/` and moves no branch, index or file, so DDL puts no question before one; inside a grant the gate allows it, and outside one, as in a standalone command, the host's own permission policy decides the call. A push, and a commit no grant covers, are what the human checks by content, in one Git review; with `commit` in the grant, the gate records the local commits inside it without a question.

Before recording or sending changes with Git, the agent shows the final diff, exact message, and destination in a review file. One submitted native choice covers the compatible ready set; its question names the review ID and that file, so the question alone is enough to decide. The hook checks ordinary commit/push calls (a commit inside the grant aside) against that review even when STOP is open; an earlier implementation approval or a normal reply is insufficient. Changed contents require a new review. A call that matches the answered review is allowed by the hook, so the host does not ask a second time; the user's own ask rules still apply, and on Codex that allow, given through PermissionRequest, is not yet checked in a live run. This guard covers calls reaching the hook, with the runtime limits documented separately. The Close stage brings design.md and the documents up to date before that review, so one commit ends the work and no further command follows.

**Tool-Assisted Option:** [Claude](../../hosts/claude/) (`/draft`, `/realize`, `/reflect` + support commands) | [OpenAI Codex](../../hosts/codex/) (`$draft`, `$realize`, `$reflect` + support skills)

[Document history on GitHub](https://github.com/SnowLightPath/DDL/commits/main/docs/en/design_philosophy.md)
