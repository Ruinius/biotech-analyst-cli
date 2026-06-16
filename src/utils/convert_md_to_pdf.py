import os
import re
import typing
import pymupdf
from markdown_pdf import MarkdownPdf, Section

def markdown_table_to_html(markdown_table_text: str, table_class: str = "", col_widths: list = None) -> str:
    import math
    lines = [line.strip() for line in markdown_table_text.strip().split("\n")]
    if not lines or len(lines) < 2:
        return markdown_table_text
        
    # Extract header
    header_line = lines[0]
    headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
    
    # Extract body rows
    rows = []
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        rows.append(cells)
        
    num_cols = len(headers)
    
    # Generate dynamic column widths based on total content volume if not provided
    if not col_widths:
        col_max_lens = []
        for col_idx in range(num_cols):
            cell_texts = [headers[col_idx]]
            for row in rows:
                if col_idx < len(row):
                    cell_texts.append(row[col_idx])
            
            lens = []
            for t in cell_texts:
                # Clean HTML tags and markdown symbols for content volume estimation
                clean_t = re.sub(r'<[^>]+>', '', t)
                clean_t = re.sub(r'[\*_`\[\]\(\)]', '', clean_t)
                lens.append(len(clean_t.strip()))
            
            col_max_lens.append(max(lens) if lens else 1)
            
        # Scale with a higher power (0.8) to give dense text columns significantly more room
        weights = [math.pow(l, 0.8) for l in col_max_lens]
        
        total_w = sum(weights)
        if total_w > 0:
            percentages = [(w / total_w) * 100 for w in weights]
        else:
            percentages = [100.0 / num_cols] * num_cols
            
        # Enforce readable minimum widths:
        # - "phase" columns: minimum 6.0%
        # - all other columns: minimum 8.0%
        min_widths = [6.0 if "phase" in headers[i].lower() else 8.0 for i in range(num_cols)]
        
        # Iteratively distribute deficit
        for _ in range(5):
            deficit = 0.0
            excess = 0.0
            for i in range(num_cols):
                if percentages[i] < min_widths[i]:
                    deficit += min_widths[i] - percentages[i]
                    percentages[i] = min_widths[i]
                else:
                    excess += percentages[i] - min_widths[i]
            
            if deficit <= 0 or excess <= 0:
                break
                
            for i in range(num_cols):
                if percentages[i] > min_widths[i]:
                    proportion = (percentages[i] - min_widths[i]) / excess
                    percentages[i] -= deficit * proportion
                    
        col_widths = [f"{p:.1f}%" for p in percentages]
            
    # Build HTML table with fixed layout for exact column sizing
    html = []
    html.append(f'<table class="{table_class}" style="width: 100%; border-collapse: collapse; margin-top: 1em; margin-bottom: 1em; page-break-inside: avoid; table-layout: fixed;">')
    
    # Col widths using <colgroup> for semantic correctness
    if col_widths:
        html.append("  <colgroup>")
        for w in col_widths:
            html.append(f'    <col style="width: {w};" />')
        html.append("  </colgroup>")
        
    # Header row
    html.append("  <thead>")
    html.append('    <tr style="background-color: #f1f5f9; border-top: 1px solid #cbd5e1; border-bottom: 2px solid #cbd5e1;">')
    for idx, h in enumerate(headers):
        # Style cell formatting inside header
        formatted_h = h
        formatted_h = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted_h)
        formatted_h = re.sub(r'\*(.*?)\*', r'<em>\1</em>', formatted_h)
        formatted_h = re.sub(r'`(.*?)`', r'<code>\1</code>', formatted_h)
        formatted_h = formatted_h.replace("<br>", "<br/>")
        
        # Inject explicit width styles directly into <th> tags; use tight, professional padding
        width_style = f" width: {col_widths[idx]};" if col_widths and idx < len(col_widths) else ""
        html.append(f'      <th style="padding: 8px 10px; font-weight: 600; text-align: left; border-bottom: 2px solid #cbd5e1; color: #0f172a; font-size: 9.5pt;{width_style}">{formatted_h}</th>')
    html.append("    </tr>")
    html.append("  </thead>")
    
    # Body rows
    html.append("  <tbody>")
    for r_idx, row in enumerate(rows):
        bg_style = ' style="background-color: #f8fafc;"' if r_idx % 2 == 1 else ""
        html.append(f'    <tr{bg_style}>')
        for idx, cell in enumerate(row):
            # Convert markdown formatting inside cells to HTML formatting
            formatted_cell = cell
            formatted_cell = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted_cell)
            formatted_cell = re.sub(r'\*(.*?)\*', r'<em>\1</em>', formatted_cell)
            formatted_cell = re.sub(r'`(.*?)`', r'<code>\1</code>', formatted_cell)
            formatted_cell = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" style="color: #2563eb; text-decoration: none;">\1</a>', formatted_cell)
            formatted_cell = formatted_cell.replace("<br>", "<br/>")
            
            # Inject explicit width styles directly into <td> tags; use tight, professional padding and line-height
            width_style = f" width: {col_widths[idx]};" if col_widths and idx < len(col_widths) else ""
            html.append(f'      <td style="padding: 8px 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; color: #1f2937; font-size: 9pt; line-height: 1.45;{width_style}">{formatted_cell}</td>')
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    
    return "\n".join(html)

