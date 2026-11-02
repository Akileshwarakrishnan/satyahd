import re
from pathlib import Path

md_path = Path("SATYAHD_COMPLETE_SPECIFICATION.md")
content = md_path.read_text(encoding="utf-8")

# Convert basic markdown elements to HTML
html_body = []
lines = content.split("\n")
in_code = False
code_lang = ""
code_buf = []
in_mermaid = False
mermaid_buf = []
in_table = False
table_buf = []

for line in lines:
    if line.startswith("```mermaid"):
        in_mermaid = True
        mermaid_buf = []
        continue
    elif in_mermaid:
        if line.startswith("```"):
            in_mermaid = False
            html_body.append('<div class="mermaid">' + "\n".join(mermaid_buf) + '</div>')
            mermaid_buf = []
        else:
            mermaid_buf.append(line)
        continue

    if line.startswith("```"):
        if in_code:
            in_code = False
            html_body.append(f'<pre><code class="language-{code_lang}">' + "\n".join(code_buf) + '</code></pre>')
            code_buf = []
            code_lang = ""
        else:
            in_code = True
            code_lang = line[3:].strip()
            code_buf = []
        continue
    elif in_code:
        # Escape HTML chars in code
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        code_buf.append(escaped)
        continue

    # Tables
    if line.strip().startswith("|") and line.strip().endswith("|"):
        if not in_table:
            in_table = True
            table_buf = []
        table_buf.append(line)
        continue
    elif in_table:
        in_table = False
        # Render table
        if len(table_buf) >= 2:
            html_table = ['<div class="table-wrap"><table>']
            # Header
            headers = [c.strip() for c in table_buf[0].split("|")[1:-1]]
            html_table.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>")
            # Rows (skip separator at index 1)
            for row_line in table_buf[2:]:
                cells = [c.strip() for c in row_line.split("|")[1:-1]]
                html_table.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            html_table.append("</tbody></table></div>")
            html_body.append("\n".join(html_table))
        table_buf = []

    # Blockquotes / Alerts
    if line.startswith("> [!IMPORTANT]") or line.startswith("> [!NOTE]") or line.startswith("> [!WARNING]"):
        alert_type = "important" if "IMPORTANT" in line else ("warning" if "WARNING" in line else "note")
        html_body.append(f'<div class="callout callout-{alert_type}"><strong>{alert_type.upper()}:</strong> ')
        continue
    elif line.startswith("> "):
        clean_text = line[2:].strip()
        html_body.append(f'<div class="quote-box">{clean_text}</div>')
        continue

    # Headers
    if line.startswith("# "):
        html_body.append(f'<h1>{line[2:].strip()}</h1>')
    elif line.startswith("## "):
        html_body.append(f'<h2>{line[3:].strip()}</h2>')
    elif line.startswith("### "):
        html_body.append(f'<h3>{line[4:].strip()}</h3>')
    elif line.startswith("#### "):
        html_body.append(f'<h4>{line[5:].strip()}</h4>')
    elif line.startswith("---"):
        html_body.append('<hr/>')
    elif line.startswith("- "):
        html_body.append(f'<li>{line[2:].strip()}</li>')
    elif re.match(r"^\d+\.\s+", line):
        item_text = re.sub(r"^\d+\.\s+", "", line).strip()
        html_body.append(f'<li>{item_text}</li>')
    elif line.strip():
        # Bold and inline code replacements
        fmt = line
        fmt = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", fmt)
        fmt = re.sub(r"\*(.*?)\*", r"<em>\1</em>", fmt)
        fmt = re.sub(r"`([^`]+)`", r"<code>\1</code>", fmt)
        html_body.append(f'<p>{fmt}</p>')

# Wrap lists properly
parsed_lines = []
in_list = False
for item in html_body:
    if item.startswith("<li>"):
        if not in_list:
            parsed_lines.append("<ul>")
            in_list = True
        parsed_lines.append(item)
    else:
        if in_list:
            parsed_lines.append("</ul>")
            in_list = False
        parsed_lines.append(item)
