# Parallel Writing Methodology

How Scribe uses SWARM to write document sections concurrently.

---

## Concept

Traditional document writing is sequential: write Section 1, then Section 2, etc. Scribe breaks this pattern by treating each section as an independent scope that can be written in parallel.

```
Sequential (traditional):
  §1 ──→ §2 ──→ §3 ──→ §4 ──→ merge
  [======================== total time]

Parallel (Scribe SWARM):
  §1 ──→ ┐
  §2 ──→ ├──→ merge ──→ unify
  §3 ──→ ┤
  §4 ──→ ┘
  [==== write][=merge=]
```

---

## When to Parallelize

The SWARM condition evaluates the number of top-level sections in `scribe.md`:

| Section count | Action |
|---------------|--------|
| 0–1 | Write inline, no SWARM |
| 2–5 | 1 writer per section |
| 6+ | Batch related sections (max 5 writers) |

Sections are identified by `### N. Title` entries under `## Outline` in `scribe.md`.

---

## Writer Agent Context

Each writer agent receives:

1. **Section outline**: The specific section and its subsections from `scribe.md`
2. **Meta settings**: tone, audience, language, style constraints
3. **Source references**: Only the sources relevant to that section
4. **Cross-reference hints**: Section titles of other sections for forward/backward references
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
- Include placeholders like [→ See §N] for cross-references
- Do not repeat content that belongs in other sections
- Match the specified tone consistently

Report completed section text to team-lead when done.
```

---

## Lead Agent: Merge Procedure

After all writer agents complete, the lead agent performs:

### Step 1: Assemble

Concatenate all sections in outline order, with consistent heading hierarchy:

```markdown
# Document Title

## 1. Section from writer-1
...content...

## 2. Section from writer-2
...content...

## 3. Section from writer-3
...content...
```

### Step 2: Resolve Cross-References

Replace all `[→ See §N]` placeholders with actual markdown links or section references:

```
[→ See §2]  →  [See Section 2: Analysis](#2-analysis)
```

### Step 3: Unify Tone

Read through the merged document and fix:
- Inconsistent terminology (same concept named differently across sections)
- Tone shifts (formal → casual within the same document)
- Perspective changes (first person → third person)
- Tense inconsistencies

### Step 4: Add Document Furniture

Based on the format and template:
- **Table of contents** (for documents with 3+ sections)
- **Executive summary** (for `report` template with `executive` audience)
- **Headers/footers** (document title, page numbers — handled by pandoc)
- **Bibliography/references** (if citations are used)

### Step 5: Format Conversion

Execute the appropriate format pipeline from `format-pipelines.md`.

---

## Handling Dependencies Between Sections

Some sections naturally depend on others (e.g., "Conclusions" depends on "Analysis"). Handle this with:

**Option A: Two-pass writing**
1. First pass: All sections write independently with cross-reference placeholders
2. Second pass: Dependent sections are revised with context from their dependencies

**Option B: Sequential dependency chain**
Mark dependencies in `scribe.md`:
```markdown
### 3. Conclusions
- depends: [1, 2]
```
Write independent sections in parallel first, then write dependent sections with full context.

---

## SWARM Block Template

```
+++SWARM: 2+ sections in scribe.md

  team: realize-write
  spawn: writer-{section}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Write section "{section}" for document "{title}".
    Follow meta settings: tone={tone}, audience={audience}, language={language}.
    Use sources relevant to this section.
    Include [→ See §N] placeholders for cross-references.
    Report completed section to team-lead when done.
  collect: |
    Lead assembles sections in outline order.
    Resolves cross-references.
    Unifies tone and terminology.
    Adds document furniture (TOC, summary).
    Converts to target format via format pipeline.
```