def replace_tables_with_html(text: str) -> str:
    # Match markdown tables (which begin with a header row, then divider row of hyphens, then multiple rows)
    # The regex checks for lines starting and ending with | and a separator line containing colons and hyphens
    pattern = re.compile(r'(^\|[^\n]+\|\r?\n^[ \t]*\|[ \t]*:?[-]+:?[ \t]*\|[ \t]*:?[-]+:?[ \t]*\|[^\n]*\r?\n(?:^\|[^\n]+\|\r?\n?)+)', re.MULTILINE)
    
    matches = pattern.findall(text)
    print(f"Found {len(matches)} markdown tables to convert.")
    
    table_index = 0
    for match in matches:
        # Determine table configuration based on contents
        if "Primary Target" in match:
            table_class = "portfolio-matrix"
        elif "Endpoint" in match:
            table_class = "efficacy-matrix"
        elif "Pipeline Load" in match:
            table_class = "crowding-matrix"
        else:
            table_class = f"custom-table-{table_index}"
            
        # Leverage our newly written robust dynamic width calculator by setting col_widths=None
        html_table = markdown_table_to_html(match, table_class, col_widths=None)
        text = text.replace(match, html_table)
        table_index += 1
        
    return text

def clean_markdown_math(text: str) -> str:
    # A dictionary of exact mapping replacements for math and symbols
    math_replacements = {
        # Scientific representations
        r"$^{177}\text{Lu}$/$^{111}\text{In}$": "<sup>177</sup>Lu/<sup>111</sup>In",
        r"$^{111}\text{In}$ / $^{177}\text{Lu}$": "<sup>111</sup>In / <sup>177</sup>Lu",
        r"$^{111}\text{In}$": "<sup>111</sup>In",
        r"$^{177}\text{Lu}$": "<sup>177</sup>Lu",
        r"$^{177}\text{Lu}$-F(ab')₂": "<sup>177</sup>Lu-F(ab')<sub>2</sub>",
        r"F(ab')₂": "F(ab')<sub>2</sub>",
        r"$\ge 75\%$": "&ge; 75%",
        r"$\ge 40\%$": "&ge; 40%",
        r"$\ge 2+$": "&ge; 2+",
        r"$\ge 1$": "&ge; 1",
        r"$\ge": "&ge;",
        r"$\le": "&le;",
        r"CD133⁺": "CD133<sup>+</sup>",
        r"CD133+": "CD133<sup>+</sup>",
        r"CD33⁺": "CD33<sup>+</sup>",
        r"CD33+": "CD33<sup>+</sup>",
        r"($N = 9$)": "(<i>N</i> = 9)",
        r"($N = 66$)": "(<i>N</i> = 66)",
        r"($N = 507$)": "(<i>N</i> = 507)",
        r"($N = 1,581$)": "(<i>N</i> = 1,581)",
        r"($N = 84$)": "(<i>N</i> = 84)",
        r"($N$)": "(<i>N</i>)",
        r"($CI$)": "(<i>CI</i>)",
        r"($K_D = 0.398 \text{ pM}$)": "(<i>K</i><sub>d</sub> = 0.398 pM)",
        r"($K_D = 0.398 \text{ \text{pM}}$)": "(<i>K</i><sub>d</sub> = 0.398 pM)",
        r"($K_D = 0.398 \text{pM}$)": "(<i>K</i><sub>d</sub> = 0.398 pM)",
        r"($>2,500\text{ mm}^3$)": "(&gt;2,500 mm<sup>3</sup>)",
        r"$>2,500\text{ mm}^3$": "&gt;2,500 mm<sup>3</sup>",
        r"$>1,300\text{ mm}^3$": "&gt;1,300 mm<sup>3</sup>",
        r"U937 MFI $>1,000$": "U937 MFI &gt;1,000",
        r"THP-1 MFI ~800": "THP-1 MFI &sim;800",
        r"U937 MFI $>1,000$ vs. ~300": "U937 MFI &gt;1,000 vs. &sim;300",
        r"~1,000 vs. ~300": "&sim;1,000 vs. &sim;300",
        r"~800 vs. ~325": "&sim;800 vs. &sim;325",
        r"~60,000 vs. ~38,000": "&sim;60,000 vs. &sim;38,000",
        r"~40% to approximately 60%": "&sim;40% to &sim;60%",
        r"~38,000": "&sim;38,000",
        r"~60,000": "&sim;60,000",
        r"~40%": "&sim;40%",
        r"~300": "&sim;300",
        r"~325": "&sim;325",
        r"~800": "&sim;800",
    }
    
    for math_str, clean_str in math_replacements.items():
        text = text.replace(math_str, clean_str)
        
    # Also clean standard dollar-wrapped terms that might be left
    text = text.replace("$N$", "<i>N</i>")
    text = text.replace("$CI$", "<i>CI</i>")
    text = text.replace("$N = 66$", "<i>N</i> = 66")
    text = text.replace("$N = 507$", "<i>N</i> = 507")
    text = text.replace("$N = 1,581$", "<i>N</i> = 1,581")
    text = text.replace("$N = 9$", "<i>N</i> = 9")
    text = text.replace("$N = 84$", "<i>N</i> = 84")
    text = text.replace("K_D = 0.398 \\text{ pM}", "<i>K</i><sub>d</sub> = 0.398 pM")
    text = text.replace("K_D = 0.398 \\text{ \\text{pM}}", "<i>K</i><sub>d</sub> = 0.398 pM")
    text = text.replace("K_D = 0.398 \\text{\\text{pM}}", "<i>K</i><sub>d</sub> = 0.398 pM")
    
    return text

