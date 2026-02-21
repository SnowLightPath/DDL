---
description: Design the document structure and outline
allowed-tools: Read, Write, Edit, Grep, Glob, Task
argument-hint: [topic or description]
disable-model-invocation: true
---

# draft

Design the document outline, audience, tone, and sources before writing.

## Usage

- `/scribe:draft` — Ask what document to write, then design the outline
- `/scribe:draft <topic>` — Design outline for a specific topic

## Phases

### Phase 0: INIT

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/document-writing/SKILL.md`
2. Read `scribe.md` if it exists — load any existing document design
3. If `scribe.md` exists with a complete outline → ask: "Revise existing design or start fresh?"

### Phase 1: DISCOVER

If the official `doc-coauthoring` skill is installed (`~/.claude/skills/doc-coauthoring/`), reference its Context Gathering stage for structured information collection from the user.

If user references source files or data:

1. Scan referenced files to understand available content
2. Identify key topics, data points, and themes from sources
3. Suggest outline sections based on source analysis

+++SWARM: 2+ source files referenced

```
  team: draft-discover
  spawn: reader-{source}
  type: Explore
  max: 5
  batch: auto
  each: |
    Read {source} and extract key topics, data points, and themes.
    Summarize what this source contributes to the document.
    Report findings to team-lead when done.
  collect: lead synthesizes all source insights into outline suggestions
```

### Phase 2: DESIGN

Collaborate with user to design the document:

1. If `$ARGUMENTS` is provided, use it as the initial topic/description
2. Ask: "What document do you want to write? Who will read it?"
2. Determine meta settings:
   - **format**: What output format? (md, pdf, docx, html, xlsx, pptx, pen, confluence)
   - **audience**: Who will read this?
   - **tone**: formal, casual, technical, or executive?
   - **language**: What language?
3. Build the outline together:
   - Propose section structure based on template and sources
   - Iterate with user until the structure feels right
4. Identify sources to reference in each section

+++DETECT:
  D1: Vague Outline — Section has no subsections or topic description
  D2: Audience Mismatch — Tone or depth doesn't match stated audience
  D3: Missing Source — Section references data but no source is listed
  D4: Orphan Source — Source file listed but not referenced by any section
  D5: Scope Overflow — Outline has 10+ sections (suggest consolidation)

+++STOP: on D2

### Phase 3: REPORT

+++STOP: always

Present the complete `scribe.md` design to user for approval:

+++Report:
| Field | Value |
|-------|-------|
| Title | {document title} |
| Format | {output format} |
| Audience | {target reader} |
| Tone | {writing tone} |
| Sections | {count} |
| Sources | {count} |
| Est. Words | {estimate} |

### Phase 4: SAVE

1. Write approved design to `scribe.md`
2. Suggest: "Run `/scribe:realize {filename}.{format}` to write the document"

## Constraints

+++NEVER: Write document content during /scribe:draft — outline only
+++NEVER: Choose format without asking the user
+++NEVER: Save design with unresolved audience mismatch (D2)
