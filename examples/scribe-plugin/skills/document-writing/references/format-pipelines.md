# Format Pipelines

Detailed tool chain procedures for each output format. The lead agent selects the appropriate pipeline based on the `format` field in `scribe.md` or the file extension in the `/scribe:realize` argument.

---

## Markdown (.md)

**Pipeline**: Direct write
**Tools**: Write

```
1. Write each section as markdown to the output file
2. No conversion step needed
```

---

## PDF (.pdf)

**Pipeline**: MD → pandoc → PDF
**Tools**: Write, Bash

**Prerequisites**: `pandoc` must be installed. For PDF output, pandoc requires a PDF engine (pdflatex, xelatex, or wkhtmltopdf).

```bash
# Step 1: Write merged markdown to temporary file
# → _scribe_tmp/{document-name}.md

# Step 2: Convert with pandoc
pandoc _scribe_tmp/{document-name}.md \
  -o {output-name}.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  -V mainfont="Hiragino Sans" \
  --toc \
  --number-sections

# Step 3: Clean up temporary files
rm -rf _scribe_tmp/
```

**Fallback if no PDF engine**: Generate HTML instead and inform user:
```bash
pandoc _scribe_tmp/{document-name}.md -o {output-name}.html --standalone --toc
```

**For Japanese documents**: Use `--pdf-engine=xelatex` with `-V CJKmainfont` for CJK font support.

---

## Word (.docx)

**Pipeline**: MD → pandoc → DOCX
**Tools**: Write, Bash

```bash
pandoc _scribe_tmp/{document-name}.md \
  -o {output-name}.docx \
  --toc \
  --number-sections \
  --reference-doc={template}.docx  # optional: custom template
```

**With custom styling**: If a `.docx` reference template exists in the project, use `--reference-doc` to apply corporate styles.

---

## HTML (.html)

**Pipeline**: MD → pandoc → HTML
**Tools**: Write, Bash

```bash
pandoc _scribe_tmp/{document-name}.md \
  -o {output-name}.html \
  --standalone \
  --toc \
  --number-sections \
  --css={stylesheet}.css  # optional
```

---

## Excel (.xlsx)

**Pipeline**: Python + openpyxl
**Tools**: Bash (python3)

**Prerequisites**: `openpyxl` must be installed. If not, install at runtime:
```bash
pip3 install openpyxl --quiet
```

**Generation approach**:
1. Parse `scribe.md` outline — each section becomes a worksheet or a section within a worksheet
2. Read source data files (CSV, existing XLSX) referenced in `## Sources`
3. Generate the workbook using openpyxl:
   - Create worksheets per section
   - Insert data tables with headers
   - Apply basic formatting (bold headers, auto-width columns)
   - Add charts if data supports visualization (matplotlib → image → embed)

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

wb = Workbook()
# Create worksheet per section
for section in sections:
    ws = wb.create_sheet(title=section.name)
    # Write header row
    for col, header in enumerate(section.headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
    # Write data rows
    for row_idx, row_data in enumerate(section.data, 2):
        for col, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col, value=value)

wb.save(output_path)
```

---

## PowerPoint (.pptx)

**Pipeline**: Python + python-pptx
**Tools**: Bash (python3)

**Prerequisites**: `python-pptx` must be installed. If not:
```bash
pip3 install python-pptx --quiet
```

**Generation approach**:
1. Each section in `scribe.md` outline becomes a slide or slide group
2. Subsections become bullet points or additional slides
3. Data visualizations from sources become embedded images

```python
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()

# Title slide
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = document_title
slide.placeholders[1].text = subtitle

# Content slides per section
for section in sections:
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = section.name
    body = slide.placeholders[1]
    for point in section.bullet_points:
        body.text_frame.add_paragraph().text = point

prs.save(output_path)
```

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

Before executing a pipeline, check if required tools are available:

```bash
# Check pandoc
which pandoc || echo "MISSING: pandoc — install via brew install pandoc"

# Check PDF engine (for PDF output)
which xelatex || which pdflatex || which wkhtmltopdf || echo "MISSING: PDF engine"

# Check Python libraries (for XLSX/PPTX)
python3 -c "import openpyxl" 2>/dev/null || echo "MISSING: openpyxl — pip3 install openpyxl"
python3 -c "from pptx import Presentation" 2>/dev/null || echo "MISSING: python-pptx — pip3 install python-pptx"
```

If a dependency is missing, inform the user with the install command and ask whether to install it automatically.
