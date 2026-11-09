"""
Преобразование документов в HTML для редактора Documentum.

Поддерживается:
- DOCX: абзацы, заголовки, выравнивание, начертание, списки, таблицы (с объединёнными ячейками);
- PDF с текстовым слоем: абзацы по блокам, заголовки по размеру и жирности шрифта;
- сканы (PDF без текста, JPG/PNG/TIFF): распознавание существующим OCR-движком;
- TXT;
- DOC/RTF/ODT: через LibreOffice, если он установлен.

HTML намеренно простой: h1–h3, p, ul/ol/li, table/tr/td, b, i, u, s, br.
Редактор и экспорт в DOCX понимают ровно этот набор.
"""

from __future__ import annotations

import html
import io
import logging
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")
LIBREOFFICE_EXT = (".doc", ".rtf", ".odt")


class UnsupportedFormatError(Exception):
    """Формат не поддерживается (или не хватает внешней программы)."""


@dataclass
class ConversionResult:
    html: str
    title: str
    source_kind: str                       # docx | pdf-text | ocr | txt
    warnings: List[str] = field(default_factory=list)


def convert_to_html(content: bytes, filename: str) -> ConversionResult:
    name = filename.lower()
    if name.endswith(".docx"):
        return _docx_to_html(content)
    if name.endswith(LIBREOFFICE_EXT):
        return _docx_to_html(_libreoffice_to_docx(content, filename), extra_warning="Файл преобразован через LibreOffice")
    if name.endswith(".pdf"):
        result = _pdf_text_to_html(content)
        return result if result else _ocr_to_html(content, filename)
    if name.endswith(IMAGE_EXT):
        return _ocr_to_html(content, filename)
    if name.endswith(".txt"):
        return _txt_to_html(content)
    raise UnsupportedFormatError(f"Формат файла «{filename}» не поддерживается")


# ---------------------------------------------------------------------------
# Общие помощники
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _align_attr(align: Optional[str]) -> str:
    return f' style="text-align:{align}"' if align else ""


def _guess_title(blocks_text: List[str], fallback: str = "Документ") -> str:
    for t in blocks_text:
        t = t.strip()
        if 3 <= len(t) <= 160:
            return t
    return fallback


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_alignment(paragraph) -> Optional[str]:
    from docx.enum.text import WD_ALIGN_PARAGRAPH as A
    align = paragraph.alignment
    if align is None and paragraph.style is not None:
        align = paragraph.style.paragraph_format.alignment
    return {A.CENTER: "center", A.RIGHT: "right", A.JUSTIFY: "justify", A.LEFT: "left"}.get(align)


def _docx_heading_level(paragraph) -> int:
    name = (paragraph.style.name if paragraph.style is not None else "") or ""
    low = name.lower()
    if low in ("title", "название", "заголовок"):
        return 1
    m = re.match(r"(heading|заголовок)\s*(\d)", low)
    if m:
        return min(int(m.group(2)), 3)
    return 0


def _docx_runs_html(paragraph) -> str:
    parts = []
    for child in paragraph._p.iterchildren():
        tag = child.tag.replace(_W, "")
        if tag == "r":
            parts.append(_docx_run_html(child))
        elif tag == "hyperlink":
            for r in child.iterchildren(_W + "r"):
                parts.append(_docx_run_html(r))
    return "".join(parts)


def _docx_run_html(r) -> str:
    rpr = r.find(_W + "rPr")

    def on(tag: str) -> bool:
        if rpr is None:
            return False
        el = rpr.find(_W + tag)
        return el is not None and el.get(_W + "val") not in ("0", "false", "none")

    text = []
    for node in r.iterchildren():
        t = node.tag.replace(_W, "")
        if t == "t":
            # Несколько пробелов подряд (выравнивание «город … дата») сохраняем неразрывными
            raw = re.sub(r" {2,}", lambda m: " " + " " * (len(m.group()) - 1), node.text or "")
            text.append(_esc(raw))
        elif t == "tab":
            text.append(" " * 8)
        elif t in ("br", "cr"):
            text.append("<br>")
    s = "".join(text)
    if not s:
        return ""
    if on("strike") or on("dstrike"):
        s = f"<s>{s}</s>"
    if on("u"):
        s = f"<u>{s}</u>"
    if on("i"):
        s = f"<i>{s}</i>"
    if on("b"):
        s = f"<b>{s}</b>"
    return s