def add_header_footer_to_pdf(pdf_path: str, header_left: str = None, footer_left: str = None):
    print("Post-processing PDF to add headers, footers and page numbers...")
    if not header_left:
        header_left = "Biotech BD Pipeline Summary: Clinical & Preclinical Asset Landscape"
    if not footer_left:
        footer_left = "Date of Report: May 29, 2026"
        
    doc = pymupdf.open(pdf_path)
    page_count = doc.page_count
    
    for page in doc:
        rect = page.rect
        w = rect.width
        h = rect.height
        
        # Check if the page is landscape
        is_landscape = w > h
        
        if is_landscape:
            margin_left = 36
            margin_right = w - 36
            header_y = 22
            header_line_y = 29
            footer_line_y = h - 29
            footer_y = h - 20
        else:
            margin_left = 54
            margin_right = w - 54
            header_y = 32
            header_line_y = 39
            footer_line_y = h - 39
            footer_y = h - 27
            
        # 1. Draw Header (Skip on Page 1)
        if page.number > 0:
            header_right = "Confidential BD Briefing"
            
            # Left-aligned header text
            page.insert_text((margin_left, header_y), header_left, fontsize=8, color=(0.4, 0.4, 0.4))
            
            # Right-aligned header text using insert_textbox
            page.insert_textbox(
                pymupdf.Rect(margin_right - 250, header_y - 8, margin_right, header_y + 12),
                header_right,
                fontsize=8,
                color=(0.4, 0.4, 0.4),
                align=2 # Right aligned
            )
            
            # Draw header horizontal line
            page.draw_line(
                pymupdf.Point(margin_left, header_line_y),
                pymupdf.Point(margin_right, header_line_y),
                color=(0.85, 0.85, 0.85),
                width=0.5
            )
            
        # 2. Draw Footer (All pages)
        footer_right = f"Page {page.number + 1} of {page_count}"
        
        # Left-aligned footer text
        page.insert_text((margin_left, footer_y), footer_left, fontsize=8, color=(0.4, 0.4, 0.4))
        
        # Right-aligned footer text
        page.insert_textbox(
            pymupdf.Rect(margin_right - 100, footer_y - 8, margin_right, footer_y + 12),
            footer_right,
            fontsize=8,
            color=(0.4, 0.4, 0.4),
            align=2 # Right aligned
        )
        
        # Draw footer horizontal line
        page.draw_line(
            pymupdf.Point(margin_left, footer_line_y),
            pymupdf.Point(margin_right, footer_line_y),
            color=(0.85, 0.85, 0.85),
            width=0.5
        )
        
    temp_path = pdf_path + ".tmp"
    doc.save(temp_path, incremental=False, encryption=False)
    doc.close()
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass
    os.rename(temp_path, pdf_path)
    print("Post-processing complete!")

