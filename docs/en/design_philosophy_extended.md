# Design-Doc Loop (DDL) - Extended

> This document supplements [design_philosophy.md](./design_philosophy.md).
> After understanding the philosophy in the Core version, reference this as needed.
> You don't need to read everything.

-----

## Cognitive Foundation

### Extended Mind

Philosophers Andy Clark and David Chalmers proposed the concept of "Extended Mind." Cognition doesn't complete within the brain alone—it functions as one with external tools and environment.

In DDL, DESIGN.md functions as this "extended mind."

```
Traditional cognitive model:
  Brain → Thinking → Action

DDL cognitive model:
  Brain ←→ DESIGN.md ←→ LLM
               ↓
         One cognitive system
```

### Relationship to SECI Model

Ikujiro Nonaka's SECI model explains the knowledge creation process.

| Phase | Conversion | DDL Correspondence |
|-------|-----------|-------------------|
| **S**ocialization | Tacit→Tacit | Dialogue between Human and LLM |
| **E**xternalization | Tacit→Explicit | Draft (articulation) |
| **C**ombination | Explicit→Explicit | DESIGN.md structuring |
| **I**nternalization | Explicit→Tacit | Restoration in next session |

### DDL as Distributed Cognition

```
Human ←→ Document ←→ LLM
  │          │          │
Intuition  Shared     Pattern recognition
Long-term  memory     Articulation
vision

      → Functions as one system
```

-----

## Related Concepts

DDL overlaps with existing methodologies.

### Documentation-Driven Development (DocDD)

**Common:** Write documents first

**DDL difference:** DocDD is one-way (Doc→Code), DDL is bidirectional (Doc⇄Code)

### Architecture Decision Records (ADR)

**Common:** Record rationale for design decisions

**DDL difference:** ADR is static (post-decision), DDL is dynamic (loops)

### Test-Driven Development (TDD)

**Common:** Define "what should be" before implementation

**DDL difference:** TDD puts "tests" first, DDL puts "experience (Draft)" first. They can coexist.

### Design by Contract (Meyer)

**Common:** Make contracts (invariants) explicit

**DDL difference:** Code level vs design principle level. Complementary relationship.

-----

## Practical Examples

### Example 1: Complete Loop Flow

#### Draft
```python
# Human: I want this experience
async with APIClient("https://api.example.com") as client:
    users = await client.get("/users")
```

Save to DESIGN.md:
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

#### Realize (Design → Dialogue → Code)

**Design:**
```
DESIGN.md:
- Context Manager Pattern
- Authentication Transparency
```

**Dialogue:**
```
Human: Implement authentication
LLM: For transparent auth, auto-authenticate in __aenter__
```

**Code:**
```python
async def __aenter__(self):
    await self._authenticate()  # transparent
    return self
```

#### Reflect (Code → Dialogue → Design)

**Code:**
```python
async def _ensure_token(self):
    if self._token_expires_soon():
        await self._refresh_token()
```

**Dialogue:**
```
Human: Update DESIGN.md with this
LLM: Adding to Core Principles
```

**Design:**
```
Added to DESIGN.md:
- Token Refresh: transparently refresh before expiry
```

-----

## When to Use DDL

### Effective Situations
- Projects spanning multiple sessions
- Many design decisions
- Exploratory development
- Deep collaboration with LLM

### Unnecessary Situations
- Completed in single session
- Clear specifications exist
- Bug fixes / small changes

-----

## Granularity Guide

```
What to write in DESIGN.md:
✓ Concept level (why)
✓ Design level (how)
△ Implementation level (important decisions only)

What not to write:
✗ All API details
✗ What's obvious from code
```

### Principle
"Minimum information needed for the next session to restore context"

-----

## Implementation Options

### Option 1: Pure Discipline
No tools, discipline only. Most lightweight.

### Option 2: Template-Based

> **Warning**: This is a starting point, not a requirement. Adapt or discard as needed.

```markdown
# DESIGN.md Template
## Intent
## Core Principles
## Open Questions
## Changelog
```

### Option 3: Workflow Integration
Incorporate Reflect into PR checklists.

### Option 4: Tool-Assisted
```
/draft, /realize, /reflect
```

See [examples/claude-commands/](../../examples/claude-commands/) for ready-to-use Claude Code slash commands.

**Warning:** Tools can become shackles. If they obstruct the Intent, discard them.

-----

## Artifacts

| Name      | Purpose            | Persistence |
|-----------|--------------------|-------------|
| DESIGN.md | Design principles, concept definitions | Temporary |
| docs/adr/ | Design decision records | Permanent |
| src/      | Manifested code | Permanent |

-----

## Lifecycle of DDL Documents

```
Creation → Use → Integration → Deletion
```

If DDL documents persist, it's evidence that the design isn't stable yet.

-----

## Changelog

| Date       | Change                    |
|------------|---------------------------|
| 2025-01-16 | Initial version |
