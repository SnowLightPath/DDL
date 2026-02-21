---
description: Write and generate the document in the specified format
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
argument-hint: <filename.ext> or --confluence "Space/Title"
disable-model-invocation: true
---

# realize

Write the document following scribe.md, output in the specified format.

## Usage

- `/scribe:realize report.pdf` — Write and export as PDF
- `/scribe:realize notes.md` — Write as Markdown
- `/scribe:realize proposal.docx` — Write and export as Word
- `/scribe:realize dashboard.xlsx` — Generate as Excel spreadsheet
- `/scribe:realize deck.pptx` — Generate as PowerPoint
- `/scribe:realize wireframe.pen` — Create as Pencil design
- `/scribe:realize --confluence "Engineering/Q4 Report"` — Publish to Confluence

## Phases

### Phase 0: INIT

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/document-writing/SKILL.md`
2. Read `scribe.md` — extract title, meta, outline, sources
3. If no `scribe.md` exists → refuse ("Run `/scribe:draft` first")
4. Parse `$ARGUMENTS` to determine output filename and format (file extension or `--confluence` flag)
5. Check format pipeline dependencies:

```bash
# Verify tools for the target format
which pandoc || echo "MISSING: pandoc"
# For PDF: check PDF engine
# For XLSX: python3 -c "import openpyxl"
# For PPTX: python3 -c "from pptx import Presentation"
```

If dependencies are missing, report and ask user whether to install.

### Phase 1: PREPARE

1. Read all source files listed in `scribe.md ## Sources`
2. Create temporary workspace: `_scribe_tmp/`
3. For each source, extract relevant data and quotes per section assignment
4. Calculate word budget per section (if `max-words` is set in scribe.md)

### Phase 2: WRITE

+++SWARM: 2+ sections in scribe.md

```
  team: realize-write
  spawn: writer-{section}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    You are writing section "{section}" for document "{title}".

    Meta settings:
    - Audience: {audience}
    - Tone: {tone}
    - Language: {language}

    Section outline:
    {section_outline}

    Relevant source material:
    {section_sources}

    Other sections in this document (for cross-references):
    {other_section_titles}

    Word budget: ~{word_budget} words.

    Write this section in markdown format.
    Use ## for the section heading.
    Use [→ See §N] for cross-references to other sections.
    Match the tone consistently throughout.

    Write the completed section content and report to team-lead when done.
  collect: |
    Lead performs the merge procedure:
    1. Assemble all sections in outline order
    2. Resolve cross-references ([→ See §N] → actual links)
    3. Unify tone and terminology across sections
    4. Add document furniture (TOC, summary, headers)
    5. Write merged document to _scribe_tmp/{document}.md
```

For inline execution (1 section or sequential), write sections directly in order.

+++DETECT:
  D1: Tone Drift — Section tone doesn't match meta settings
  D2: Missing Content — Section outline topic not covered in output
  D3: Source Unused — Source assigned to section but not referenced
  D4: Cross-Reference Broken — [→ See §N] points to nonexistent section
  D5: Word Budget Exceeded — Section exceeds allocated word count by >30%
  D6: Format Incompatibility — Content uses features unsupported by target format

+++STOP: on D6

### Phase 3: CONVERT

Execute the format pipeline based on the target format.
Read `${CLAUDE_PLUGIN_ROOT}/skills/document-writing/references/format-pipelines.md` for the specific procedure.

**Markdown (.md)**:
```bash
cp _scribe_tmp/{document}.md {output_path}
```

**PDF (.pdf)**:
```bash
pandoc _scribe_tmp/{document}.md -o {output_path} \
  --pdf-engine=xelatex --toc --number-sections \
  -V geometry:margin=2.5cm
```

**Word (.docx)**:
```bash
pandoc _scribe_tmp/{document}.md -o {output_path} \
  --toc --number-sections
```

**HTML (.html)**:
```bash
pandoc _scribe_tmp/{document}.md -o {output_path} \
  --standalone --toc --number-sections
```

**Excel (.xlsx)**: Generate via Python + openpyxl script.

**PowerPoint (.pptx)**: Generate via Python + python-pptx script.

**Pencil (.pen)**: Use Pencil MCP tools (open_document, batch_design, get_screenshot).

**Confluence (--confluence)**: Use Atlassian MCP tools (createConfluencePage or updateConfluencePage).

### Phase 4: REPORT

+++STOP: always

1. Report output file path, size, and format
2. List sections written and word counts
3. List any Detection Targets that fired and their resolution
4. Suggest: "Run `/scribe:reflect` to review document quality"

+++Report:
| Field | Value |
|-------|-------|
| Output | {file path} |
| Format | {format} |
| Sections | {count written} |
| Words | {total word count} |
| Detection | {any targets fired} |

### Phase 5: CLEANUP

Remove temporary workspace:
```bash
rm -rf _scribe_tmp/
```

## Constraints

+++NEVER: Write without reading scribe.md first
+++NEVER: Skip format dependency check — missing tools must be reported
+++NEVER: Output a format different from what the user requested
