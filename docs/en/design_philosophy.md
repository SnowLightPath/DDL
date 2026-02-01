# Design-Doc Loop (DDL)

## ✨ Intent

Human and LLM continue to share design principles across sessions.

DDL is not a rigid process—it's a collection of desired designs.

DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.

> For detailed background theory, examples, and guidelines, see [design_philosophy_extended.md](./design_philosophy_extended.md).
> You don't need to read everything. Reference only what you need, when you need it.

-----

## 🎯 Background: The Session Discontinuity Problem

Collaborative development with LLMs has a discontinuity problem:

- Long contexts are difficult to carry over accurately, just like for us
- Discussions are forgotten, just like for us
- Sessions with LLMs can unexpectedly disappear

So we share code design as memos with LLMs.

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

### Realize

**Intent:** Write code based on design principles.

Implement code following the documented principles.

### Reflect

**Intent:** Update documents based on implementation results.

If you learn something from implementation, update the documents.

Sometimes your fingers fly across the keyboard so fast that code outpaces design.

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
| Writing code without documents | Context is lost in the next session |
| Strictly following the process | DDL is not a strict procedure |
| Letting LLM do everything | Human judgment and long-term perspective missing |
| Human does everything | LLM's articulation and technical knowledge unused |
| Making tooling the goal | Intent comes first, tools are means |
| Trying to persist DDL documents | Delete when no longer needed |
| Getting caught up in formality | DDL is temporary notes |

-----

## 📋 Summary

DDL is not a strict methodology—it's a collection of purposes and designs.

It's temporary notes for Human and LLM to continue sharing design across sessions.

Ultimately, code becomes the source of truth. Delete DDL documents when no longer needed.

> **Tool-Assisted Option**: [Claude Code](../../examples/claude-commands/) | [OpenAI Codex](../../examples/codex-skills/)

-----

## 📝 Changelog

| Date       | Change                    |
|------------|---------------------------|
| 2025-01-16 | Initial version |
