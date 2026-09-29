#!/usr/bin/env python3
"""md2pdf — render a Markdown file to a printable PDF using the local Chrome/Chromium in headless mode.

    python3 scripts/md2pdf.py input.md output.pdf [--title "Title"] [--html-only]

Standard library only. Handles headings, paragraphs, nested bullet/numbered lists, tables, block quotes, fenced
code, horizontal rules, bold/italic/code/links, and strips HTML comments. Everything stays on this machine.
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROMES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]

CSS = """
@page { size: letter; margin: 0.7in 0.7in 0.8in; }
body { font: 10.5pt/1.42 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; color: #111; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 8pt; line-height: 1.2; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; padding-bottom: 2pt; border-bottom: 1px solid #999; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10pt 0 3pt; page-break-after: avoid; }
p { margin: 4pt 0; orphans: 3; widows: 3; }
ul, ol { margin: 2pt 0 5pt 18pt; padding: 0; }
li { margin: 1.5pt 0; }
li > ul, li > ol { margin-top: 1pt; margin-bottom: 1pt; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 6pt 0 8pt; }
th, td { border: 1px solid #bbb; padding: 2.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #eee; font-weight: 600; }
tr { page-break-inside: avoid; }
blockquote { margin: 4pt 0 6pt 10pt; padding: 2pt 0 2pt 9pt; border-left: 3px solid #bbb; color: #333; }
code { font: 9pt Menlo, Consolas, monospace; background: #f1f1f1; padding: 0 2pt; border-radius: 2pt; }
pre { font: 8.5pt Menlo, Consolas, monospace; background: #f4f4f4; padding: 6pt 8pt; white-space: pre-wrap; }
hr { border: 0; border-top: 1px solid #bbb; margin: 12pt 0; }
strong { font-weight: 650; }
"""


def inline(text):
    """Escape HTML, then apply inline Markdown (code, bold, italics, links)."""
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\0{len(codes) - 1}\0"
    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"\0(\d+)\0", lambda m: codes[int(m.group(1))], text)
    return text


def join_wrapped_items(lines):
    """Fold indented continuation lines of a list item onto the item, so inline markup that wraps still matches."""
    out, in_code, in_item = [], False, False
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            out.append(ln)
            in_item = False
            continue
        if in_code:
            out.append(ln)
            continue
        is_item = bool(re.match(r"^\s*([-*+]|\d+[.)])\s+", ln))
        if in_item and ln.startswith((" ", "\t")) and s and not is_item and not s.startswith(("|", ">", "#")):
            out[-1] = out[-1] + " " + s
            continue
        out.append(ln)
        in_item = is_item or (in_item and bool(s))
        if not s:
            in_item = False
    return out


def md_to_html(md, title=""):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = join_wrapped_items(md.split("\n"))
    out = []
    i = 0
    list_stack = []  # (indent, tag)

    def close_lists(to_indent=-1):
        while list_stack and list_stack[-1][0] > to_indent:
            out.append(f"</li></{list_stack.pop()[1]}>")

    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        if not stripped:
            close_lists()
            i += 1
            continue
        if stripped.startswith("```"):
            close_lists()
            j = i + 1
            block = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                block.append(lines[j])
                j += 1
            out.append("<pre>" + html.escape("\n".join(block)) + "</pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            close_lists()
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("|"):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if len(rows) >= 2 and all(re.match(r"^:?-{2,}:?$", c) for c in rows[1] if c):
                head, body = rows[0], rows[2:]
            else:
                head, body = None, rows
            t = ["<table>"]
            if head:
                t.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>")
            for r in body:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</table>")
            out.append("".join(t))
            continue
        if stripped.startswith(">"):
            close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + "<br>".join(inline(q) for q in quote) + "</blockquote>")
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", ln)
        if m:
            indent = len(m.group(1).expandtabs(4))
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if list_stack and indent > list_stack[-1][0]:
                out.append(f"<{tag}><li>{inline(m.group(3))}")
                list_stack.append((indent, tag))
            else:
                close_lists(indent)
                if list_stack and list_stack[-1][0] == indent:
                    out.append(f"</li><li>{inline(m.group(3))}")
                else:
                    out.append(f"<{tag}><li>{inline(m.group(3))}")
                    list_stack.append((indent, tag))
            i += 1
            continue
        if list_stack and ln.startswith((" ", "\t")):
            out.append(" " + inline(stripped))  # continuation of the current list item
            i += 1
            continue
        close_lists()
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|\s*([-*+]|\d+[.)])\s|\||>|```|-{3,})", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")
    close_lists()
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style></head><body>{''.join(out)}</body></html>")


def render_pdf(html_path, pdf_path):
    """Prefer Playwright driving the installed Chrome (reliable); fall back to Chrome's own --print-to-pdf."""
    chrome = next((c for c in CHROMES if Path(c).exists()), None)
    if not chrome:
        sys.exit("No Chrome/Chromium/Brave/Edge found in /Applications")
    with tempfile.TemporaryDirectory() as profile:
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                            f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                            f"--print-to-pdf={pdf_path}", Path(html_path).resolve().as_uri()],
                           capture_output=True, text=True, timeout=90)
    if not Path(pdf_path).exists():
        sys.exit("Chrome did not produce the PDF:\n" + "\n".join(l for l in r.stderr.splitlines() if "ERROR" in l)[:2000])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else ""
    if len(args) < 2:
        sys.exit(__doc__)
    src, dest = Path(args[0]), Path(args[1])
    page = md_to_html(src.read_text(), title or src.stem)
    html_path = dest.with_suffix(".html")
    html_path.write_text(page)
    if "--html-only" in sys.argv:
        print(html_path)
        return
    render_pdf(html_path, dest)
    html_path.unlink()
    print(dest)


if __name__ == "__main__":
    main()