def parse_github_alerts(text: str) -> str:
    alert_types = ["NOTE", "IMPORTANT", "WARNING", "TIP"]
    for alert_type in alert_types:
        pattern = re.compile(
            r'^>[ \t]*\[!' + alert_type + r'\][ \t]*\r?\n((?:^>[^\n]*\r?\n?)+)', 
            re.MULTILINE | re.IGNORECASE
        )
        
        def replace_alert(match):
            content_lines = []
            for line in match.group(1).split('\n'):
                line_stripped = line.strip()
                if line_stripped.startswith('>'):
                    content_lines.append(line_stripped[1:].strip())
                else:
                    content_lines.append(line_stripped)
            content = " ".join(content_lines).strip()
            
            # Format inline markdown in content
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
            content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)
            
            return f'<div class="alert {alert_type.lower()}"><strong>{alert_type} &bull;</strong> {content}</div>\n'
            
        text = pattern.sub(replace_alert, text)
    return text

def convert_generic(md_path: str, pdf_path: str):
    print(f"Generic compilation: {md_path} -> {pdf_path}")
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    # Preprocess generic markdown content
    md_content = parse_github_alerts(md_content)
    md_content = clean_markdown_math(md_content)
    md_content = replace_tables_with_html(md_content)
    
    # Extract Title and Date for headers & footers
    header_title = None
    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    if title_match:
        header_title = title_match.group(1).strip()
    else:
        header_title = "Biotech BD Due Diligence Briefing"
        
    report_date = None
    date_match = re.search(r"(?:Date of Report|Date):\s*\*\*?([^\*\n\r]+)\*\*?", md_content, re.IGNORECASE)
    if date_match:
        report_date = f"Date of Report: {date_match.group(1).strip()}"
    else:
        report_date = "Date of Report: June 2, 2026"
        
    pdf = MarkdownPdf(toc_level=2)
    
    css = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1f2937;
  line-height: 1.5;
  font-size: 10pt;
  margin: 0;
  padding: 0;
}

h1, h2, h3, h4, h5, h6 {
  color: #0f172a;
  font-weight: 700;
  margin-top: 1.4em;
  margin-bottom: 0.4em;
  line-height: 1.25;
}

h1 {
  font-size: 18pt;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 6px;
  margin-top: 0;
}

h2 {
  font-size: 13pt;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 5px;
}

h3 {
  font-size: 11pt;
  color: #1e3a8a; /* deep Navy */
}

h4 {
  font-size: 10pt;
  color: #1f2937;
}

a {
  color: #2563eb;
  text-decoration: none;
}

ul, ol {
  margin-top: 0.4em;
  margin-bottom: 0.4em;
  padding-left: 20px;
}

li {
  margin-bottom: 0.2em;
}

strong {
  color: #0f172a;
}

/* Alert block styling */
.alert {
  padding: 12px 16px;
  margin: 1.2em 0;
  border-radius: 6px;
  font-size: 9pt;
  page-break-inside: avoid;
}

