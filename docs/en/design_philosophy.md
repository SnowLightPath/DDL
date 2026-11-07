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

Ultimately, code becomes the source of truth. DDL documents get integrated into code or docs, and are deleted when no longer needed. No need to be formal about it.

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

If you learn something from implementation, update the documents. Check the code against Binding Decisions, and replace finished Direction with what actually happened. In the tool-assisted loop, Reflect runs as the Close stage at the end of Realize, before the single commit that ends the work.

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

When a decision is needed, the agent recommends a course for the whole review and shows the compatible actions and their impacts as a short numbered list. Material risks and unknowns stay visible; detailed evidence is available separately.

One native interaction offers **Approve all**, **Select a subset or revise**, and **Hold**, with optional free text. Approve all covers exactly the displayed, ready recommendations and stated resolutions in the current batch. The agent applies that approved scope without asking again for each item, file, section, language, or state. Future STOPs, outward actions not explicitly named in the reviewed choice, and undisclosed Binding Decision changes remain unapproved.

Incompatible alternatives cannot both be approved. The agent presents compatible complete plans or leaves the unresolved part pending. Individual selection is available when the human requests it, preferably through one native checklist or grouped form submission; serial questions and typed ID lists are not the default.

Only an actual submitted answer approving the current report and scope permits work. Details, revisions, cancellation, dismissal, no answer, and timeout are not approval.

A report of completed or read-only work needs no approval by itself. If a next step needs direction, the agent asks about that specific action; choosing it does not waive its own approval gates.

Native approval UI depends on the host and mode. When it is unavailable or not permitted, the agent states the limitation and stops instead of automatically substituting typed choices. A request receipt is not the human's answer.

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

## Summary

DDL uses temporary notes to help Human and LLM share purposes and designs across sessions, agents, and harnesses. The loop stays flexible as implementation teaches you more.

Ultimately, code becomes the source of truth. Delete DDL documents when no longer needed.

Before recording or sending changes with Git, the agent shows the final diff, exact message, and destination in a review file. One submitted native choice covers the compatible ready set; its question names the review ID and that file, so the question alone is enough to decide. The hook checks ordinary commit/push calls against that review even when STOP is open; an earlier implementation approval or a normal reply is insufficient. Changed contents require a new review. This guard covers calls reaching the hook, with the runtime limits documented separately. The Close stage brings design.md and the documents up to date before that review, so one commit ends the work and no further command follows.

**Tool-Assisted Option:** [Claude](../../hosts/claude/) (`/draft`, `/realize`, `/reflect` + support commands) | [OpenAI Codex](../../hosts/codex/) (`$draft`, `$realize`, `$reflect` + support skills)

[Document history on GitHub](https://github.com/SnowLightPath/DDL/commits/main/docs/en/design_philosophy.md)
