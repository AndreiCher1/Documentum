"""Тесты преобразования документов для редактора: DOCX/PDF/TXT → HTML и HTML → DOCX."""

import io
import re

import docx
import pymupdf
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.editor.converter import convert_to_html, UnsupportedFormatError
from app.editor.exporter import html_to_docx


def _sample_docx() -> bytes:
    d = docx.Document()
    t = d.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run("ДОГОВОР ПОСТАВКИ № 7").bold = True
    d.add_heading("1. Предмет договора", level=2)
    p = d.add_paragraph("Поставщик передаёт ")
    p.add_run("Товар").bold = True
    p.add_run(" в ")
    p.add_run("собственность").italic = True
    p.add_run(" Покупателя.")
    d.add_paragraph("Первый пункт", style="List Number")
    d.add_paragraph("Второй пункт", style="List Number")
    table = d.add_table(rows=2, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Наименование"
    table.cell(0, 2).text = "Сумма"
    table.cell(1, 0).text = "Стол"
    table.cell(1, 1).text = "2 шт."
    table.cell(1, 2).text = "10 000"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_docx_structure_and_formatting():
    r = convert_to_html(_sample_docx(), "dogovor.docx")
    assert r.source_kind == "docx"
    assert r.title == "ДОГОВОР ПОСТАВКИ № 7"
    assert '<h1 style="text-align:center">ДОГОВОР ПОСТАВКИ № 7</h1>' in r.html
    assert re.search(r"<h2[^>]*>1\. Предмет договора</h2>", r.html)
    assert "<b>Товар</b>" in r.html and "<i>собственность</i>" in r.html
    assert "<ol><li>Первый пункт</li><li>Второй пункт</li></ol>" in r.html
    assert '<td colspan="2">Наименование</td>' in r.html


def test_docx_keeps_repeated_spaces():
    d = docx.Document()
    d.add_paragraph("г. Самара      1 марта 2025 г.")
    buf = io.BytesIO()
    d.save(buf)
    r = convert_to_html(buf.getvalue(), "a.docx")
    assert "г. Самара      1 марта" in r.html


def test_roundtrip_docx_keeps_content():
    first = convert_to_html(_sample_docx(), "a.docx").html
    exported = html_to_docx(first, "Договор")
    again = docx.Document(io.BytesIO(exported))
    text = "\n".join(p.text for p in again.paragraphs)
    assert "ДОГОВОР ПОСТАВКИ № 7" in text
    assert "Поставщик передаёт Товар в собственность Покупателя." in text
    assert "1. Первый пункт" in text and "2. Второй пункт" in text
    bold = [r.text for p in again.paragraphs for r in p.runs if r.bold]
    assert "Товар" in bold
    assert len(again.tables) == 1
    assert again.tables[0].cell(1, 2).text == "10 000"
    assert again.tables[0].cell(0, 0).text == "Наименование"


def test_export_handles_editor_html():
    html = ('<h1>ДОГОВОР</h1><p style="text-align:right">г. Самара</p>'
            '<p>Текст с <b>жирным</b>, <u>подчёркнутым</u> и <s>зачёркнутым</s>.<br>Новая строка</p>'
            '<ul><li>пункт</li></ul><table><tr><td><p>А</p><p>Б</p></td><td>В</td></tr></table>')
    d = docx.Document(io.BytesIO(html_to_docx(html)))
    assert d.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert d.paragraphs[1].alignment == WD_ALIGN_PARAGRAPH.RIGHT
    runs = {r.text: r for r in d.paragraphs[2].runs}
    assert runs["подчёркнутым"].underline and runs["зачёркнутым"].font.strike
    assert any(p.text == "• пункт" for p in d.paragraphs)
    assert d.tables[0].cell(0, 0).text == "А\nБ"


def test_pdf_with_text_layer():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 80), "ПРИКАЗ № 15", fontsize=18, fontname="helv")
    page.insert_text((72, 130), "Utverdit reglament dokumentooborota s 1 dekabrya.", fontsize=11)
    page.insert_text((72, 146), "Kontrol ispolneniya ostavlyayu za soboy.", fontsize=11)
    r = convert_to_html(pdf.tobytes(), "prikaz.pdf")
    assert r.source_kind == "pdf-text"
    assert r.html.startswith("<h1")
    assert "reglament" in r.html


def test_txt_cp1251_paragraphs():
    raw = "Служебная записка\n\nПрошу согласовать закупку.\nСумма 245 000 руб.".encode("cp1251")
    r = convert_to_html(raw, "zapiska.txt")
    assert r.html == "<p>Служебная записка</p><p>Прошу согласовать закупку.<br>Сумма 245 000 руб.</p>"


def test_unsupported_format():
    try:
        convert_to_html(b"123", "data.xyz")
    except UnsupportedFormatError:
        return
    raise AssertionError("ожидалась ошибка формата")
