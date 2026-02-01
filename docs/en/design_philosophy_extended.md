# Design-Doc Loop (DDL) - Extended

> This document supplements [design_philosophy.md](./design_philosophy.md).
> Reference as needed after understanding the core DDL design.

-----

## 🗺️ How to Read

This document is intended for dictionary-style lookup.

| Goal | Section |
|------|---------|
| Understand theoretical background | §1 Cognitive Foundations |
| Compare with existing methodologies | §2 Related Methodologies |
| Systematize operations | §3 Systematization Framework |
| Get concrete examples | §4 Practical Examples |
| Make adoption decisions | §5 Adoption Criteria |

No need to read cover-to-cover. Pick what you need.

-----

## 🧩 §1 Cognitive Foundations

DDL intersects with several cognitive science and philosophy theories. These are not post-hoc rationalizations but frameworks referenced during design.

### 1.1 Extended Mind

Clark & Chalmers (1998) proposed "Extended Mind"—the claim that cognition doesn't complete in the brain but integrates with external tools.

The famous **Inga/Otto thought experiment**: Inga remembers the museum address in biological memory; Otto, with Alzheimer's, records it in a notebook. Clark argued Otto's notebook is **functionally equivalent** to Inga's memory.

DESIGN.md in DDL corresponds to "Otto's notebook."

| Functional Equivalence Criteria | Otto's Notebook | DESIGN.md |
|--------------------------------|-----------------|-----------|
| Always available | Always carried | Lives in repository |
| Directly accessible | Quick to reference | Loaded at session start |
| Automatically trusted | Followed without doubt | Respected as design principles |
| Consciously recorded in past | Intentionally noted | Explicitly recorded via Draft/Reflect |

This table is DDL's design rationale. By satisfying these 4 conditions, DESIGN.md functions as "extended memory" for the Human-LLM system.

```
Traditional: Brain -> Thinking -> Action

DDL:  Human Brain <-> DESIGN.md <-> LLM
                  |
          One cognitive system
```

### 1.2 SECI Model

Nonaka's SECI model (1995) describes conversion cycles between tacit and explicit knowledge.

```
+---------------+---------------+
|  Socialization| Externalize   |
|    (share)    |  (articulate) |
| Tacit -> Tacit| Tacit -> Form |
+---------------+---------------+
| Internalize   | Combination   |
|   (embody)    | (systematize) |
| Form -> Tacit | Form -> Form  |
+---------------+---------------+
```

DDL correspondence:

| Phase | DDL Example |
|-------|-------------|
| Socialization | Share "something like this" through Human-LLM dialogue |
| Externalization | Articulate experience in Draft |
| Combination | Structure DESIGN.md, organize relationships between principles |
| Internalization | Restore context by reading DESIGN.md in next session |

SECI has been criticized for "weak empirical grounding" (Gourlay, 2006). DDL addresses this by presenting concrete, practice-verifiable methods.

### 1.3 Distributed Cognition

Hutchins (1995) proposed "Distributed Cognition"—the view that cognition is distributed across teams, tools, and environments.

Flor & Hutchins (1992) analyzed pair programming and showed that the system as a whole has cognitive properties distinct from individual programmers. DDL explicitly designs this distributed structure.

```
  Human <-------> Document <-------> LLM
    |                |                |
 Intuition       Shared           Pattern
 Long-term       Memory           Recognition
 Values          Persist          Tech Knowledge
```

Where to delegate what—this awareness is DDL's core.

### 1.4 Human-AI Collaboration Research

Research on LLM collaboration has surged in 2024-2025.

**Session Discontinuity Problem**: LLMs lack long-term memory. Accuracy drops significantly on long interaction histories. DESIGN.md is a practical solution to this problem.

**LLM as Cognitive Extension**: Sabbah & Li (2025) argue that LLMs can compensate for human bounded rationality.

| Human Constraint | LLM Compensation | DDL Realization |
|-----------------|------------------|-----------------|
| Bounded rationality | Exhaustive exploration | Expand options in Draft |
| Satisficing | Optimal solution pursuit | Check against principles in Realize |
| Uncertainty avoidance | Risk assessment | Discuss in dialogue |

LLMs don't replace humans—they complement. DDL structures this complementary relationship.

-----

## 🔗 §2 Related Methodologies

DDL overlaps with existing methodologies. To avoid reinventing wheels, we clarify differences.

### 2.1 Documentation-Driven Development (DocDD)

In the lineage of Knuth's Literate Programming (1984). Based on the insight: "What's hard to explain is poorly designed."

| Aspect | DocDD | DDL |
|--------|-------|-----|
| Direction | One-way (Doc→Code) | Bidirectional (Doc⇄Code) |
| Purpose | Finalize specifications | Maintain shared memory |
| Persistence | Documents are deliverables | Documents are temporary |