def _docx_list_kind(paragraph, numbering) -> Optional[str]:
    """Возвращает 'ol' / 'ul', если абзац — элемент списка."""
    ppr = paragraph._p.pPr
    num_pr = ppr.numPr if ppr is not None else None
    style_name = (paragraph.style.name if paragraph.style is not None else "").lower()
    if num_pr is None:
        if "list number" in style_name:
            return "ol"
        if "list bullet" in style_name or "list paragraph" in style_name:
            return "ul"
        return None
    try:
        num_id = num_pr.numId.val
        ilvl = num_pr.ilvl.val if num_pr.ilvl is not None else 0
        num = numbering.find(f"{_W}num[@{_W}numId='{num_id}']")
        abs_id = num.find(_W + "abstractNumId").get(_W + "val")
        abstract = numbering.find(f"{_W}abstractNum[@{_W}abstractNumId='{abs_id}']")
        lvl = abstract.find(f"{_W}lvl[@{_W}ilvl='{ilvl}']")
        fmt = lvl.find(_W + "numFmt").get(_W + "val")
        return "ul" if fmt == "bullet" else "ol"
    except Exception:
        return "ul"


def _docx_table_html(table) -> str:
    rows_html = []
    for row in table.rows:
        cells_html, prev = [], None
        span = 1
        cells = list(row.cells)
        for i, cell in enumerate(cells):
            if prev is not None and cell._tc is prev._tc:
                span += 1
                continue
            if prev is not None:
                cells_html.append(_cell_html(prev, span))
            prev, span = cell, 1
        if prev is not None:
            cells_html.append(_cell_html(prev, span))
        rows_html.append("<tr>" + "".join(cells_html) + "</tr>")
    return "<table>" + "".join(rows_html) + "</table>"


def _cell_html(cell, span: int) -> str:
    inner = "<br>".join(h for h in (_docx_runs_html(p) for p in cell.paragraphs) if h)
    colspan = f' colspan="{span}"' if span > 1 else ""
    return f"<td{colspan}>{inner}</td>"


def _docx_to_html(content: bytes, extra_warning: str = "") -> ConversionResult:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(io.BytesIO(content))
    try:
        numbering = document.part.numbering_part.element
    except Exception:
        numbering = None

    out: List[str] = []
    texts: List[str] = []
    open_list: Optional[str] = None
    images = 0
    first_block = True

    def close_list():
        nonlocal open_list
        if open_list:
            out.append(f"</{open_list}>")
            open_list = None

    for child in document.element.body.iterchildren():
        tag = child.tag.replace(_W, "")
        if tag == "tbl":
            close_list()
            out.append(_docx_table_html(Table(child, document)))
            first_block = False
            continue
        if tag != "p":
            continue
        p = Paragraph(child, document)
        if child.findall(".//" + _W + "drawing") or child.findall(".//" + _W + "pict"):
            images += 1
        inner = _docx_runs_html(p)
        plain = p.text.strip()
        if not plain:
            continue
        texts.append(plain)
        align = _docx_alignment(p)
        level = _docx_heading_level(p)

        # Заголовки без стиля: короткий абзац целиком жирным и по центру
        if not level and align == "center" and len(plain) < 120 and inner.startswith("<b>") and inner.endswith("</b>") and inner.count("<b>") == 1:
            level = 1 if first_block else 2

        kind = _docx_list_kind(p, numbering) if numbering is not None and not level else None
        if kind:
            if open_list != kind:
                close_list()
                out.append(f"<{kind}>")
                open_list = kind
            out.append(f"<li>{inner}</li>")
        else:
            close_list()
            if level:
                inner = re.sub(r"^<b>(.*)</b>$", r"\1", inner)
                out.append(f'<h{level} style="text-align:{align or "left"}">{inner}</h{level}>')
            else:
                out.append(f"<p{_align_attr(align)}>{inner}</p>")
        first_block = False
    close_list()

    warnings = []
    if extra_warning:
        warnings.append(extra_warning)
    if images:
        warnings.append(f"Изображения ({images}) пока не переносятся в редактор — они остаются в исходном файле")
    if any(s.header.paragraphs and any(p.text.strip() for p in s.header.paragraphs) for s in document.sections):
        warnings.append("Колонтитулы не показываются в редакторе")
    return ConversionResult("".join(out), _guess_title(texts), "docx", warnings)


