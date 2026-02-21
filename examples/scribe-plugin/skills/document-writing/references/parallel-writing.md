# Parallel Writing — `collect:` Microcode

How Scribe assembles document sections after parallel compilation.

SWARM execution follows DDL-PROTOCOL-SKILL.md §2.4 (TeamCreate → Scale → Spawn → Monitor → Collect → Shutdown). This document defines the document-specific `collect:` microcode — the merge procedure executed by the lead agent after all writer agents complete.

---

## Compilation Model

```
Sequential (traditional):
  §1 ──→ §2 ──→ §3 ──→ §4 ──→ output
  [======================== total time]

Parallel (SWARM §2.4):
  §1 ──→ ┐
  §2 ──→ ├──→ collect: (link + optimize + codegen)
  §3 ──→ ┤
  §4 ──→ ┘
  [==== compile][== collect ==]
```

Each section is a **compilation unit**. Writer agents compile sections independently. The `collect:` microcode then links, optimizes, and generates the target format.

---

## Dynamic Scaling

The SWARM condition evaluates section count per DDL-PROTOCOL §2.3:

| Section count | max | Result |
|---------------|-----|--------|
| 0–1 | — | Inline, no SWARM |
| 2–5 | 5 | 1 writer per section |
| 6+ | 5 | Lead batches related sections (§2.3 `batch: auto`) |

Sections are identified by `### N. Title` entries under `## Outline` in `scribe.md`.

---

## Writer Agent Context

Each writer agent (compilation unit processor) receives:

1. **Section outline**: The specific section and its subsections from `scribe.md`
2. **Meta settings**: tone, audience, language, style constraints
3. **Source references**: Only the sources relevant to that section
4. **Cross-reference hints**: Section titles of other sections (external symbols for forward/backward references)
5. **Word budget**: If `max-words` is set, proportionally divided by section

### Writer Prompt Template

```
Write section "{section_title}" for the document "{document_title}".

Context:
- Audience: {audience}
- Tone: {tone}
- Language: {language}

Section outline:
{section_outline}

Relevant sources:
{filtered_sources}

Other sections (for cross-references):
{other_section_titles}

Word budget: approximately {word_budget} words.

Instructions:
- Write in markdown format
- Use the heading level appropriate for this section (## for top-level)
- Include placeholders like [→ See §N] for cross-references (unresolved symbols)
- Do not repeat content that belongs in other sections
- Match the specified tone consistently

Report completed section text to team-lead when done.
```

---

## `collect:` Microcode — Merge Procedure

After all writer agents complete (§2.4 Step 5), the lead agent executes the following merge procedure. This is the `collect:` field's microcode — the link + optimize + codegen passes.

### Pass 1: Assemble (Link)

Concatenate all compilation units in outline order:

```markdown
# Document Title

## 1. Section from writer-1
...content...

## 2. Section from writer-2
...content...

## 3. Section from writer-3
...content...
```

### Pass 2: Resolve Cross-References (Symbol Resolution)

Replace all unresolved symbols (`[→ See §N]`) with actual links:

```
[→ See §2]  →  [See Section 2: Analysis](#2-analysis)
```

### Pass 3: Unify Tone (Optimization)

Read through the merged document and fix:
- Inconsistent terminology (same concept named differently across sections)
- Tone shifts (formal → casual within the same document)
- Perspective changes (first person → third person)
- Tense inconsistencies

### Pass 4: Add Document Furniture

Based on the format and template:
- **Table of contents** (for documents with 3+ sections)
- **Executive summary** (for `report` template with `executive` audience)
- **Headers/footers** (document title, page numbers — handled by format pipeline)
- **Bibliography/references** (if citations are used)

### Pass 5: Code Generation (Format Conversion)

Execute the target backend from `format-pipelines.md`. If an official Anthropic skill is installed for the target format, read and follow its SKILL.md instead.

Write merged document to `_scribe_tmp/{document}.md`, then convert to target format.

---

## Handling Dependencies Between Sections

Some compilation units have dependencies (e.g., "Conclusions" depends on "Analysis"). Handle with:

**Option A: Two-pass compilation**
1. First pass: All sections compile independently with unresolved symbols
2. Second pass: Dependent sections are recompiled with resolved context from their dependencies

**Option B: Dependency-ordered scheduling**
Mark dependencies in `scribe.md`:
```markdown
### 3. Conclusions
- depends: [1, 2]
```
Compile independent sections in parallel first, then compile dependent sections with full context. This maps to §2.3 `batch: auto` where the lead groups dependent sections into later batches.