### 2.2 Architecture Decision Records (ADR)

Popularized by Nygard (2011). Records design decisions and their rationale.

| Aspect | ADR | DDL |
|--------|-----|-----|
| Timing | Post-decision (static) | During decision (dynamic) |
| Updates | Append-only | Rewritable |
| Granularity | Architecture level | Concept to implementation |

Promoting DDL documents to ADR once stable is a valid workflow.

### 2.3 Test-Driven Development (TDD)

Core practice of XP by Beck (1999).

| Aspect | TDD | DDL |
|--------|-----|-----|
| Define first | Tests | Experience (ideal API) |
| Feedback loop | Red→Green→Refactor | Draft→Realize→Reflect |

TDD and DDL are orthogonal and can coexist. Draft → Test → Implement is a natural flow.

### 2.4 Design by Contract (DbC)

Formalized by Meyer in Eiffel (1986). Makes contracts (invariants) explicit.

| Aspect | DbC | DDL |
|--------|-----|-----|
| Level | Code (executable) | Design policy (conceptual) |
| Enforcement | Runtime checks | Discipline and dialogue |

-----

## 🔧 §3 Systematization Framework

A framework for more systematic DDL operation. Use as an aid for understanding and operation, not as enforcement.

### 3.1 State Model

```
        +-----------------------------------+
        |                                   |
        v                                   |
    +-------+     +-------+     +-------+   |
    | DRAFT | --> |REALIZE| <-> |REFLECT|   |
    +-------+     +-------+     +-------+   |
        |                           ^       |
        +---------------------------+-------+
                  (Skip OK)
```

You can transition from any state to any other. No strict ordering.

| State | Entry Condition | Exit Condition |
|-------|-----------------|----------------|
| DRAFT | New feature or project start | Ideal experience articulated |
| REALIZE | DESIGN.md exists | Code embodies principles |
| REFLECT | Code written | Design updated |

### 3.2 Session Context Preservation

To address the session discontinuity problem, organize information to preserve.

```yaml
session:
  last_topic: "Authentication flow design"
  pending_decisions:
    - "JWT token storage location"
  open_questions:
    - "Refresh token expiration?"
  state: REALIZE
```

Resume next session with "Last time we were discussing X."

### 3.3 Design-Code Alignment Verification

Perspectives to support Reflect:

| Type | Content | Action |
|------|---------|--------|
| DRIFT | Code violates principle | Update principle or fix code |
| NEW_PATTERN | Undocumented pattern found | Add as principle |
| OUTDATED | Principle without implementation | Delete or implement |

-----

## 💻 §4 Practical Examples

### Example 1: Complete Loop

Typical Draft → Realize → Reflect flow.

**Draft:**
```python
# This is the experience I want
async with APIClient("https://api.example.com") as client:
    users = await client.get("/users")
```

Record in DESIGN.md:
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

**Realize:**
```
Human: Implement authentication
LLM: DESIGN.md says "Authentication Transparency", so I'll
     auto-authenticate in __aenter__
```

```python
async def __aenter__(self):
    await self._authenticate()  # transparent
    return self
```

**Reflect:**

Token Refresh necessity discovered during implementation.

```python
async def _ensure_token(self):
    if self._token_expires_soon():
        await self._refresh_token()
```

Add to DESIGN.md:
- Token Refresh: Transparently refresh before expiration

### Example 2: Skipping Draft

Joining an existing codebase. Specs exist but design philosophy is unclear.

**Start from Reflect:**
```
Human: I want to organize this codebase's design philosophy
LLM: I'll read src/ and extract implicit patterns
```

Discovered patterns:
- All APIs return Result type
- Errors are values, not exceptions
- Side effects are explicitly marked

**Reverse-generate DESIGN.md:**
```markdown
## Core Principles
- Result-based Error Handling: No exceptions
- Explicit Side Effects: Indicate in function names
```

Reflect → DESIGN.md without Draft. An example of "transition from any state."

### Example 3: Realize-Reflect Iteration

Exploratory development where design isn't settled.

```
[Realize] Implement following principles
    |
[Reflect] Implementation revealed principle was impractical
    |
[Realize] Modify principle and re-implement
    |
[Reflect] Still feels wrong
    |
...repeat...
```

DESIGN.md gets rewritten frequently. This is normal. Evidence that design isn't stable—and evidence that DDL is working.

-----

## 🎯 §5 Adoption Criteria

### Effective Situations

| Situation | Reason |
|-----------|--------|
| Spans multiple sessions | Session discontinuity problem occurs |
| Many design decisions | Preserving decision rationale is important |
| Exploratory development | Recording trial-and-error is useful |
| Deep LLM collaboration | Shared memory is effective |

