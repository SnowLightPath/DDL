# Design-Doc Loop (DDL)

## ✨ Intent

Human and LLM continue to share design principles across sessions, agents, and harnesses.

DDL is not a rigid process—it's a collection of desired designs.

DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.

> For detailed background theory, examples, and guidelines, see [design_philosophy_extended.md](./design_philosophy_extended.md).
> You don't need to read everything. Reference only what you need, when you need it.

-----

## 🎯 Background: The Session Discontinuity Problem

Collaborative development with LLMs has a discontinuity problem:

- What one agent remembers, the next session, agent, or harness does not see
- What the agent remembers is not what the human agreed to
- The more a session holds, the less of it the model recalls, so context is a budget, for the model as for us

So we share code design as memos with LLMs.

### In the Harness Era

Agent harnesses such as Claude Code and Codex now carry memory of their own: instruction files, automatic memory, summaries of long conversations. That memory helps the agent recall, but what the agent writes there is not a record the human has agreed to. And when an agent hands work to parallel subagents, each subagent usually starts as a new session, so the discontinuity grows with every worker.

The scarce resource is no longer the model's memory but the human's attention and the context a session can hold. The shared memo now does two jobs: it keeps the design across sessions, and it tells agents, before they run, what the human has fixed and where the human wants to look.

The harness can also hold part of the loop. Where it offers hooks, agent definitions, and imports, DDL's adapters make a STOP hold until the human speaks, keep workers in their roles, and keep the memo in context; the rules themselves do not change, and a session without those mechanisms runs them as instructions.

-----

## 💡 Core Principle

```
Human ←→ Document ←→ LLM
              ↓
            Code
```

Documents connect Human and LLM. Code is written based on them.

However, design issues may be discovered during implementation. When that happens, update the documents.

Ultimately, code becomes the source of truth. DDL documents get integrated into code or docs, and are deleted when no longer needed. No need to be formal about it.

-----

## 🔄 The Loop

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
async with Client("https://api.example.com") as c:
    users = await c.get("/users")  # Is this usage good?
```

Some decisions cannot be separated from the experience. A library's language is its usage; a streaming interface may depend on its framework; an organization may require a platform. Draft records these as **Binding Decisions**, each with the reason it binds and its source (the human's words and the date, or the human's approval of a report that listed it):

```markdown
## Binding Decisions
| Decision | Why it binds | Source |
|---|---|---|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |
```

When you already see the path to implementation, Draft records it as **Direction**: stages, parallel lanes, and the points where you want to look. Direction is an outlook, not a contract. **Acceptance Gates** say what must hold when the work is done: commands that must pass, and approvals you will give. They are retired once the work is accepted.

Only the human binds. The LLM may propose a technology; it stays unbound until you choose it. Technology already present in the code is an existing premise: commands show it in their reports, and design.md does not record it; it becomes a Binding Decision only when the human gives a reason.

### Realize

**Intent:** Write code based on design principles.

Implement code following the documented principles and Binding Decisions. Follow Direction unless there is a reason not to, and say so when you deviate. Stop at the human gates.

### Reflect

**Intent:** Update documents based on implementation results.

If you learn something from implementation, update the documents. Check the code against Binding Decisions, and replace finished Direction with what actually happened.

Sometimes your fingers fly across the keyboard so fast that code outpaces design. In the harness era, they are often the agent's fingers.

---

Realize and Reflect are roughly inverse functions.

-----

## 🤝 Roles: Human and LLM

In DDL, Human and LLM are equal partners.

|       | Human              | LLM                    |
|-------|--------------------|------------------------|
| Strengths | Initial intuition, long-term vision, patience | Technical knowledge, pattern recognition, articulation |
| Weaknesses | Comprehensiveness, implementation details | Short-term bias |

Human controls the pace and corrects LLM's short-term bias.

When agents run long and in parallel, the human's share becomes concrete: decide what binds, decide where to look, and approve at those gates. Agents work between the gates.

-----

## 🌊 Stay Flexible

DDL is not a strict procedure.

- Skip Draft and go straight to Realize if you want
- Finish code before writing documents if that works

When work flows, let it flow.

What matters is updating documents after the work (Reflect).

-----

## ⚠️ Anti-Patterns

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

-----

## 📋 Summary

DDL is not a strict methodology—it's a collection of purposes and designs.

It's temporary notes for Human and LLM to continue sharing design across sessions, agents, and harnesses.

Ultimately, code becomes the source of truth. Delete DDL documents when no longer needed.

> **Tool-Assisted Option**: [Claude Code](../../examples/claude-commands/) (`/draft`, `/realize`, `/reflect` + support commands) | [OpenAI Codex](../../examples/codex-skills/) (`$draft`, `$realize`, `$reflect` + support skills)

-----

## 📝 Changelog

| Date       | Change                    |
|------------|---------------------------|
| 2026-10-18 | Instructions and mechanisms (In the Harness Era) |
| 2026-10-17 | Harness-era revision: harness-era background; Binding Decisions, Direction, and Acceptance Gates in Draft, with Acceptance Gates retired once the work is accepted; the human's role at gates; three anti-patterns; removed the Scribe Plugin option; approval of a report as a Binding Decision source, and technology already in the code as an existing premise; context-engineering background and one anti-pattern |
| 2026-01-04 | Initial version |
