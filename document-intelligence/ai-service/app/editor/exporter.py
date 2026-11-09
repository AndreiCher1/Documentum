"""
Экспорт HTML из редактора Documentum в DOCX.

Понимает тот же набор тегов, что выдаёт converter.py: h1–h3, p, ul/ol/li,
table/tr/td/th, b/strong, i/em, u, s/strike/del, br, span. Пометки правок
(del/ins внутри .sug) к этому моменту уже разрешены на стороне интерфейса.
Оформление: Times New Roman 12 pt, поля 3/1,5/2/2 см, абзацный отступ 1,25 см.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import List, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
HEADING_SIZE = {"h1": 14, "h2": 12, "h3": 12}
INLINE = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline",
          "s": "strike", "strike": "strike", "del": "strike"}


class _Builder(HTMLParser):
    def __init__(self, doc):
        super().__init__(convert_charrefs=True)
        self.doc = doc
        self.para = None              # текущий абзац python-docx
        self.block = None             # тег текущего блока
        self.fmt: List[str] = []      # стек начертаний
        self.lists: List[str] = []    # стек ul/ol
        self.table = None
        self.row_cells: List = []
        self.cell_idx = 0
        self.cell = None
        self.skip = 0                 # глубина тегов, которые не выводим

    # --- блоки ---
    def _new_para(self, tag: str, attrs: dict):
        container = self.cell if self.cell is not None else self.doc
        if self.cell is not None and not self.cell_used:
            self.para = self.cell.paragraphs[0]
            self.cell_used = True
        else:
            self.para = container.add_paragraph()
        self.block = tag
        pf = self.para.paragraph_format
        pf.space_after = Pt(0 if self.cell is not None else 3)
        align = _style_align(attrs)
        if tag in HEADING_SIZE:
            pf.alignment = ALIGN.get(align or "center")
            pf.space_before = Pt(10)
            pf.space_after = Pt(4)
            pf.keep_with_next = True
        elif tag == "li":
            pf.left_indent = Cm(1.0 + 0.6 * (len(self.lists) - 1))
            pf.first_line_indent = Cm(-0.5)
            pf.alignment = ALIGN.get(align or "justify")
            kind = self.lists[-1] if self.lists else "ul"
            if kind == "ol":
                self.list_counters[-1] += 1
                self._run(f"{self.list_counters[-1]}. ")
            else:
                self._run("• ")
        elif self.cell is not None:
            pf.alignment = ALIGN.get(align or "left")
        else:
            pf.alignment = ALIGN.get(align or "justify")
            pf.first_line_indent = Cm(1.25)

    def _run(self, text: str):
        if self.para is None:
            self._new_para("p", {})
        run = self.para.add_run(text)
        flags = set(self.fmt)
        if self.block in HEADING_SIZE:
            flags.add("bold")
            run.font.size = Pt(HEADING_SIZE[self.block])
        run.bold = "bold" in flags or None
        run.italic = "italic" in flags or None
        run.underline = "underline" in flags or None
        run.font.strike = "strike" in flags or None
        return run

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        if self.skip or tag in ("script", "style"):
            self.skip += 1
            return
        if self.collect is not None and tag in ("p", "h1", "h2", "h3", "li", "div"):
            if self.collect:
                self.collect.append(("br", None))   # абзац внутри ячейки — перенос строки
            return
        if tag in ("p", "h1", "h2", "h3", "li"):
            self._new_para(tag, attrs)
        elif tag in ("ul", "ol"):
            self.lists.append(tag)
            self.list_counters.append(0)
        elif tag == "table":
            self.table_rows = []
        elif tag == "tr":
            self.table_rows.append([])
        elif tag in ("td", "th"):
            self.table_rows[-1].append({"html": [], "colspan": int(attrs.get("colspan", 1) or 1), "th": tag == "th"})
            self.collect = self.table_rows[-1][-1]["html"]
        elif tag == "br":
            if self.collect is not None:
                self.collect.append(("br", None))
            elif self.para is not None:
                self.para.add_run().add_break()
        elif tag in INLINE:
            if self.collect is not None:
                self.collect.append(("start", INLINE[tag]))
            else:
                self.fmt.append(INLINE[tag])

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
            return
        if self.collect is not None and tag in ("p", "h1", "h2", "h3", "li", "div"):
            return
        if tag in ("p", "h1", "h2", "h3", "li"):
            self.para = None
            self.block = None
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
                self.list_counters.pop()
        elif tag in ("td", "th"):
            self.collect = None
        elif tag == "table":
            self._flush_table()
        elif tag in INLINE:
            if self.collect is not None:
                self.collect.append(("end", INLINE[tag]))
            elif INLINE[tag] in self.fmt:
                self.fmt.reverse()
                self.fmt.remove(INLINE[tag])
                self.fmt.reverse()

    def handle_data(self, data):
        if self.skip:
            return
        text = re.sub(r"\s+", " ", data)
        if not text.strip() and self.para is None:
            return
        if self.collect is not None:
            self.collect.append(("text", text))
        else:
            self._run(text)

    # --- таблицы ---
    def _flush_table(self):
        rows = self.table_rows or []
        if not rows:
            return
        ncols = max(sum(c["colspan"] for c in r) for r in rows)
        table = self.doc.add_table(rows=len(rows), cols=ncols)
        table.style = "Table Grid"
        for ri, row in enumerate(rows):
            ci = 0
            for c in row:
                cell = table.cell(ri, ci)
                if c["colspan"] > 1:
                    cell = cell.merge(table.cell(ri, min(ncols - 1, ci + c["colspan"] - 1)))
                self.cell, self.cell_used = cell, False
                self._new_para("td", {})
                saved = self.fmt
                self.fmt = ["bold"] if c["th"] else []
                for kind, val in c["html"]:
                    if kind == "text":
                        self._run(val)
                    elif kind == "br":
                        self.para.add_run().add_break()
                    elif kind == "start":
                        self.fmt.append(val)
                    elif kind == "end" and val in self.fmt:
                        self.fmt.remove(val)
                self.fmt = saved
                self.cell, self.para = None, None
                ci += c["colspan"]
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)
        self.table_rows = None


def _style_align(attrs: dict) -> Optional[str]:
    m = re.search(r"text-align\s*:\s*(left|center|right|justify)", attrs.get("style", "") or "")
    return m.group(1) if m else attrs.get("align")


def html_to_docx(html_text: str, title: str = "") -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin, sec.right_margin = Cm(3.0), Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.line_spacing = 1.15
    if title:
        doc.core_properties.title = title

    b = _Builder(doc)
    b.list_counters, b.table_rows, b.collect, b.cell_used = [], None, None, False
    b.feed(html_text or "")
    b.close()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