.alert.note {
  background-color: #eff6ff;
  border-left: 4px solid #3b82f6;
  color: #1e3a8a;
  line-height: 1.4;
}

.alert.important {
  background-color: #fef2f2;
  border-left: 4px solid #ef4444;
  color: #991b1b;
  line-height: 1.4;
}

.alert.warning {
  background-color: #fffbef;
  border-left: 4px solid #f59e0b;
  color: #78350f;
  line-height: 1.4;
}

.alert.tip {
  background-color: #f0fdf4;
  border-left: 4px solid #10b981;
  color: #065f46;
  line-height: 1.4;
}

code {
  font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 8.5pt;
  background-color: #f1f5f9;
  padding: 2px 4px;
  border-radius: 4px;
  color: #0f172a;
}
"""
    pdf.add_section(Section(md_content, paper_size="A4-L", borders=(36, 36, -36, -36)), user_css=css)
    pdf.save(pdf_path)
    
    # Post-process to add headers, footers and page numbers
    add_header_footer_to_pdf(pdf_path, header_left=header_title, footer_left=report_date)
    print("Generic PDF compilation complete (landscape A4-L)!")


def run():
    md_path = r"f:\AI-native-biotech\asset-pipeline-research\input\20260529_pipeline\20260529_pipeline_summary.md"
    pdf_path = r"f:\AI-native-biotech\asset-pipeline-research\input\20260529_pipeline\20260529_pipeline_summary.pdf"
    
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    # Preprocess markdown content
    
    # 1. Replace the [!NOTE] blockquote with beautifully styled HTML callout block
    blockquote_note_regex = re.compile(
        r'> \[!NOTE\]\r?\n>[ \t]*\*Cross-Trial Caveat\*: ([^\n]+(?:\r?\n>[^\n]+)*)', 
        re.MULTILINE
    )
    note_match = blockquote_note_regex.search(md_content)
    if note_match:
        caveat_text = note_match.group(1).replace("\n>", "").replace("\r>", "").strip()
        # Clean formatting in caveat text
        caveat_text = caveat_text.replace("Osemitamab phase 2 data is compiled up to April 14, 2025, from Gong et al., ASCO 2025 (Abstract 4032). Zolbetuximab benchmark data is from Shah et al., *Nature Medicine*, 2023. Nivolumab benchmark data is from Janjigian et al., *The Lancet*, 2021. Direct statistical comparisons across these trials must be made with caution.",
                                           "Osemitamab phase 2 data is compiled up to April 14, 2025, from Gong et al., ASCO 2025 (Abstract 4032). Zolbetuximab benchmark data is from Shah et al., <em>Nature Medicine</em>, 2023. Nivolumab benchmark data is from Janjigian et al., <em>The Lancet</em>, 2021. Direct statistical comparisons across these trials must be made with caution.")
        
        html_callout = f'<div class="alert note"><strong>NOTE &bull; Cross-Trial Caveat:</strong> {caveat_text}</div>'
        md_content = md_content.replace(note_match.group(0), html_callout)
        print("Replaced [!NOTE] blockquote with custom HTML callout.")
        
    # 2. Replace the mermaid block with our custom beautiful HTML grid table
    mermaid_regex = re.compile(r'```mermaid.*?```', re.DOTALL)
    mermaid_html = """
