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
| Measure effectiveness | [§6 Metrics](#-6-metrics) |
| Choose how to implement DDL | [§7 Implementation Options](#️-7-implementation-options) |
| Manage artifacts and their lifecycle | [§8 Artifacts and Lifecycle](#-8-artifacts-and-lifecycle) |

No need to read cover-to-cover. Pick what you need.

-----

## 🧩 §1 Cognitive Foundations

DDL intersects with several cognitive science and philosophy theories. These are not post-hoc rationalizations but frameworks referenced during design.

### 1.1 Extended Mind

Clark & Chalmers (1998) proposed "Extended Mind"—the claim that cognition doesn't complete in the brain but integrates with external tools.

The famous **Inga/Otto thought experiment**: Inga remembers the museum address in biological memory; Otto, with Alzheimer's, records it in a notebook. Clark argued Otto's notebook is **functionally equivalent** to Inga's memory.

design.md in DDL corresponds to "Otto's notebook."

| Functional Equivalence Criteria | Otto's Notebook | design.md |
|--------------------------------|-----------------|-----------|
| Always available | Always carried | Lives in repository |
| Directly accessible | Quick to reference | Loaded at session start |
| Automatically trusted | Followed without doubt | Respected as design principles |
| Consciously recorded in past | Intentionally noted | Explicitly recorded via Draft/Reflect |

This table is DDL's design rationale. By satisfying these 4 conditions, design.md functions as "extended memory" for the Human-LLM system.

**Harness memory is not the notebook.** Agent harnesses now keep memory of their own: instruction files, automatic memory, summaries of long conversations, progress files written for the next session. For the agent, that memory meets the first two conditions. For the human, what the agent wrote there usually fails the fourth: the agent wrote it, and the human never consciously endorsed it. design.md is the part both sides have agreed to. The two complement each other; neither replaces the other.

```
Traditional: Brain -> Thinking -> Action

DDL:  Human Brain <-> design.md <-> LLM
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
| Combination | Structure design.md, organize relationships between principles |
| Internalization | Restore context by reading design.md in next session |

SECI has been criticized for "weak empirical grounding" (Gourlay, 2006). DDL addresses this by presenting concrete, practice-verifiable methods.

### 1.3 Distributed Cognition

Hutchins (1995) proposed "Distributed Cognition"—the view that cognition is distributed across teams, tools, and environments.

Flor & Hutchins (1991) analyzed pair programming and showed that the system as a whole has cognitive properties distinct from individual programmers. DDL explicitly designs this distributed structure.

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

**Session Discontinuity Problem**: LLMs lack long-term memory. Accuracy drops significantly on long interaction histories. design.md is a practical solution to this problem.

Harnesses have since added memory (instruction files, automatic memory, compaction), which reduces forgetting within one agent. Two gaps remain. Memory written by the agent is not endorsed by the human. And whether a SWARM worker inherits the lead's conversation depends on the runtime and on how the worker is started. DDL therefore treats every worker as a new session: the lead builds each prompt from design.md, so five workers running in parallel need nothing beyond what their prompts say.

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

### 2.5 AI-Era Development Paradigms (2025–2026)

Three structured approaches to AI-assisted development emerged in 2025–2026, each from a different origin and solving a different problem.

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

#### Harness Engineering in Brief

In 2025–2026 the harness around the model became an engineering subject of its own. Anthropic described a harness for long-running agents in which an initializer agent sets up the environment, and each later session reads a progress file, a feature list, and the git log before choosing its work (Anthropic, 2025). OpenAI's harness engineering report describes a product built with no manually written code: engineers design the environment, specify intent, and build feedback loops, while Codex writes the code (Lopopolo, 2026).

Of everything these harnesses record and specify, DDL addresses the part the human must agree to: the experience, the decisions that bind it, and the gates where the human looks.

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
| Harness engineering | Persist agent progress | Progress file and feature list read at each session start (Anthropic, 2025) |
| DDL | Design as shared memory | design.md is the cognitive bridge between sessions |

SDD and AI-DLC treat persistence as a side effect of their workflow, and harness engineering persists the agent's working state. DDL treats persisting what the human agreed to as the central design problem.

#### Technology Choice

Spec Kit keeps technology out of the specification: `/speckit.specify` describes what and why, and `/speckit.plan` names the stack (GitHub, 2025). DDL keeps both in one Draft but in separate sections, and asks each technology why it binds the experience. A technology the human names with a reason (the experience depends on it, an external constraint requires it, or the human prefers it and says so) becomes a Binding Decision. An LLM proposal, a technology named without a reason, and a delegated choice stay unbound: they are listed under the table as `Unbound:` and bind nothing. An `Unbound:` line is either delegated to `/realize` or `awaiting choice`. For a delegated line, `/realize` states its pick and the reason in its plan; for an awaiting line, `/realize` asks the human to pick. A pick binds only when the human approves that plan: it then moves into the table with Source `approved in /realize plan (<date>)`. Once approved, design.md wins over later command arguments: a different technology named in an argument is a Binding Decision change and halts. Technology already present in the code is an existing premise: commands show it in their reports, and design.md does not record it; it becomes a Binding Decision only when the human gives a reason.

#### Complementary Use

These paradigms occupy different layers and can coexist:

- DDL's Realize phase can use SDD-style specification—writing a spec before implementation is one way to Realize
- AI-DLC's mob elaboration can incorporate DDL's Reflect to feed implementation discoveries back into requirements
- SDD and AI-DLC don't address philosophy evolution (design principles changing through implementation); DDL does
- Harness memory (progress files, automatic memory) carries the agent's working state; design.md carries what the human agreed to. Keep them apart: don't copy agent progress into design.md, and don't leave a binding decision only in agent memory

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
    +--------+  +---------+  +------+  +------------+  +---------+
    |VALIDATE|  |RESONATE*|  |COMMIT|  |REFACTORING |  |  DOCS   |
    +--------+  +---------+  +------+  +------------+  +---------+
    * this repository only; not in examples/
```

The Core Loop drives design evolution. Support Commands maintain quality around it.

| State | Entry Condition | Exit Condition |
|-------|-----------------|----------------|
| DRAFT | New feature or project start | Experience articulated; Binding Decisions, Direction, and Acceptance Gates recorded when they exist |
| REALIZE | design.md exists | Code embodies principles and Binding Decisions; gates pass |
| REFLECT | Code written | Design updated |

| Support Command | Purpose |
|-----------------|---------|
| VALIDATE | Run mechanical validation per scope as declared in design.md |
| RESONATE | Synchronize multilingual document versions (this repository only; not in examples/) |
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

Harnesses now keep this kind of session state themselves (automatic memory, conversation summaries, progress files). Keep in design.md only what the human has seen and accepted: a pending technology choice as an `Unbound:` line, other open items in Open Questions, settled ones in Experience, Binding Decisions, or Principles.

### 3.3 Design-Code Alignment Verification

Perspectives to support Reflect:

| Type | Content | Action |
|------|---------|--------|
| DRIFT | Code violates principle | Update principle or fix code |
| NEW_PATTERN | Undocumented pattern found | Add as principle |
| OUTDATED | Principle without implementation | Delete or implement |
| BINDING_DRIFT | Code departs from a Binding Decision | The human chooses: fix the code, or change the decision |
| SPENT_DIRECTION | Direction stages are marked passed | Replace them with the outcome; delete the section when every stage is done |
| SPENT_ACCEPTANCE | Every Acceptance Gate is marked passed, so the work is accepted | Move lasting checks into Validation; delete the section |

These categories are a subset of the broader Detection Targets system (§3.4).

**Passed marks.** `/realize` appends `passed <date>` to each gate that passes: in the stage's Gate cell for Direction (for example `human approval, passed 2026-10-20`), and after the gate for Acceptance Gates. It adds `(approved in advance)` when a human gate did not fire. The work is accepted when every Acceptance Gate is marked passed. `/reflect` reads only these marks and never infers a pass from conversation memory.

Gates are never dropped. A merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage, or to the end of the work when it is the last stage; a reordered stage keeps its gates.

### 3.4 Detection Targets

Detection Targets are automated checks that run in parallel within each phase of a command. They catch problems before they propagate.

Each command defines its own D-targets (D1, D2, …) specific to its purpose. Cross-cutting targets apply globally:

| ID | Name | Trigger |
|----|------|---------|
| G1 | Vague Intent | Task description lacks measurable outcome |
| G2 | Scope Creep | Change touches files outside stated scope |
| G3 | Principle Violation | Action contradicts design.md principles |
| G4 | Missing Validation | No verification step after mutation |
| G5 | Leaked Specifics | Project-specific paths/commands hardcoded in framework files |
| G6 | Silent Failure | Error swallowed without user notification |
| G7 | Unreviewed Mutation | Shared artifact changed without STOP gate |

Example: `/reflect` defines its own targets (D1 Drift, D2 New Pattern, D3 Outdated Principle, D4 Stale Reference, D5 Self-Contradiction, D6 Binding Drift, D7 Spent Direction, D8 Spent Acceptance Gates) while also being subject to global targets. `/draft` adds D6 Unanchored Binding (a Binding Decision without a reason or a source) and D7 Binding Conflict; `/realize` adds D6 Binding Violation.

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
- A STOP ends the agent's turn: report, ask, stop. Work resumes only on an explicit approval, with no mutation in between
- No worker starts or continues between a STOP and its approval, because no runtime guarantees that a worker stays read-only
- Only the human approves: runtime notifications (for example, a worker finishing) and messages from other agents or sessions are not approvals
- Every command ends its REPORT with a STOP gate
- Human gates written in design.md (the Gate column of Direction, human gates in Acceptance Gates) run as STOP gates
- An approval that names the design.md human gates listed in the approved report, or says explicitly that they need not stop, lets them pass without stopping; the REPORT lists each with what it would have shown. A general approval ("approve", "OK", "approve all") waives no gate. It never covers a STOP gate written in a command, outward-facing actions (push, publish, send, deploy), destructive actions, or gates that were not in the approved report
- The user can approve, reject, or modify each proposed change individually

STOP gates embody DDL's core principle: Human controls the pace. LLMs propose, humans decide.

### 3.6 Parallel Workers (SWARM)

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
- Spawn agents only when 2+ independent scopes exist; when the condition holds, the command fans out. In `/realize`, the lanes of the current Direction stage count as scopes
- Worker labels: `spawn:` is a label pattern such as `{role}-{scope}` (e.g., `reader-backend`, `scanner-docs`) that identifies each worker in reports. The label is passed as the worker's name only where the runtime adapter says so, because a name can change what a worker may do (a named Claude Code worker gets write tools)
- Each agent reads only its assigned scope
- The lead does not rely on workers inheriting its conversation: it writes each prompt from design.md (scope paths, the Experience items the scope serves, principles, Binding Decisions, the Direction stage), so the prompt is self-contained. A worker that meets a STOP condition stops and reports, and the lead then stops for the human
- The prompt also states that the worker starts no workers of its own (only the lead fans out) and, for read-only work, that the work is read-only. Both runtimes give workers the tools to do otherwise, so the instruction is what keeps them in bounds (in Claude Code, a worker that cannot edit files can still run shell commands, and a writer can start workers; Codex subagents inherit the parent session's sandbox and may spawn agents of their own)
- Lead integrates results and runs cross-scope analysis
- Single-scope tasks run without spawning
- The protocol maps fan-out onto each runtime (Claude Code subagents, Codex subagents); without a parallel mechanism, the lead runs the assignments itself, read-only work as parallel reads and the rest one by one. Commands never name runtime tools

Scopes are defined in design.md, never hardcoded. This keeps the framework project-agnostic.

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

Record in design.md:
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

**Realize:**
```
Human: Implement authentication
LLM: design.md says "Authentication Transparency", so I'll
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

Add to design.md:
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

**Reverse-generate design.md:**
```markdown
## Core Principles
- Result-based Error Handling: No exceptions
- Explicit Side Effects: Indicate in function names
```

Reflect → design.md without Draft. An example of "transition from any state."

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

design.md gets rewritten frequently. This is normal. Evidence that design isn't stable—and evidence that DDL is working.

### Example 4: Draft with Binding Decisions and Direction

A web feature whose experience depends on its framework.

**Draft:**
```
Human: Internal knowledge search. The answer should appear while it is being written.
       I want to build it with Next.js.
LLM:   I split this into experience and binding. Two questions: should it be limited
       to the App Router? And what should the user see when nothing is found,
       or when the search fails?
Human: Yes, App Router. Nothing found: three related queries. Failure: keep the question, offer Retry.
```

Record in design.md:
```markdown
## Experience
Within a second of sending a question, the answer starts to appear and grows as it is
written. Sources are listed below it.
- Nothing found: "No results", plus three related queries
- Failure: the question stays in the box, with "Retry"

## Binding Decisions
| Decision | Why it binds | Source |
|---|---|---|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

## Direction
| Stage | Work (parallel lanes) | Human sees | Gate |
|---|---|---|---|
| S0 | Fix the search API as a CLI | sample CLI output | `npm test` |
| S1 | Three screen states, one lane each | three screenshots | human approval |
| S2 | Streaming display | a screen recording | `npx playwright test` |
```

**Realize:**
```
LLM: Binding Decisions honored (package.json, app/). S0 passed `npm test`: its Gate
     cell now reads "`npm test`, passed 2026-10-20". S1 and S2 merged; both gates
     (`npx playwright test`, then human approval) moved to the end of the merged stage.
LLM: Stop. Hosting serves static files only, so the server cannot stream the answer,
     and streaming is why Next.js App Router binds. Options: request a Node runtime,
     stream from a separate API server, show the answer only when it is complete,
     or change the Binding Decision. You choose.
```

**Reflect:**

The human chose a Node runtime, so Binding Decisions match the code. Every stage is marked passed, so Direction is deleted (version control keeps the history). The stop button added during implementation goes into Experience.

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
Write in design.md:
✓ Concept level (why)
  e.g., "Authentication should be transparent"
✓ Design level (how)
  e.g., "Use Context Manager Pattern"
△ Implementation level (important decisions only)
  e.g., "Chose JWT, reason: stateless"
  Binding Decisions live at this level: the decision, why it binds, and its source (the human's words and the date, or the human's approval of a report that listed it)

Don't write:
✗ All API details
✗ What's obvious from code
```

The principle: "Minimum information needed to restore context in the next session."

### README-as-design Alternative

design.md is not mandatory. What matters is that *some* shared notebook exists between Human and LLM — Otto's notebook, in any file form.

For projects where the public surface itself is the design (typically open-source libraries, CLIs, or HTTP APIs), the README plus the API reference and guides can serve as the living spec:

| Situation | Suggested Notebook |
|-----------|-------------------|
| Application / multi-deliverable / research project | `design.md` |
| Public library where API == design | `README.md` + `docs/` (API reference, guides) |
| Tiny tool (single script) | docstring at top of file |

Rules of thumb:
- The notebook must be **loaded at session start** and **referenced before changes**, regardless of file name
- Name the notebook files in the runtime guidance (`CLAUDE.md` or `AGENTS.md`); the protocol allows this. Commands then read and write the named files wherever the protocol or a command says design.md, so README updates are design updates and `/reflect` writes to the README and guides
- Switch to a separate design.md the moment design diverges from what users need to read

This is the AgenticFlow pattern: a public Python library whose `CLAUDE.md` and `AGENTS.md` name `README.md` + `docs/en/` as the design documents. The README documents the contract, and the development guide (`docs/en/guides/development-workflow.md`, in the AgenticFlow repository) holds the scope matrix and the validation commands, so a separate design.md would be redundant. The four functional-equivalence conditions (always available, directly accessible, automatically trusted, consciously recorded) are satisfied by these files themselves.

-----

## 📊 §6 Metrics

Metrics for understanding DDL effectiveness. Numbers are guidelines—adjust per project.

| Metric | Definition | Measurement | Healthy Target |
|--------|------------|-------------|----------------|
| Session Continuity | Can you resume previous session's intent? | "Success" if you grasp previous discussion and continue work within 5 minutes | Success rate > 80% |
| Design-Code Alignment | Are principles reflected in code? | Ratio of implemented principles to total in design.md | > 70% |
| Document Freshness | Does design.md reflect current state? | Days since last update | < 1 week |
| Binding Alignment | Does the code honor every Binding Decision? | Ratio of honored Binding Decisions | 100% |

Note on "Session Continuity": No need for rigorous measurement. If "I can't remember what we were doing" or "I'm re-explaining everything to the LLM" happens frequently, there's a problem with design.md granularity or update frequency.

-----

## 🛠️ §7 Implementation Options

### Option 1: Pure Discipline
No tools, discipline only. Most lightweight. Recommended as starting point.

### Option 2: Template-Based

```markdown
# design.md Template
## Intent
## Scopes
## Experience
## Binding Decisions
## Direction
## Acceptance Gates
## Core Principles
## Validation
## Open Questions
## Changelog
```

> Just a starting point. Discard if it doesn't fit. Experience comes first; Binding Decisions, Direction, and Acceptance Gates are optional. Scopes and Validation are what the commands read for fan-out and checks.

### Option 3: Workflow Integration
Incorporate Reflect into PR checklists. For team development.

### Option 4: Tool-Assisted

Commands implement DDL as Phase-based workflows with Detection Targets, STOP gates, and parallel workers (+++SWARM).

**Core Loop** — the Draft → Realize → Reflect cycle:

| Command | Intent |
|---------|--------|
| `/draft` | Write the user-side experience first, with the decisions and outlook it depends on |
| `/realize` | Write code based on design principles |
| `/reflect` | Update documents based on implementation |

**Support Commands** — invokable at any point:

| Command | Intent |
|---------|--------|
| `/validate` | Run mechanical validation per scope (lint/test/build) |
| `/resonate` (this repository only; not in examples/) | Synchronize multilingual document versions |
| `/commit` | Record verified changes to repository |
| `/docs` | Audit and fix documentation quality |
| `/refactoring` | Audit and fix code quality |

Each command follows the same structure:
1. **Phases** — ordered steps (INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY)
2. **Detection Targets** — automated checks that run in parallel within their phase (D1, D2, … per command)
3. **+++SWARM** — parallel workers per scope through the runtime's own mechanism (Claude Code subagents, Codex subagents) when 2+ scopes exist; without a parallel mechanism, the lead runs the assignments itself, read-only work as parallel reads and the rest one by one
4. **STOP gates** — mandatory human approval before mutating shared artifacts; the agent ends its turn and waits
5. **Constraints** — invariants that must never be violated
6. **Runtime adapters** — one table in the protocol maps the directives onto each harness, so commands never name runtime tools

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

binding:
  - decision: "Python (asyncio)"
    why: "The experience is async consumer code: async with APIClient(...)"
    source: '"I want to use it with async with" (2026-10-17)'

session:
  last_topic: "Authentication flow design"
```

Enables automated verification and session continuity tracking. However, if tools become the goal, you've missed the point.

-----

## 📦 §8 Artifacts and Lifecycle

| Name | Purpose | Persistence |
|------|---------|-------------|
| design.md | Design philosophy, concept definitions | Temporary |
| Direction (in design.md) | Outlook on the path to implementation | Most temporary: deleted when every stage is done |
| Acceptance Gates (in design.md) | Definition of done | Deleted once every gate is marked passed (the work is accepted); lasting checks move to Validation first |
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
- Move Binding Decisions into README requirements or an ADR once the code embodies them (the code shows what was chosen, not why), only with the human's approval in `/reflect`; the commands then stop checking them
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
- GitHub (2025). [Spec Kit](https://github.com/github/spec-kit). *GitHub*.
- Anthropic (2025). [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). *Anthropic Engineering*.
- Lopopolo, R. (2026). [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/). *OpenAI*.

### Related Methodologies
- Knuth, D. (1984). [Literate Programming](https://academic.oup.com/comjnl/article/27/2/97/343244). *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). *Cognitect Blog*.
- Beck, K. (1999). [*Extreme Programming Explained*](https://www.oreilly.com/library/view/extreme-programming-explained/0201616416/). Addison-Wesley.
- Meyer, B. (1992). [Applying Design by Contract](https://ieeexplore.ieee.org/document/161279/). *IEEE Computer*, 25(10), 40-51.

-----

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-10-17 | Harness-era revision: harness memory and design.md (§1.1, §1.4), harness engineering and technology choice (§2.5), VALIDATE in the state model (§3.1), harness session state (§3.2), Binding and Direction checks (§3.3, §3.4), G1–G7 IDs (§3.4), STOP semantics and parallel workers (§3.5, §3.6), Example 4, Binding Decisions in §5, §6, §8, template sections (§7), three references; follow-up: passed marks and retired Acceptance Gates (§3.3, §3.4, Example 4, §8), no worker started or continued during a STOP and no approval from notifications or other agents (§3.5), worker labels, self-contained prompts, and the read-only and no-nesting instructions in each prompt (§1.4, §3.6), terminology alignment (Codex subagents in §3.6 and §7; D1, D2, … in §7), a notebook named by runtime guidance (§5), Phases in the protocol's role order (§7); notebook named design.md throughout; `Unbound:` lines, approved picks, arguments that would change a Binding Decision, and existing premises (§2.5); gates never dropped (§3.3); every REPORT ending with a STOP gate and gates outside the approved report never approved in advance (§3.5); the lead's fallback without a parallel mechanism (§3.6, §7); `/resonate` marked repository-only (§3.1, §7); approval of a report as a Binding Decision source (§5); How to Read rows for §6–§8; the `/draft` intent (§7) |
| 2026-04-25 | VALIDATE support command (§3.1, §7); README-as-design Alternative (§5) |
| 2026-02-14 | Expand §2.5 to three-way comparison (SDD / AI-DLC / DDL) |
| 2026-01-04 | Initial version |