### Unnecessary Situations

| Situation | Reason |
|-----------|--------|
| Completes in single session | No discontinuity problem |
| Clear specs exist | Already formalized |
| Bug fixes / small changes | Overhead too large |

### Granularity Guidelines

```
Write in DESIGN.md:
✓ Concept level (why)
  e.g., "Authentication should be transparent"
✓ Design level (how)
  e.g., "Use Context Manager Pattern"
△ Implementation level (important decisions only)
  e.g., "Chose JWT, reason: stateless"

Don't write:
✗ All API details
✗ What's obvious from code
```

The principle: "Minimum information needed to restore context in the next session."

-----

## 📊 §6 Metrics

Metrics for understanding DDL effectiveness. Numbers are guidelines—adjust per project.

| Metric | Definition | Measurement | Healthy Target |
|--------|------------|-------------|----------------|
| Session Continuity | Can you resume previous session's intent? | "Success" if you grasp previous discussion and continue work within 5 minutes | Success rate > 80% |
| Design-Code Alignment | Are principles reflected in code? | Ratio of implemented principles to total in DESIGN.md | > 70% |
| Document Freshness | Does DESIGN.md reflect current state? | Days since last update | < 1 week |

Note on "Session Continuity": No need for rigorous measurement. If "I can't remember what we were doing" or "I'm re-explaining everything to the LLM" happens frequently, there's a problem with DESIGN.md granularity or update frequency.

-----

## 🛠️ §7 Implementation Options

### Option 1: Pure Discipline
No tools, discipline only. Most lightweight. Recommended as starting point.

### Option 2: Template-Based

```markdown
# DESIGN.md Template
## Intent
## Core Principles
## Open Questions
## Changelog
```

> Just a starting point. Discard if it doesn't fit.

### Option 3: Workflow Integration
Incorporate Reflect into PR checklists. For team development.

### Option 4: Tool-Assisted

Claude Code: `/draft`, `/realize`, `/reflect`
→ [examples/claude-commands/](../../examples/claude-commands/)

OpenAI Codex: `$draft`, `$realize`, `$reflect`
→ [examples/codex-skills/](../../examples/codex-skills/)

### Option 5: Structured Schema

Machine-readable format:

```yaml
# DESIGN.yaml
version: "1.0"
intent: "API client library"

principles:
  - id: P001
    name: "Context Manager Pattern"
    status: implemented
    related_code:
      - src/client.py:15-30

session:
  last_topic: "Authentication flow design"
```

Enables automated verification and session continuity tracking. However, if tools become the goal, you've missed the point.

-----

## 📦 §8 Artifacts and Lifecycle

| Name | Purpose | Persistence |
|------|---------|-------------|
| DESIGN.md | Design philosophy, concept definitions | Temporary |
| docs/adr/ | Design decision records | Permanent |
| src/ | Manifested code | Permanent |

```
Creation -> Use -> Integration -> Deletion
```

DDL documents persisting long-term is evidence that design isn't stable yet.

Integration patterns:
- Absorb into code comments
- Promote to README / API docs
- Persist as ADR
- Delete (became obvious from code)

-----

## 📚 References

### Extended Mind
- Clark, A., & Chalmers, D. (1998). The Extended Mind. *Analysis*, 58(1), 7-19.
- Clark, A. (2008). *Supersizing the Mind*. Oxford University Press.

### SECI Model
- Nonaka, I., & Takeuchi, H. (1995). *The Knowledge-Creating Company*. Oxford University Press.
- Nonaka, I., Toyama, R., & Konno, N. (2000). SECI, Ba and Leadership. *Long Range Planning*, 33(1).
- Gourlay, S. (2006). Conceptualizing Knowledge Creation: A Critique of Nonaka's Theory. *Journal of Management Studies*, 43(7), 1415-1436.

### Distributed Cognition
- Hutchins, E. (1995). *Cognition in the Wild*. MIT Press.
- Flor, N. V., & Hutchins, E. (1991). Analyzing Distributed Cognition in Software Teams. *Empirical Studies of Programmers: Fourth Workshop*.

### Human-AI Collaboration
- Sabbah, J., & Li, F. (2025). When Humans and Large Language Models Collaborate, Problem-Finding Illuminates. *Innovation: Organization and Management*. DOI: 10.1080/14479338.2025.2504428

### Related Methodologies
- Knuth, D. (1984). Literate Programming. *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). Documenting Architecture Decisions. *Cognitect Blog*.
- Beck, K. (1999). *Extreme Programming Explained*. Addison-Wesley.
- Meyer, B. (1992). Applying Design by Contract. *IEEE Computer*, 25(10), 40-51.

-----

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-01-04 | Initial version |
