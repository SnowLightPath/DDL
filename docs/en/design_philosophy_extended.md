# Design-Doc Loop (DDL) - Extended

> This document supplements [design_philosophy.md](./design_philosophy.md).
> Reference as needed after understanding the core DDL design.

-----

## 🗺️ How to Read

This document is intended for dictionary-style lookup.

| Goal | Section |
|------|---------|
| Understand theoretical background | [§1 Cognitive Foundations](#-1-cognitive-foundations) |
| Compare with existing methodologies | [§2 Related Methodologies](#-2-related-methodologies) |
| Systematize operations | [§3 Systematization Framework](#-3-systematization-framework) |
| Get concrete examples | [§4 Practical Examples](#-4-practical-examples) |
| Make adoption decisions | [§5 Adoption Criteria](#-5-adoption-criteria) |

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

### 2.5 AI-Era Development Paradigms (2025)

Three structured approaches to AI-assisted development emerged in 2025, each from a different origin and solving a different problem.

| Origin | Paradigm | Core Problem |
|--------|----------|-------------|
| Product development | Spec-Driven Development (SDD) | AI generates wrong code without specs |
| Enterprise development | AI-Driven Development Life Cycle (AI-DLC) | SDLC doesn't account for AI as primary executor |
| Research / exploratory development | Design-Doc Loop (DDL) | Design intent is lost across sessions |

All three share a common background: unstructured AI coding ("vibe coding") doesn't scale. Each structures the Human-AI relationship differently.

#### SDD in Brief

Write specifications in natural language, then let AI generate code from them. Not one methodology—multiple tools (GitHub Spec Kit, Kiro, Tessl) differ significantly (Thoughtworks, 2025). The spec is the source of truth; code is derived.

#### AI-DLC in Brief

AWS-originated methodology (Raja SP et al., 2025) that redesigns the entire SDLC with AI as primary executor. Three phases: Inception (mob elaboration → requirements), Construction (mob construction → code), Operation (AI-monitored deployment). Redefines agile terminology: sprints → bolts (hours/days), epics → units of work. Human role: validate and approve AI proposals.

#### Structural Comparison

| Aspect | SDD | AI-DLC | DDL |
|--------|-----|--------|-----|
| Problem | AI code quality | Development velocity | Cognitive continuity |
| AI role | Generator | Teammate proposing artifacts | Equal partner |
| Human role | Spec author | Validator / approver | Co-thinker; role shifts per phase |
| Direction | Spec→Code (one-way) | AI proposes→Human approves | Doc⇄Code (bidirectional) |
| Knowledge flow | Specification→Code | AI artifacts→Human review | Design philosophy⇄Implementation |
| Iteration unit | Spec lifecycle | Bolt (hours/days) | Reflect loop (no fixed cadence) |
| Document lifecycle | Spec is source of truth | Artifacts are process byproducts | Document is temporary; code becomes truth |
| Scale assumption | Team with product spec | Enterprise (10–100+ engineers) | Small team / individual (1–5) |

#### Session Discontinuity

Each approach handles the session problem differently:

| Paradigm | Strategy | Mechanism |
|----------|----------|-----------|
| SDD | Persist the spec | Code is regenerable from spec; spec survives sessions |
| AI-DLC | Persist process artifacts | Requirements, stories, units stored in repository |
| DDL | Design as shared memory | DESIGN.md is the cognitive bridge between sessions |

SDD and AI-DLC treat persistence as a side effect of their workflow. DDL treats it as the central design problem.

#### Complementary Use

These paradigms occupy different layers and can coexist:

- DDL's Realize phase can use SDD-style specification—writing a spec before implementation is one way to Realize
- AI-DLC's mob elaboration can incorporate DDL's Reflect to feed implementation discoveries back into requirements
- SDD and AI-DLC don't address philosophy evolution (design principles changing through implementation); DDL does

The "waterfall criticism" (Marmelab, 2025) applies to SDD's one-way flow. AI-DLC mitigates this with short bolts. DDL sidesteps it entirely with its bidirectional loop.

DDL's role fluidity works in small-team exploratory contexts. In enterprise contexts requiring audit trails and clear accountability, AI-DLC's fixed roles (AI proposes, human approves) may be more appropriate. This is not a weakness—it reflects different operating constraints.

-----

## 🔧 §3 Systematization Framework

A framework for more systematic DDL operation. Use as an aid for understanding and operation, not as enforcement.

### 3.1 State Model

DDL operates in two layers: the **Core Loop** and **Support Commands**.

```
Core Loop:
        +-----------------------------------+
        |                                   |
        v                                   |
    +-------+     +-------+     +-------+   |
    | DRAFT | --> |REALIZE| <-> |REFLECT|   |
    +-------+     +-------+     +-------+   |
        |                           ^       |
        +---------------------------+-------+
                  (Skip OK)

Support Commands (invokable at any point):
    +--------+  +------+  +------------+  +---------+
    |RESONATE|  |COMMIT|  |REFACTORING |  |  DOCS   |
    +--------+  +------+  +------------+  +---------+
```

The Core Loop drives design evolution. Support Commands maintain quality around it.

| State | Entry Condition | Exit Condition |
|-------|-----------------|----------------|
| DRAFT | New feature or project start | Ideal experience articulated |
| REALIZE | DESIGN.md exists | Code embodies principles |
| REFLECT | Code written | Design updated |

| Support Command | Purpose |
|-----------------|---------|
| RESONATE | Synchronize multilingual document versions |
| COMMIT | Record verified changes to repository |
| DOCS | Audit and fix documentation quality |
| REFACTORING | Audit and fix code quality |

You can transition from any Core Loop state to any other. No strict ordering. Support Commands can be invoked at any point.

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

These categories are a subset of the broader Detection Targets system (§3.4).

### 3.4 Detection Targets

Detection Targets are automated checks that run at phase boundaries within each command. They catch problems before they propagate.

Each command defines its own D1–D7 targets specific to its purpose. Cross-cutting targets apply globally:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Vague Intent | Task description lacks measurable outcome |
| D2 | Scope Creep | Change touches files outside stated scope |
| D3 | Principle Violation | Action contradicts DESIGN.md principles |
| D4 | Missing Validation | No verification step after mutation |
| D5 | Leaked Specifics | Project-specific paths/commands hardcoded in framework files |
| D6 | Silent Failure | Error swallowed without user notification |
| D7 | Unreviewed Mutation | Shared artifact changed without STOP gate |

Example: `/reflect` defines its own targets (D1 Drift, D2 New Pattern, D3 Outdated Principle, D4 Stale Reference, D5 Self-Contradiction) while also being subject to global targets.

### 3.5 STOP Gates

A STOP gate is a mandatory human approval point. The system halts and presents its findings before making changes to shared artifacts.

```
Phase N: Analysis complete
    ↓
[STOP gate] — Present report, wait for approval
    ↓
Phase N+1: Apply approved changes only
```

Rules:
- STOP gates are **blocking** — never auto-proceed
- Every command that mutates shared artifacts (DESIGN.md, code, docs) must have at least one STOP gate
- The user can approve, reject, or modify each proposed change individually

STOP gates embody DDL's core principle: Human controls the pace. LLMs propose, humans decide.

### 3.6 Agent Swarm

When a task spans multiple independent scopes, parallel agent execution reduces time and improves coverage.

```
Lead agent
    ├── survey-{scope-1}  ──┐
    ├── survey-{scope-2}  ──┤── Parallel execution
    └── survey-{scope-3}  ──┘
            ↓
    Lead integrates results
            ↓
    Cross-scope analysis
```

Rules:
- Spawn agents only when 2+ independent scopes exist
- Agent naming: `{role}-{scope}` (e.g., `reader-backend`, `scanner-docs`)
- Each agent reads only its assigned scope
- Lead integrates results and runs cross-scope analysis
- Swarm is optional — single-scope tasks run without spawning

Scopes are defined in DESIGN.md, never hardcoded. This keeps the framework project-agnostic.

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

Commands implement DDL as Phase-based workflows with Detection Targets, STOP gates, and Agent Swarm support.

**Core Loop** — the Draft → Realize → Reflect cycle:

| Command | Intent |
|---------|--------|
| `/draft` | Write the user-side experience first |
| `/realize` | Write code based on design principles |
| `/reflect` | Update documents based on implementation |

**Support Commands** — invokable at any point:

| Command | Intent |
|---------|--------|
| `/resonate` | Synchronize multilingual document versions |
| `/commit` | Record verified changes to repository |
| `/docs` | Audit and fix documentation quality |
| `/refactoring` | Audit and fix code quality |

Each command follows the same structure:
1. **Phases** — ordered steps (INIT → READ → EXECUTE → VALIDATE)
2. **Detection Targets** — automated checks at phase boundaries (D1–D7 per command)
3. **Swarm triggers** — parallel agent execution when 2+ scopes exist
4. **STOP gates** — mandatory human approval before mutating shared artifacts
5. **Constraints** — invariants that must never be violated

Claude Code: → [examples/claude-commands/](../../examples/claude-commands/)
OpenAI Codex: → [examples/codex-skills/](../../examples/codex-skills/)

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
- Clark, A., & Chalmers, D. (1998). [The Extended Mind](https://academic.oup.com/analysis/article-abstract/58/1/7/153111). *Analysis*, 58(1), 7-19.
- Clark, A. (2008). [*Supersizing the Mind*](https://global.oup.com/academic/product/supersizing-the-mind-9780195333213). Oxford University Press.

### SECI Model
- Nonaka, I., & Takeuchi, H. (1995). [*The Knowledge-Creating Company*](https://global.oup.com/academic/product/the-knowledge-creating-company-9780195092691). Oxford University Press.
- Nonaka, I., Toyama, R., & Konno, N. (2000). [SECI, Ba and Leadership](https://www.sciencedirect.com/science/article/abs/pii/S0024630199001156). *Long Range Planning*, 33(1), 5-34.
- Gourlay, S. (2006). [Conceptualizing Knowledge Creation: A Critique of Nonaka's Theory](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-6486.2006.00637.x). *Journal of Management Studies*, 43(7), 1415-1436.

### Distributed Cognition
- Hutchins, E. (1995). [*Cognition in the Wild*](https://mitpress.mit.edu/9780262581462/cognition-in-the-wild/). MIT Press.
- Flor, N. V., & Hutchins, E. (1991). Analyzing Distributed Cognition in Software Teams. *Empirical Studies of Programmers: Fourth Workshop*, 36-64.

### Human-AI Collaboration
- Sabbah, J., & Li, F. (2025). [When Humans and Large Language Models Collaborate, Problem-Finding Illuminates](https://doi.org/10.1080/14479338.2025.2504428). *Innovation: Organization and Management*.

### AI-Era Development Paradigms
- Thoughtworks (2025). [Spec-Driven Development: Unpacking one of 2025's key new AI-assisted engineering practices](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices).
- Fowler, M. et al. (2025). [Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html). *martinfowler.com*.
- Marmelab (2025). [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html).
- AWS (2025). [AI-Driven Development Life Cycle: Reimagining Software Engineering](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/). *AWS DevOps Blog*.

### Related Methodologies
- Knuth, D. (1984). [Literate Programming](https://academic.oup.com/comjnl/article/27/2/97/343244). *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). *Cognitect Blog*.
- Beck, K. (1999). [*Extreme Programming Explained*](https://www.oreilly.com/library/view/extreme-programming-explained/0201616416/). Addison-Wesley.
- Meyer, B. (1992). [Applying Design by Contract](https://ieeexplore.ieee.org/document/161279/). *IEEE Computer*, 25(10), 40-51.

-----

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-02-14 | Expand §2.5 to three-way comparison (SDD / AI-DLC / DDL) |
| 2026-01-04 | Initial version |