<table class="mermaid-replacement-table">
  <tr>
    <td class="mermaid-col lead-col">
      <div class="mermaid-header lead-header">Lead Biotech Programs</div>
      <div class="mermaid-card lead-card">
        <div class="card-title">Osemitamab (TST-001)</div>
        <div class="card-desc">Phase 3 &bull; Anti-CLDN18.2 IV/SubQ</div>
      </div>
      <div class="mermaid-card lead-card">
        <div class="card-title">TRK-950 Platform</div>
        <div class="card-desc">Phase II &bull; Anti-CAPRIN-1 mAb/ADC/RI-ADC</div>
      </div>
      <div class="mermaid-card lead-card">
        <div class="card-title">STF32 ADC</div>
        <div class="card-desc">Preclinical &bull; Myeloid Malignancies (AML/CMML)</div>
      </div>
    </td>
    <td class="mermaid-col bd-col">
      <div class="mermaid-header bd-header">Validated Low-Competition Targets</div>
      <div class="mermaid-card bd-card">
        <div class="card-title">NaPi2b ADCs</div>
        <div class="card-desc">TUB-040 (Gilead / Tubulis)</div>
      </div>
      <div class="mermaid-card bd-card">
        <div class="card-title">Integrin &alpha;v&beta;6 ADCs</div>
        <div class="card-desc">Sigvotatug vedotin (Pfizer)</div>
      </div>
      <div class="mermaid-card bd-card">
        <div class="card-title">N-Glyco CEACAM5/6</div>
        <div class="card-desc">EBC-129 Precision ADC</div>
      </div>
      <div class="mermaid-card bd-card">
        <div class="card-title">5T4 ADCs</div>
        <div class="card-desc">TUB-030 & JK06</div>
      </div>
    </td>
    <td class="mermaid-col modalities-col">
      <div class="mermaid-header modalities-header">Emerging Modality Platforms</div>
      <div class="mermaid-card modalities-card">
        <div class="card-title">Degrader-Antibody Conjugates</div>
        <div class="card-desc">BMS-986497 (GSPT1 DAC)</div>
      </div>
      <div class="mermaid-card modalities-card">
        <div class="card-title">Dual-Payload ADCs</div>
        <div class="card-desc">Sutro Biopharma</div>
      </div>
      <div class="mermaid-card modalities-card">
        <div class="card-title">Immune-Stimulating Conjugates</div>
        <div class="card-desc">Preclinical Platforms</div>
      </div>
    </td>
  </tr>