if in_list:
    parsed_lines.append("</ul>")

full_body = "\n".join(parsed_lines)

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Satyahd — Complete System Specification</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
  </script>
  <style>
    :root {{
      --primary: #1e3a8a;
      --primary-hover: #1e40af;
      --bg: #f8fafc;
      --surface: #ffffff;
      --text: #0f172a;
      --text-muted: #475569;
      --border: #cbd5e1;
      --radius: 8px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      padding: 32px 16px;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
      padding: 48px;
    }}
    .actions-bar {{
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      background: var(--primary);
      color: #ffffff;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }}
    .btn:hover {{
      background: var(--primary-hover);
    }}
    .btn-secondary {{
      background: #475569;
    }}
    .btn-secondary:hover {{
      background: #334155;
    }}
    h1 {{
      font-size: 32px;
      font-weight: 700;
      color: var(--primary);
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 12px;
      margin-bottom: 8px;
    }}
    h2 {{
      font-size: 22px;
      font-weight: 600;
      color: #1e293b;
      margin-top: 36px;
      margin-bottom: 14px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 6px;
    }}
    h3 {{
      font-size: 18px;
      font-weight: 600;
      color: #334155;
      margin-top: 24px;
      margin-bottom: 10px;
    }}
    h4 {{
      font-size: 15px;
      font-weight: 600;
      color: #475569;
      margin-top: 16px;
      margin-bottom: 6px;
    }}
    p {{
      margin-bottom: 12px;
      font-size: 15px;
    }}
    hr {{
      border: 0;
      border-top: 1px solid var(--border);
      margin: 24px 0;
    }}
    ul, ol {{
      margin-left: 24px;
      margin-bottom: 14px;
    }}
    li {{
      margin-bottom: 6px;
    }}
    code {{
      background: #f1f5f9;
      color: #0f172a;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: ui-monospace, Menlo, Monaco, monospace;
      font-size: 13.5px;
      border: 1px solid #e2e8f0;
    }}
    pre {{
      background: #0f172a;
      color: #f8fafc;
      padding: 16px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 16px 0;
      font-family: ui-monospace, Menlo, Monaco, monospace;
      font-size: 13.5px;
      line-height: 1.5;
    }}
    pre code {{
      background: transparent;
      color: inherit;
      border: none;
      padding: 0;
    }}
    .quote-box {{
      background: #f8fafc;
      border-left: 4px solid var(--primary);
      padding: 12px 18px;
      margin: 14px 0;
      font-style: italic;
      color: #334155;
    }}
    .callout {{
      padding: 14px 18px;
      border-radius: 6px;
      margin: 16px 0;
      font-size: 14px;
    }}
    .callout-important {{
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1e40af;
    }}
    .table-wrap {{
      overflow-x: auto;
      margin: 18px 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 14px;
      border: 1px solid var(--border);
      text-align: left;
    }}
    th {{
      background: #f1f5f9;
      font-weight: 600;
      color: #1e293b;
    }}
    tr:nth-child(even) {{
      background: #f8fafc;
    }}
    .mermaid {{
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 20px;
      margin: 20px 0;
      text-align: center;
    }}
    @media print {{
      body {{
        background: #ffffff;
        padding: 0;
      }}
      .container {{
        border: none;
        box-shadow: none;
        padding: 0;
        max-width: 100%;
      }}
      .actions-bar {{
        display: none !important;
      }}
      a {{
        text-decoration: none;
        color: inherit;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="actions-bar">
      <button class="btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
      <a class="btn btn-secondary" href="/download/spec.md" download="SATYAHD_COMPLETE_SPECIFICATION.md">📥 Download Markdown (.md)</a>
    </div>
    {full_body}
  </div>
</body>
</html>
"""

Path("SATYAHD_COMPLETE_SPECIFICATION.html").write_text(full_html, encoding="utf-8")
Path("c:/Users/Akileshwarakrishnan/Downloads/SATYAHD_COMPLETE_SPECIFICATION.html").write_text(full_html, encoding="utf-8")
print("HTML generated successfully in project root and Downloads folder.")
