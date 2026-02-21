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

Commands are programs. This skill is the instruction set for document authoring. `+++` directives are instructions — when the processor (you) encounters one, execute its defined procedure. Code blocks within directive definitions are tool call templates: resolve variables and execute them.

---

## Compilation Model

Scribe processes documents as a compiler processes source code:

```
scribe.md (source)  →  /scribe:draft   (frontend — natural language → structured design)
                    →  /scribe:realize  (compiler + linker — design → sections → merged doc → target format)
                    →  /scribe:reflect  (static analyzer — quality check, drift detection)
```

| Compiler Concept | Scribe Equivalent |
|------------------|-------------------|
| Source code | `scribe.md` — the document design |
| Compilation unit | Section — independently processable |
| Parallel compilation (`make -j`) | `+++SWARM` — follows DDL-PROTOCOL §2.4 |
| Code generation (target backend) | Format pipeline — PDF, DOCX, PPTX, XLSX, HTML, .pen, Confluence |
| Symbol resolution (linking) | Cross-reference resolution (`[→ See §N]` → actual links) |
| Optimization pass | Tone unification across sections |
| Microcode library | `references/format-pipelines.md` — format-specific tool call templates |

---

## Core Principle: Section = Scope

In Scribe, the document outline defines the scopes. Each top-level section in `scribe.md` is an independent compilation unit that can be written, reviewed, and revised in parallel.

```
scribe.md Outline          SWARM mapping
─────────────────          ─────────────
### 1. Introduction    →   writer-introduction
### 2. Analysis        →   writer-analysis
### 3. Recommendations →   writer-recommendations
```

---

## Phase Role Mapping

Scribe commands use domain-specific phase names that map to DDL canonical roles:

| DDL Canonical | /scribe:draft | /scribe:realize | /scribe:reflect |
|---------------|---------------|-----------------|-----------------|
| INIT | Phase 0: INIT | Phase 0: INIT | Phase 0: INIT |
| SURVEY/READ | Phase 1: DISCOVER | Phase 1: PREPARE | Phase 1: ANALYZE |
| WORK/IMPLEMENT | Phase 2: DESIGN | Phase 2: WRITE | Phase 2: ASSESS |
| REPORT | Phase 3: REPORT | Phase 4: REPORT | Phase 3: REPORT |
| EXECUTE | Phase 4: SAVE | Phase 3: CONVERT | Phase 4: REVISE |
| VERIFY | — | Phase 5: CLEANUP | Phase 5: VERIFY |

---

## scribe.md Format

`scribe.md` is the source code — the document design. It defines what to write, not how to write it.

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

---

## Format Pipelines

Each output format has a specific code generation backend. See `references/format-pipelines.md` for the microcode library.

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

---

## Parallel Writing Procedure

SWARM execution follows DDL-PROTOCOL-SKILL.md §2.4 (TeamCreate → Scale → Spawn → Monitor → Collect → Shutdown). See `references/parallel-writing.md` for the document-specific `collect:` microcode — the merge procedure that assembles, links, and optimizes sections after parallel compilation.

**Summary**: When a document has 2+ top-level sections, spawn one writer agent per section. Each writer receives the section outline, meta settings, and source references. The lead agent executes the `collect:` microcode: assemble in outline order, resolve cross-references (symbol linking), unify tone (optimization pass), and convert to target format (code generation).

---

## Directive Reference

| Directive | Syntax | Count | Rule |
|-----------|--------|-------|------|
| `# header` | `# command-name` followed by one-line intent | 1 | Required |
| `## usage` | `## Usage` followed by dash-list of invocations | 1+ lines | Required |
| `### phase` | `### Phase N: NAME` | 4–6 | N starts at 0, ascending. Phase 0 INIT required: load SKILL → scribe.md. See Phase Role Mapping for domain-specific names |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D{n}` | 1+ | `always` required at REPORT phase. Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 5–7 | D starts at 1, ascending, unique per command. Trigger must be operationally verifiable |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block | 0+ | Evaluate condition against scribe.md. If 2+ sections: execute DDL-PROTOCOL §2.4. If 0–1: inline |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | 2–4 | Local constraints per command |
| `+++Report` | `+++Report:` followed by markdown table rows | 0–1 | Output template presented to human at STOP gate |