</table>
"""
    md_content = mermaid_regex.sub(mermaid_html, md_content)
    print("Replaced Mermaid block with beautifully formatted HTML Table.")

    # 3. Clean scientific math symbols and notations
    md_content = clean_markdown_math(md_content)
    print("Cleaned scientific notations and math symbols.")

    # 4. Convert all markdown tables to clean HTML tables with inline column widths and styling
    md_content = replace_tables_with_html(md_content)
    print("Converted all markdown tables to clean HTML tables with layout widths.")

    # 5. Split content into three sections:
    # Section 1: Title and Executive Portfolio Overview (Portrait)
    # Section 2: Master Portfolio & Asset Landscape Matrix (Landscape)
    # Section 3: Deep Dives and everything else (Portrait)
    
    parts = md_content.split("## 2. Master Portfolio & Asset Landscape Matrix")
    part_1 = parts[0]
    
    rest = parts[1]
    parts_2 = rest.split("## 3. Deep-Dive Evaluations of Core Portfolio Assets")
    part_2 = "## 2. Master Portfolio & Asset Landscape Matrix" + parts_2[0]
    
    # Split Section 3 into separate subsections to isolate page-rendering contexts and
    # bypass the MuPDF Bug 707324 (which duplicates table/alert backgrounds across page flows).
    part_3_header = "## 3. Deep-Dive Evaluations of Core Portfolio Assets\n\n"
    part_3_body = parts_2[1]
    
    # Split by headings
    split_3b = part_3_body.split("### 3.2 TRK-950 Platform")
    part_3a = part_3_header + split_3b[0].strip()
    
    split_3c = split_3b[1].split("### 3.3 STF32 ADC")
    part_3b = "### 3.2 TRK-950 Platform" + split_3c[0]
    
    split_3d = split_3c[1].split("## 4. Validated Low-Competition In-Licensing Targets")
    part_3c = "### 3.3 STF32 ADC" + split_3d[0]
    part_3d = "## 4. Validated Low-Competition In-Licensing Targets" + split_3d[1]

    # Save components to verify splitting
    print("Splitting markdown into: Section 1 (Portrait), Section 2 (Landscape), Section 3 (Portrait)")
    
    pdf = MarkdownPdf(toc_level=2)
    
    # Custom Premium CSS to override styling
    css = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1f2937;
  line-height: 1.5;
  font-size: 10pt;
  margin: 0;
  padding: 0;
}

h1, h2, h3, h4, h5, h6 {
  color: #0f172a;
  font-weight: 700;
  margin-top: 1.4em;
  margin-bottom: 0.4em;
  line-height: 1.25;
}

h1 {
  font-size: 18pt;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 6px;
  margin-top: 0;
}

h2 {
  font-size: 13pt;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 5px;
}

h3 {
  font-size: 11pt;
  color: #1e3a8a; /* deep Navy */
}

h4 {
  font-size: 10pt;
  color: #1f2937;
}

a {
  color: #2563eb;
  text-decoration: none;
}

ul, ol {
  margin-top: 0.4em;
  margin-bottom: 0.4em;
  padding-left: 20px;
}

li {
  margin-bottom: 0.2em;
}

strong {
  color: #0f172a;
}

/* Mermaid replacement table layout */
.mermaid-replacement-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 12px;
  margin: 1.2em 0;
  page-break-inside: avoid;
}

.mermaid-replacement-table td {
  border: none !important;
  padding: 0 !important;
  vertical-align: top;
  width: 33.33%;
  background-color: transparent !important;
}

.mermaid-col {
  background-color: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 8px !important;
  padding: 12px !important;
}

.mermaid-header {
  font-weight: 700;
  font-size: 9.5pt;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 2px solid #e2e8f0;
}

.lead-header {
  color: #1e40af;
  border-bottom-color: #bfdbfe;
}

.bd-header {
  color: #065f46;
  border-bottom-color: #a7f3d0;
}

.modalities-header {
  color: #6b21a8;
  border-bottom-color: #e9d5ff;
}

.mermaid-card {
  background-color: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 6px !important;
  padding: 10px !important;
  margin-bottom: 10px !important;
}

.lead-card {
  border-left: 4px solid #3b82f6 !important;
}

.bd-card {
  border-left: 4px solid #10b981 !important;
}

.modalities-card {
  border-left: 4px solid #8b5cf6 !important;
}

.card-title {
  font-weight: 700;
  font-size: 9pt;
  color: #0f172a;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 8pt;
  color: #4b5563;
}

/* Alert block styling */
.alert {
  padding: 12px 16px;
  margin: 1.2em 0;
  border-radius: 6px;
  font-size: 9pt;
  page-break-inside: avoid;
}

.alert.note {
  background-color: #eff6ff;
  border-left: 4px solid #3b82f6;
  color: #1e3a8a;
  line-height: 1.4;
}

code {
  font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 8.5pt;
  background-color: #f1f5f9;
  padding: 2px 4px;
  border-radius: 4px;
  color: #0f172a;
}
"""

    # Section 1: Portrait with elegant 0.75in margins (54pt)
    pdf.add_section(Section(part_1, paper_size="A4", borders=(54, 54, -54, -54)), user_css=css)
    
    # Section 2: Landscape with narrower 0.5in margins (36pt) to give table maximum width
    pdf.add_section(Section(part_2, paper_size="A4-L", borders=(36, 36, -36, -36)), user_css=css)
    
    # Section 3a: Osemitamab Deep-Dive (Portrait)
    pdf.add_section(Section(part_3a, paper_size="A4", borders=(54, 54, -54, -54)), user_css=css)
    
    # Section 3b: TRK-950 Deep-Dive (Portrait)
    pdf.add_section(Section(part_3b, paper_size="A4", borders=(54, 54, -54, -54)), user_css=css)
    
    # Section 3c: STF32 Deep-Dive (Portrait)
    pdf.add_section(Section(part_3c, paper_size="A4", borders=(54, 54, -54, -54)), user_css=css)
    
    # Section 3d: Remainder of Deep Dives and Reference Matrix (Portrait)
    pdf.add_section(Section(part_3d, paper_size="A4", borders=(54, 54, -54, -54)), user_css=css)
    
    # Save the initial PDF
    pdf.save(pdf_path)
    print(f"Initial PDF compiled at: {pdf_path}")
    
    # Post-process to add headers, footers and page numbers
    add_header_footer_to_pdf(pdf_path)
    print("Process successfully finished!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert Markdown to PDF (with special styling and headers/footers)")
    parser.add_argument("--input", help="Path to input Markdown file")
    parser.add_argument("--output", help="Path to output PDF file")
    args = parser.parse_args()
    
    if args.input and args.output:
        convert_generic(args.input, args.output)
    else:
        run()
