---
name: document-writing
description: >
  This skill should be used when the user invokes Scribe commands
  ("draft", "realize", "reflect"), wants to "write a document",
  "create a report", "generate a PDF/DOCX/PPTX", references "scribe.md",
  mentions "parallel writing" or "section-based writing", or asks about
  document generation workflows. Do NOT use for code development,
  software documentation, or tasks unrelated to document authoring.
user-invocable: false
---

# Scribe — Document Writing Protocol

Parallel document authoring workflow. Human-LLM collaborative document creation.

This skill extends the DDL `+++` directive pattern for document writing. Commands follow the same Phase → DETECT → STOP → SWARM structure, but the unit of work is a **document section** instead of a code scope.

---

## Core Principle: Section = Scope

In Scribe, the document outline defines the scopes. Each top-level section in `scribe.md` is an independent unit that can be written, reviewed, and revised in parallel.

```
scribe.md Outline          SWARM mapping
─────────────────          ─────────────
### 1. Introduction    →   writer-introduction
### 2. Analysis        →   writer-analysis
### 3. Recommendations →   writer-recommendations
```

## scribe.md Format

`scribe.md` is the document design file (analogous to DDL's `design.md`). It defines what to write, not how to write it.

```markdown
# Document Title

## Meta
- format: docx
- language: ja
- audience: executive
- tone: formal
- template: report

## Outline
### 1. Section Name
- 1.1 Subsection topic
- 1.2 Subsection topic

### 2. Section Name
- 2.1 Subsection topic

## Sources
- data/sales.csv
- notes/meeting-2025-01.md
- https://example.com/reference

## Style
- max-words: 3000
- heading-style: numbered
- citation-style: footnotes
```

### Meta Fields

| Field | Values | Default |
|-------|--------|---------|
| `format` | `md`, `pdf`, `docx`, `html`, `xlsx`, `pptx`, `pen`, `confluence` | `md` |
| `language` | ISO 639-1 code (`en`, `ja`, `zh`, etc.) | `en` |
| `audience` | Free text describing the reader | — |
| `tone` | `formal`, `casual`, `technical`, `executive` | `formal` |
| `template` | `report`, `memo`, `proposal`, `manual`, `slides`, `spreadsheet` | — |

## Format Pipelines

Each output format has a specific tool chain. See `references/format-pipelines.md` for detailed procedures.

| Format | Pipeline | Tools | Official Skill |
|--------|----------|-------|----------------|
| `.md` | Direct write | Write tool | — |
| `.pdf` | Python + reportlab | Bash(python3) | `pdf` |
| `.docx` | JavaScript + docx-js | Bash(node) | `docx` |
| `.html` | Python + markdown | Bash(python3) | — |
| `.xlsx` | Python + openpyxl | Bash(python3) | `xlsx` |
| `.pptx` | JavaScript + pptxgenjs | Bash(node) | `pptx` |
| `.pen` | Pencil MCP tools | MCP tools | — |
| `confluence` | Atlassian MCP | MCP tools | — |

Official skills: `github.com/anthropics/skills`. When installed, the CONVERT phase reads and follows the skill's SKILL.md instead of the fallback pipeline.

## Parallel Writing Procedure

See `references/parallel-writing.md` for the full SWARM execution procedure for section-parallel writing.

**Summary**: When a document has 2+ top-level sections, spawn one writer agent per section. Each writer receives the section outline, meta settings, and source references. The lead agent merges results, unifies tone, resolves cross-references, and converts to the target format.

## Directive Reference

Scribe commands use the same `+++` directives as DDL:

| Directive | Scribe Usage |
|-----------|-------------|
| `+++STOP` | Pause before writing (outline approval), before finalizing (review) |
| `+++DETECT` | Check for document quality issues (tone drift, missing sections, stale refs) |
| `+++SWARM` | Parallel section writing — condition is `2+ sections in scribe.md` |
| `+++NEVER` | Document-specific prohibitions per command |
| `+++Report` | Present findings table at STOP gates |
