---
description: Review document quality and reconcile with scribe.md
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
argument-hint: [document-path]
disable-model-invocation: true
---

# reflect

Review document quality, check alignment with scribe.md, and improve.

## Usage

- `/scribe:reflect` — Review the most recently generated document
- `/scribe:reflect report.pdf` — Review a specific document

## Phases

### Phase 0: INIT

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/document-writing/SKILL.md`
2. Read `scribe.md` — extract the original design (outline, meta, sources)
3. Read the target document from `$ARGUMENTS` (or most recently generated output):
   - For `.md`: read directly
   - For `.pdf/.docx/.html`: convert back to text via pandoc for analysis
   - For `.xlsx`: read via Python + openpyxl
   - For `.pptx`: read via Python + python-pptx
   - For `.pen`: use Pencil MCP `batch_get` to read content
   - For Confluence: use Atlassian MCP `getConfluencePage`
4. If no `scribe.md` exists → read document standalone, infer structure

### Phase 1: ANALYZE

+++SWARM: 2+ sections in document

```
  team: reflect-analyze
  spawn: reviewer-{section}
  type: Explore
  max: 5
  batch: auto
  each: |
    Review section "{section}" of the document against scribe.md design.
    Check for:
    - Completeness: all outline topics covered?
    - Tone: matches meta settings?
    - Sources: referenced material properly used?
    - Quality: clear, well-structured, appropriate depth?
    - Cross-references: valid and helpful?
    Report findings with severity (critical/warning/info) to team-lead when done.
  collect: |
    Lead integrates all section reviews.
    Performs cross-section analysis:
    - Tone consistency across sections
    - Terminology consistency
    - Logical flow between sections
    - Overall document coherence
```

### Phase 2: ASSESS

Lead performs holistic document assessment:

1. **Completeness check**: Every scribe.md outline item has corresponding content
2. **Source verification**: All listed sources are referenced; no phantom citations
3. **Structure check**: Heading hierarchy, numbering consistency, TOC accuracy
4. **Readability**: Sentence complexity appropriate for audience
5. **Format check**: Output format renders correctly (no broken tables, images, links)

+++DETECT:
  D1: Missing Section — Outline section has no corresponding content
  D2: Tone Inconsistency — Tone shifts between sections
  D3: Phantom Citation — Reference to source not in scribe.md Sources
  D4: Orphan Content — Content not traceable to any outline item
  D5: Readability Mismatch — Complexity inappropriate for stated audience
  D6: Broken Formatting — Tables, images, or links render incorrectly
  D7: Stale Content — Document references outdated data or dates

### Phase 3: REPORT

+++STOP: always

Do NOT modify the document without approval.

+++Report:
| # | Section | Severity | Finding | Recommendation |
|---|---------|----------|---------|----------------|

Present overall quality score:
- **Structure**: {score}/5
- **Completeness**: {score}/5
- **Consistency**: {score}/5
- **Readability**: {score}/5
- **Overall**: {score}/5

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: REVISE

+++SWARM: 2+ approved revisions across sections

```
  team: reflect-revise
  spawn: editor-{section}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved revisions to section "{section}".
    Maintain consistency with surrounding sections.
    Report completed revisions to team-lead when done.
  collect: |
    Lead re-merges revised sections.
    Re-runs tone unification.
    Regenerates document furniture if needed.
    Converts to target format via pipeline.
```

After applying revisions:
1. Summarize what changed
2. Report new quality scores
3. If format conversion is needed, re-execute the format pipeline

### Phase 5: VERIFY

Re-scan the revised document:

1. Confirm all approved revisions were applied
2. Check that no new Detection Targets were introduced
3. Verify format output is correct
4. Suggest: "Run `/scribe:reflect` again for another pass, or finalize"

## Constraints

+++NEVER: Modify document without +++STOP approval
+++NEVER: Change document format without explicit request
+++NEVER: Skip holistic assessment — section reviews alone are insufficient
