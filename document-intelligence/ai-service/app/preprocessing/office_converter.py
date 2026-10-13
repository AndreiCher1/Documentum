"""
Конвертер офисных и текстовых документов (DOCX, XLSX, CSV, TXT).

Функции:
1. Прямое чтение структурированного цифрового текста без потерь качества.
2. Формирование виртуальных страниц формата A4 (1240 x 1754 px) с чистой типографикой.
3. Генерация точных геометрических Bounding Box [x1, y1, x2, y2] для каждого абзаца и ячейки таблицы.
4. Мгновенный рендеринг в PNG для превью в Electron UI.
"""

import io
import re
import csv
import logging
from typing import List, Tuple, Any
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.api.schemas import OcrResult

logger = logging.getLogger(__name__)

PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN_X = 80
MARGIN_Y = 80
LINE_HEIGHT = 32
FONT_SIZE_BODY = 22
FONT_SIZE_TITLE = 30
FONT_SIZE_TABLE = 18


def _get_font(size: int = FONT_SIZE_BODY, bold: bool = False):
    """Загрузка системного шрифта с поддержкой кириллицы."""
    try:
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            return ImageFont.truetype("calibri.ttf", size)
        except Exception:
            return ImageFont.load_default()


class OfficeDocumentConverter:
    """Универсальный парсер и визуализатор офисных документов."""

    @classmethod
    def is_office_document(cls, filename: str) -> bool:
        fn = filename.lower()
        return fn.endswith((".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt"))

    @classmethod
    def process_file(
        cls,
        content: bytes,
        filename: str
    ) -> List[Tuple[np.ndarray, List[OcrResult]]]:
        """
        Парсит документ и возвращает список страниц:
        Каждая страница - это (np_image_bgr, list_of_ocr_blocks).
        """
        fn = filename.lower()
        if fn.endswith((".docx", ".doc")):
            return cls._process_docx(content)
        elif fn.endswith((".xlsx", ".xls")):
            return cls._process_xlsx(content)
        elif fn.endswith(".csv"):
            return cls._process_csv(content)
        elif fn.endswith(".txt"):
            return cls._process_txt(content)
        return []

    @classmethod
    def render_page_png(cls, content: bytes, filename: str, page: int = 1) -> bytes:
        """Рендерит запрошенную страницу в PNG байты для /render-page."""
        pages = cls.process_file(content, filename)
        if not pages:
            # Пустой белый лист
            img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        idx = max(0, min(page - 1, len(pages) - 1))
        page_bgr, _ = pages[idx]
        page_rgb = Image.fromarray(page_bgr[:, :, ::-1])
        buf = io.BytesIO()
        page_rgb.save(buf, format="PNG")
        return buf.getvalue()

    # --- DOCX Обработчик ---
    @classmethod
    def _process_docx(cls, content: bytes) -> List[Tuple[np.ndarray, List[OcrResult]]]:
        import docx
        doc = docx.Document(io.BytesIO(content))

        pages: List[Tuple[np.ndarray, List[OcrResult]]] = []
        current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
        draw = ImageDraw.Draw(current_img)
        current_blocks: List[OcrResult] = []
        y = MARGIN_Y
        page_num = 1

        font_title = _get_font(FONT_SIZE_TITLE, bold=True)
        font_body = _get_font(FONT_SIZE_BODY)

        def flush_page():
            nonlocal current_img, draw, current_blocks, y, page_num
            # Добавляем номер страницы внизу
            font_footer = _get_font(16)
            draw.text((PAGE_WIDTH // 2 - 20, PAGE_HEIGHT - 50), f"— {page_num} —", fill=(130, 130, 130), font=font_footer)
            pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
            page_num += 1
            current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
            draw = ImageDraw.Draw(current_img)
            current_blocks = []
            y = MARGIN_Y

        # Считываем параграфы
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                y += LINE_HEIGHT // 2
                continue

            is_heading = p.style.name.startswith("Heading") or len(text) < 60 and text.isupper()
            font = font_title if is_heading else font_body
            f_height = 42 if is_heading else 30

            # Перенос длинных строк
            words = text.split()
            lines = []
            cur_line = []
            for w in words:
                test_line = " ".join(cur_line + [w])
                bbox = font.getbbox(test_line)
                line_w = bbox[2] - bbox[0]
                if line_w < (PAGE_WIDTH - 2 * MARGIN_X):
                    cur_line.append(w)
                else:
                    if cur_line:
                        lines.append(" ".join(cur_line))
                    cur_line = [w]
            if cur_line:
                lines.append(" ".join(cur_line))

            for l_text in lines:
                if y + f_height > (PAGE_HEIGHT - MARGIN_Y):
                    flush_page()

                bbox_t = font.getbbox(l_text)
                txt_w = bbox_t[2] - bbox_t[0]
                txt_h = bbox_t[3] - bbox_t[1]

                # Отрисовка
                color = (20, 20, 30) if not is_heading else (10, 30, 90)
                draw.text((MARGIN_X, y), l_text, fill=color, font=font)

                current_blocks.append(
                    OcrResult(
                        text=l_text,
                        confidence=0.99,
                        bbox=[MARGIN_X, y, MARGIN_X + txt_w, y + txt_h],
                        page=page_num
                    )
                )
                y += f_height + 4

            y += 8  # Отступ между абзацами

        # Считываем встроенные таблицы docx
        for table in doc.tables:
            y += 16
            font_t = _get_font(FONT_SIZE_TABLE)
            col_count = len(table.columns)
            col_width = (PAGE_WIDTH - 2 * MARGIN_X) // max(1, col_count)

            for r_idx, row in enumerate(table.rows):
                if y + 40 > (PAGE_HEIGHT - MARGIN_Y):
                    flush_page()

                row_y = y
                for c_idx, cell in enumerate(row.cells):
                    cell_x = MARGIN_X + c_idx * col_width
                    c_text = cell.text.strip().replace("\n", " ")
                    draw.rectangle([cell_x, row_y, cell_x + col_width, row_y + 36], outline=(180, 180, 180), width=1)
                    if c_text:
                        short_text = c_text[:col_width // 10]
                        draw.text((cell_x + 6, row_y + 8), short_text, fill=(30, 30, 30), font=font_t)
                        current_blocks.append(
                            OcrResult(
                                text=c_text,
                                confidence=0.99,
                                bbox=[cell_x + 4, row_y + 4, cell_x + col_width - 4, row_y + 32],
                                page=page_num
                            )
                        )
                y += 36
            y += 16

        flush_page()
        return pages

    # --- XLSX Обработчик ---
    @classmethod
    def _process_xlsx(cls, content: bytes) -> List[Tuple[np.ndarray, List[OcrResult]]]:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.active

        pages: List[Tuple[np.ndarray, List[OcrResult]]] = []
        current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
        draw = ImageDraw.Draw(current_img)
        current_blocks: List[OcrResult] = []
        y = MARGIN_Y
        page_num = 1

        font_header = _get_font(24, bold=True)
        font_cell = _get_font(16)

        # Заголовок листа
        draw.text((MARGIN_X, y), f"Лист: {sheet.title}", fill=(20, 40, 100), font=font_header)
        y += 50

        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return [(np.array(current_img)[:, :, ::-1], [])]

        max_cols = min(10, max(len(r) for r in rows if r))
        col_w = (PAGE_WIDTH - 2 * MARGIN_X) // max(1, max_cols)

        for r_idx, row in enumerate(rows):
            if not any(row):
                continue
            if y + 36 > (PAGE_HEIGHT - MARGIN_Y):
                pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
                page_num += 1
                current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
                draw = ImageDraw.Draw(current_img)
                current_blocks = []
                y = MARGIN_Y

            is_head_row = (r_idx == 0)
            row_y = y

            for c_idx in range(max_cols):
                val = row[c_idx] if c_idx < len(row) else ""
                val_str = str(val).strip() if val is not None else ""
                cell_x = MARGIN_X + c_idx * col_w

                # Фон заголовка
                bg_col = (235, 240, 250) if is_head_row else (255, 255, 255)
                draw.rectangle([cell_x, row_y, cell_x + col_w, row_y + 32], fill=bg_col, outline=(190, 200, 215))

                if val_str:
                    draw.text((cell_x + 6, row_y + 6), val_str[:col_w // 9], fill=(20, 20, 20), font=font_cell)
                    current_blocks.append(
                        OcrResult(
                            text=val_str,
                            confidence=0.99,
                            bbox=[cell_x + 2, row_y + 2, cell_x + col_w - 2, row_y + 30],
                            page=page_num
                        )
                    )
            y += 32

        pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
        return pages

    # --- CSV Обработчик ---
    @classmethod
    def _process_csv(cls, content: bytes) -> List[Tuple[np.ndarray, List[OcrResult]]]:
        # Детекция кодировки (UTF-8 или CP1251)
        text_data = ""
        try:
            text_data = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text_data = content.decode("cp1251")
            except Exception:
                text_data = content.decode("utf-8", errors="ignore")

        reader = csv.reader(io.StringIO(text_data))
        rows = list(reader)

        pages: List[Tuple[np.ndarray, List[OcrResult]]] = []
        current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
        draw = ImageDraw.Draw(current_img)
        current_blocks: List[OcrResult] = []
        y = MARGIN_Y
        page_num = 1
        font_cell = _get_font(16)

        max_cols = min(10, max(len(r) for r in rows if r) if rows else 1)
        col_w = (PAGE_WIDTH - 2 * MARGIN_X) // max(1, max_cols)

        for r_idx, row in enumerate(rows):
            if y + 32 > (PAGE_HEIGHT - MARGIN_Y):
                pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
                page_num += 1
                current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
                draw = ImageDraw.Draw(current_img)
                current_blocks = []
                y = MARGIN_Y

            for c_idx in range(min(max_cols, len(row))):
                val_str = row[c_idx].strip()
                cell_x = MARGIN_X + c_idx * col_w
                bg_col = (240, 244, 252) if r_idx == 0 else (255, 255, 255)
                draw.rectangle([cell_x, y, cell_x + col_w, y + 30], fill=bg_col, outline=(200, 205, 215))
                if val_str:
                    draw.text((cell_x + 6, y + 6), val_str[:col_w // 9], fill=(20, 20, 20), font=font_cell)
                    current_blocks.append(
                        OcrResult(
                            text=val_str,
                            confidence=0.99,
                            bbox=[cell_x + 2, y + 2, cell_x + col_w - 2, y + 28],
                            page=page_num
                        )
                    )
            y += 30

        pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
        return pages

    # --- TXT Обработчик ---
    @classmethod
    def _process_txt(cls, content: bytes) -> List[Tuple[np.ndarray, List[OcrResult]]]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("cp1251")
            except Exception:
                text = content.decode("utf-8", errors="ignore")

        pages: List[Tuple[np.ndarray, List[OcrResult]]] = []
        current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
        draw = ImageDraw.Draw(current_img)
        current_blocks: List[OcrResult] = []
        y = MARGIN_Y
        page_num = 1
        font_body = _get_font(20)

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                y += 18
                continue

            # Перенос длинной строки
            words = line.split()
            wrapped_lines = []
            cur_line = []
            for w in words:
                t = " ".join(cur_line + [w])
                box = font_body.getbbox(t)
                if (box[2] - box[0]) < (PAGE_WIDTH - 2 * MARGIN_X):
                    cur_line.append(w)
                else:
                    if cur_line:
                        wrapped_lines.append(" ".join(cur_line))
                    cur_line = [w]
            if cur_line:
                wrapped_lines.append(" ".join(cur_line))

            for wl in wrapped_lines:
                if y + 28 > (PAGE_HEIGHT - MARGIN_Y):
                    pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
                    page_num += 1
                    current_img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255))
                    draw = ImageDraw.Draw(current_img)
                    current_blocks = []
                    y = MARGIN_Y

                bbox_t = font_body.getbbox(wl)
                txt_w = bbox_t[2] - bbox_t[0]
                txt_h = bbox_t[3] - bbox_t[1]

                draw.text((MARGIN_X, y), wl, fill=(25, 25, 30), font=font_body)
                current_blocks.append(
                    OcrResult(
                        text=wl,
                        confidence=0.99,
                        bbox=[MARGIN_X, y, MARGIN_X + txt_w, y + txt_h],
                        page=page_num
                    )
                )
                y += 28

        pages.append((np.array(current_img)[:, :, ::-1], current_blocks))
        return pages