def _find_libreoffice() -> Optional[str]:
    for cand in ("soffice", "soffice.exe",
                 r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        path = shutil.which(cand) or (cand if os.path.isfile(cand) else None)
        if path:
            return path
    return None


def _libreoffice_to_docx(content: bytes, filename: str) -> bytes:
    soffice = _find_libreoffice()
    if not soffice:
        raise UnsupportedFormatError("Для файлов .doc, .rtf и .odt нужен установленный LibreOffice. Сохраните файл как .docx и загрузите снова.")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "source" + os.path.splitext(filename)[1].lower())
        with open(src, "wb") as f:
            f.write(content)
        subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, src],
                       check=True, timeout=120, capture_output=True)
        with open(os.path.join(tmp, "source.docx"), "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# PDF с текстовым слоем
# ---------------------------------------------------------------------------

def _pdf_text_to_html(content: bytes) -> Optional[ConversionResult]:
    import pymupdf

    doc = pymupdf.open(stream=content, filetype="pdf")
    blocks = []
    sizes = []
    for page in doc:
        width = page.rect.width
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            spans = [s for line in b["lines"] for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            lines = [" ".join(s["text"] for s in line["spans"]).strip() for line in b["lines"]]
            text = ""
            for ln in lines:
                if not ln:
                    continue
                if text.endswith("-") and ln[:1].islower():
                    text = text[:-1] + ln       # перенос слова
                else:
                    text = (text + " " + ln).strip()
            size = max(s["size"] for s in spans)
            bold = all(s["flags"] & 16 for s in spans)
            x0, _, x1, _ = b["bbox"]
            centered = abs((x0 + x1) / 2 - width / 2) < width * 0.05 and (x1 - x0) < width * 0.7
            blocks.append((text, size, bold, centered))
            sizes.extend(s["size"] for s in spans)
    doc.close()

    total = sum(len(b[0]) for b in blocks)
    if total < 40:
        return None                          # текста нет — это скан
    body = statistics.median(sizes) if sizes else 12
    out, texts = [], []
    for i, (text, size, bold, centered) in enumerate(blocks):
        texts.append(text)
        align = "center" if centered else None
        if len(text) < 140 and (size > body * 1.15 or (bold and centered)):
            level = 1 if (i == 0 or size > body * 1.4) else 2
            out.append(f'<h{level} style="text-align:{align or "left"}">{_esc(text)}</h{level}>')
        else:
            out.append(f"<p{_align_attr(align)}>{'<b>' + _esc(text) + '</b>' if bold else _esc(text)}</p>")
    return ConversionResult("".join(out), _guess_title(texts), "pdf-text",
                            ["PDF преобразован в редактируемый текст: сложная вёрстка и таблицы могут отличаться от оригинала"])


# ---------------------------------------------------------------------------
# Сканы — распознавание
# ---------------------------------------------------------------------------

def _ocr_to_html(content: bytes, filename: str) -> ConversionResult:
    from app.ocr.factory import get_ocr_engine
    from app.preprocessing.pipeline import DocumentPreprocessor

    prep = DocumentPreprocessor(dpi=200, auto_enhance=True).process(content, filename)
    engine = get_ocr_engine()
    paragraphs: List[str] = []
    words = low = 0
    for page in prep.pages:
        blocks = engine.recognize(page.processed_image, page_num=page.page_number)
        blocks = [b for b in blocks if b.text.strip()]
        if not blocks:
            continue
        heights = [max(1, b.bbox[3] - b.bbox[1]) for b in blocks]
        line_h = statistics.median(heights)
        blocks.sort(key=lambda b: ((b.bbox[1] + b.bbox[3]) / 2, b.bbox[0]))
        # Строки: блоки с близкой серединой по вертикали
        lines, cur, cur_y = [], [], None
        for b in blocks:
            y = (b.bbox[1] + b.bbox[3]) / 2
            if cur and abs(y - cur_y) > line_h * 0.6:
                lines.append(cur)
                cur = []
            cur.append(b)
            cur_y = y if len(cur) == 1 else cur_y
        if cur:
            lines.append(cur)
        # Абзацы: большой вертикальный зазор между строками
        para, prev_bottom = [], None
        for line in lines:
            line.sort(key=lambda b: b.bbox[0])
            top = min(b.bbox[1] for b in line)
            if para and prev_bottom is not None and top - prev_bottom > line_h * 1.2:
                paragraphs.append(" ".join(para))
                para = []
            for b in line:
                words += len(b.text.split())
                if b.confidence < 0.8:
                    low += len(b.text.split())
                    para.append(f'<span class="ocr-low" title="Распознано неуверенно">{_esc(b.text)}</span>')
                else:
                    para.append(_esc(b.text))
            prev_bottom = max(b.bbox[3] for b in line)
        if para:
            paragraphs.append(" ".join(para))

    if not paragraphs:
        raise UnsupportedFormatError("На изображении не найден текст")
    texts = [re.sub(r"<[^>]+>", "", p) for p in paragraphs]
    out = "".join(f"<p>{p}</p>" for p in paragraphs)
    warnings = [f"Текст распознан со скана: {words} слов, неуверенно — {low}. Сверьте выделенные слова с оригиналом."]
    return ConversionResult(out, _guess_title(texts, "Скан документа"), "ocr", warnings)


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------

def _txt_to_html(content: bytes) -> ConversionResult:
    for enc in ("utf-8-sig", "cp1251", "utf-16"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if p.strip()]
    out = "".join("<p>" + "<br>".join(_esc(l) for l in p.split("\n")) + "</p>" for p in paras)
    return ConversionResult(out, _guess_title(paras), "txt", [])
