# Format Pipelines

Detailed tool chain procedures for each output format. The lead agent selects the appropriate pipeline based on the `format` field in `scribe.md` or the file extension in the `/scribe:realize` argument.

Tool chains align with Anthropic official skills (`github.com/anthropics/skills`). If the official skill is installed, read and follow its SKILL.md. Otherwise, use the fallback procedures below.

---

## Official Skill Detection

Before running a format pipeline, check if the corresponding official skill is available:

```bash
# Check for official skills (installed via github.com/anthropics/skills)
for skill in pdf docx pptx xlsx; do
  if [ -f "$HOME/.claude/skills/$skill/SKILL.md" ] || \
     [ -f ".claude/skills/$skill/SKILL.md" ]; then
    echo "FOUND: $skill"
  else
    echo "NOT_FOUND: $skill (using fallback pipeline)"
  fi
done
```

If found: read the skill's SKILL.md and follow its procedures.
If not found: use the fallback procedures defined in this file.

---

## Markdown (.md)

**Pipeline**: Direct write
**Tools**: Write
**Official skill**: None needed

```
1. Write each section as markdown to the output file
2. No conversion step needed
```

---

## PDF (.pdf)

**Pipeline**: Python + reportlab
**Tools**: Bash (python3)
**Official skill**: `pdf` — uses reportlab, pypdf, pdfplumber

**Fallback procedure** (when `pdf` skill is not installed):

```python
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os, subprocess

doc = SimpleDocTemplate("{output_path}", pagesize=A4,
    topMargin=2.5*cm, bottomMargin=2.5*cm,
    leftMargin=2.5*cm, rightMargin=2.5*cm)
styles = getSampleStyleSheet()
story = []

# CJK font setup (when language is ja)
font_path = os.path.expanduser("~/.claude/fonts/NotoSansJP.ttf")
if not os.path.exists(font_path):
    os.makedirs(os.path.dirname(font_path), exist_ok=True)
    subprocess.run(["curl", "-fsSL", "-o", font_path,
        "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
    ], check=True, timeout=60)
pdfmetrics.registerFont(TTFont("NotoSansJP", font_path))
for s in ("Title", "Heading1", "Normal"):
    styles[s].fontName = "NotoSansJP"

# Title
story.append(Paragraph(document_title, styles['Title']))
story.append(Spacer(1, 12))

# Sections
for section in sections:
    story.append(Paragraph(section.heading, styles['Heading1']))
    story.append(Paragraph(section.content, styles['Normal']))
    story.append(Spacer(1, 12))

doc.build(story)
```

**Important**: Never use Unicode subscript/superscript characters in reportlab — use `<sub>` and `<super>` tags in Paragraph objects instead.

**For Japanese documents**: The CJK font block above downloads Noto Sans JP to `~/.claude/fonts/NotoSansJP.ttf` (cached across runs) and applies it to Title/Heading1/Normal styles. Include the CJK font block only when `{language}` starts with `ja`. For other CJK languages, adapt the font accordingly.

---

## Word (.docx)

**Pipeline**: JavaScript + docx-js (npm)
**Tools**: Bash (node)
**Official skill**: `docx` — uses docx-js for creation, XML unpack/pack for editing

**Fallback procedure** (when `docx` skill is not installed):

```bash
# Ensure docx-js is available
npm list -g docx 2>/dev/null || npm install -g docx
```

```javascript
const { Document, Packer, Paragraph, TextRun, HeadingLevel,
        AlignmentType, PageBreak } = require('docx');
const fs = require('fs');

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },  // US Letter in DXA
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // Title
      new Paragraph({ heading: HeadingLevel.HEADING_1,
        children: [new TextRun(document_title)] }),
      // Sections
      ...sections.map(s => [
        new Paragraph({ heading: HeadingLevel.HEADING_2,
          children: [new TextRun(s.heading)] }),
        new Paragraph({ children: [new TextRun(s.content)] }),
      ]).flat()
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("{output_path}", buffer);
});
```

**Critical rules**: Never use `\n` (use separate Paragraphs). Never use Unicode bullets (use `LevelFormat.BULLET`). Always set page size explicitly. Use `WidthType.DXA` for table widths (never PERCENTAGE).

---

## HTML (.html)

**Pipeline**: Python markdown or direct write
**Tools**: Write, Bash (python3)
**Official skill**: None

```python
import markdown

# Convert merged markdown to HTML
with open("_scribe_tmp/{document}.md") as f:
    md_content = f.read()

html_body = markdown.markdown(md_content, extensions=['tables', 'toc', 'fenced_code'])

html = f"""<!DOCTYPE html>
<html lang="{language}">
<head>
  <meta charset="UTF-8">
  <title>{document_title}</title>
  <style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

with open("{output_path}", "w") as f:
    f.write(html)
```

**Fallback**: If `markdown` module is not available, use pandoc if detected:
```bash
which pandoc && pandoc _scribe_tmp/{document}.md -o {output_path} --standalone --toc
```

---

