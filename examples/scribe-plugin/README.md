# ✨ Scribe Plugin

> Document writing workflow for [Claude Code](https://code.claude.com/) and [Claude Cowork](https://claude.com/).

Draft outlines, write documents in parallel by section, output in any format.

## Installation

### Local Testing

```bash
claude --plugin-dir ./examples/scribe-plugin
```

### From Marketplace

```bash
claude plugin marketplace add SnowLightPath/snow-light-place
claude plugin install scribe@snow-light-place
```

### Project Setup

After installing, copy the CLAUDE.md template to your project:

```bash
cp examples/scribe-plugin/CLAUDE.md .claude/CLAUDE.md
```

Edit `.claude/CLAUDE.md` to set your project name and customize detection targets.

## The Loop

```
  /scribe:draft          Design the outline
       ↓
  scribe.md         ←→   Document structure
       ↓
  /scribe:realize        Write & export
       ↓
  report.pdf             Output file
       ↓
  /scribe:reflect        Review & improve
       ↓
  (iterate)
```

## Commands

| Command | Intent | Example |
|---------|--------|---------|
| `/scribe:draft` | Design document outline, audience, format | `/scribe:draft quarterly report` |
| `/scribe:realize` | Write and export the document | `/scribe:realize report.pdf` |
| `/scribe:reflect` | Review quality and improve | `/scribe:reflect report.pdf` |

## Supported Formats

| Format | Extension | Tool Chain |
|--------|-----------|------------|
| Markdown | `.md` | Direct write |
| PDF | `.pdf` | pandoc + xelatex |
| Word | `.docx` | pandoc |
| HTML | `.html` | pandoc |
| Excel | `.xlsx` | Python + openpyxl |
| PowerPoint | `.pptx` | Python + python-pptx |
| Pencil Design | `.pen` | Pencil MCP |
| Confluence | `--confluence` | Atlassian MCP |

## How It Works

### 1. Draft the outline

```bash
/scribe:draft
> "Write a quarterly report. Sales analysis, project progress, next steps."
```

Creates `scribe.md` — a document design file:

```markdown
# Q4 Quarterly Report

## Meta
- format: pdf
- audience: executive
- tone: formal
- language: ja

## Outline
### 1. Sales Analysis
### 2. Project Progress
### 3. Next Steps

## Sources
- data/sales_q4.csv
```

### 2. Write the document

```bash
/scribe:realize quarterly-report.pdf
```

Scribe reads `scribe.md` and writes sections **in parallel** using SWARM:

```
writer-1: §1 Sales Analysis    ─→ ┐
writer-2: §2 Project Progress  ─→ ├─→ Lead merges → pandoc → PDF
writer-3: §3 Next Steps        ─→ ┘
```

### 3. Review and improve

```bash
/scribe:reflect quarterly-report.pdf
```

Reviews quality, consistency, and completeness. Suggests improvements.

## Parallel Writing

Documents with 2+ sections are written in parallel. Each writer agent receives:
- The section outline
- Meta settings (tone, audience, language)
- Relevant source material
- Cross-reference context

The lead agent merges sections, unifies tone, resolves cross-references, and converts to the target format.

## Prerequisites

| Tool | Required For | Install |
|------|-------------|---------|
| pandoc | PDF, DOCX, HTML | `brew install pandoc` |
| xelatex | PDF output | `brew install --cask mactex` |
| openpyxl | XLSX output | `pip3 install openpyxl` |
| python-pptx | PPTX output | `pip3 install python-pptx` |
| Pencil MCP | .pen output | Configure in MCP settings |
| Atlassian MCP | Confluence | Configure in MCP settings |

Only install what you need. The plugin checks dependencies at runtime and prompts for missing tools.

## Philosophy

> Write the structure before the sentences. Divide to conquer. Merge to polish.