## Excel (.xlsx)

**Pipeline**: Python + openpyxl
**Tools**: Bash (python3)
**Official skill**: `xlsx` — uses openpyxl, pandas

**Fallback procedure** (when `xlsx` skill is not installed):

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

wb = Workbook()

for section in sections:
    ws = wb.create_sheet(title=section.name)
    # Header row
    for col, header in enumerate(section.headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill('solid', fgColor='D5E8F0')
    # Data rows
    for row_idx, row_data in enumerate(section.data, 2):
        for col, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col, value=value)
    # Auto-width columns
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

# Remove default empty sheet
if "Sheet" in wb.sheetnames:
    del wb["Sheet"]

wb.save("{output_path}")
```

**Important**: Always use Excel formulas (`=SUM(...)`) instead of hardcoding calculated values. Use `recalc.py` from the official skill if available to recalculate formula values.

---

## PowerPoint (.pptx)

**Pipeline**: JavaScript + pptxgenjs (npm)
**Tools**: Bash (node)
**Official skill**: `pptx` — uses pptxgenjs for creation, XML unpack/pack for editing

**Fallback procedure** (when `pptx` skill is not installed):

```bash
# Ensure pptxgenjs is available
npm list -g pptxgenjs 2>/dev/null || npm install -g pptxgenjs
```

```javascript
const pptxgen = require('pptxgenjs');
const prs = new pptxgen();

// Title slide
let slide = prs.addSlide();
slide.addText(document_title, {
  x: 0.5, y: 1.5, w: 9, h: 2,
  fontSize: 36, bold: true, align: 'center'
});

// Content slides per section
for (const section of sections) {
  slide = prs.addSlide();
  slide.addText(section.heading, {
    x: 0.5, y: 0.3, w: 9, h: 0.8,
    fontSize: 28, bold: true
  });
  slide.addText(section.bullets.map(b => ({ text: b, options: { bullet: true } })), {
    x: 0.5, y: 1.3, w: 9, h: 5,
    fontSize: 16
  });
}

prs.writeFile({ fileName: "{output_path}" });
```

**Design tips**: Pick a bold color palette specific to the topic. Use varied layouts (two-column, icon+text rows, large stat callouts). Every slide needs a visual element — avoid text-only slides. See the official `pptx` skill for comprehensive design guidelines.

---

## Pencil Design (.pen)

**Pipeline**: Pencil MCP tools
**Tools**: MCP (pencil)

**Procedure**:
1. Call `open_document("new")` to create a new `.pen` file
2. Call `get_guidelines("landing-page")` or appropriate topic for design guidelines
3. Call `get_style_guide_tags` → `get_style_guide(tags)` for visual style
4. For each section, use `batch_design` to insert design nodes:
   - Text blocks for content
   - Layout containers for structure
   - Image nodes for visuals
5. Call `get_screenshot` to verify visual output
6. Save as `.pen` file

---

## Confluence (--confluence)

**Pipeline**: Atlassian MCP tools
**Tools**: MCP (Atlassian)

**Procedure**:
1. Write document content as Confluence-compatible HTML/wiki markup
2. Call `getConfluenceSpaces` to verify target space exists
3. Call `createConfluencePage` with:
   - `spaceId`: Target Confluence space
   - `title`: Document title from `scribe.md`
   - `body`: Converted content (Confluence storage format)
   - `parentId`: Optional parent page for hierarchy
4. For updates to existing pages: use `updateConfluencePage`
5. Report the page URL to the user

---

## Dependency Management

Before executing a pipeline, check required tools:

```bash
# Python libraries (pre-installed in Claude Cowork sandbox)
python3 -c "from reportlab.lib.pagesizes import A4" 2>/dev/null || echo "MISSING: reportlab — pip3 install reportlab"
python3 -c "import openpyxl" 2>/dev/null || echo "MISSING: openpyxl — pip3 install openpyxl"
python3 -c "import markdown" 2>/dev/null || echo "MISSING: markdown — pip3 install markdown"

# npm packages (for DOCX/PPTX)
npm list -g docx 2>/dev/null || echo "MISSING: docx — npm install -g docx"
npm list -g pptxgenjs 2>/dev/null || echo "MISSING: pptxgenjs — npm install -g pptxgenjs"

# Optional accelerator (not required)
which pandoc && echo "OPTIONAL: pandoc available" || echo "INFO: pandoc not found (not required)"
```

If a dependency is missing, inform the user with the install command and ask whether to install it automatically.

---

## Recommended: Install Official Skills

For the best document generation experience, install the official Anthropic skills:

```bash
# Clone the official skills repository
git clone https://github.com/anthropics/skills.git ~/.claude/skills-repo

# Symlink document skills
for skill in pdf docx pptx xlsx doc-coauthoring; do
  ln -sf ~/.claude/skills-repo/skills/$skill ~/.claude/skills/$skill
done
```

These skills provide comprehensive procedures, helper scripts, QA workflows, and design guidelines that far exceed the fallback pipelines above.
