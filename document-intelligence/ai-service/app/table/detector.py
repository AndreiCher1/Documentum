"""
Детектор табличных областей в документах (Table Detector).

Поддерживает два режима детекции:
1. Сетчатые таблицы (Bordered): OpenCV морфологический анализ горизонтальных и вертикальных линий.
2. Бессеточные таблицы (Borderless): геометрический анализ OCR-разметки по ключевым заголовкам колонок.
"""

import logging
import re
from typing import Any, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Ключевые слова заголовков колонок в российских деловых документах
TABLE_HEADER_KEYWORDS = [
    r'№\s*(?:п\/?п)?',
    r'n\s*(?:п\/?п)?',
    r'п\/?п',
    r'наименование(?:\s*товара|\s*работ|\s*услуг)?',
    r'товар|услуга|описание',
    r'кол(?:-|\s*)?во|количество',
    r'ед(?:\.|\s*изм\.?)?',
    r'цена(?:\s*без\s*ндс)?',
    r'сумма(?:\s*без\s*ндс)?',
    r'ставка\s*ндс|ндс',
    r'всего(?:\s*с\s*ндс)?',
    r'стоимость',
    r'артикул|код'
]

TABLE_FOOTER_KEYWORDS = [
    r'^итого(?:\s*без\s*ндс)?[:\.]?',
    r'^всего(?:\s*к\s*оплате|\s*наименований)?[:\.]?',
    r'^в\s*том\s*числе\s*ндс[:\.]?',
    r'^сумма\s*прописью[:\.]?',
    r'^руководитель[:\.]?',
    r'^главный\s*бухгалтер[:\.]?',
    r'^подпись[:\.]?'
]


class TableRegion:
    """Обнаруженная область таблицы с границами колонок и строк."""

    def __init__(
        self,
        bbox: List[int],
        headers: List[str],
        col_spans: List[Tuple[int, int]],
        header_y: Tuple[int, int],
        footer_y: int,
        page: int = 1,
        is_bordered: bool = False
    ):
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.headers = headers
        self.col_spans = col_spans  # [(x_start, x_end), ...]
        self.header_y = header_y    # (y_top, y_bottom)
        self.footer_y = footer_y    # y_bottom_of_table
        self.page = page
        self.is_bordered = is_bordered


class TableDetector:
    """Универсальный детектор таблиц."""

    def detect(self, image: Optional[np.ndarray], ocr_blocks: List[Any], page_num: int = 1) -> List[TableRegion]:
        """
        Главная точка входа для детекции таблиц на странице.
        Сначала пробует морфологическую детекцию линий сетки, затем текстовую детекцию заголовков.
        """
        regions: List[TableRegion] = []

        # 1. Попытка детекции сетчатой таблицы через OpenCV
        if image is not None:
            try:
                grid_regions = self._detect_bordered_tables(image, ocr_blocks, page_num)
                if grid_regions:
                    regions.extend(grid_regions)
            except Exception as e:
                logger.warning(f"Ошибка морфологической детекции сетки таблицы: {e}")

        # 2. Если сетчатых таблиц не найдено, ищем бессеточные таблицы по структуре заголовков
        if not regions:
            try:
                borderless_regions = self._detect_borderless_tables(ocr_blocks, page_num)
                if borderless_regions:
                    regions.extend(borderless_regions)
            except Exception as e:
                logger.warning(f"Ошибка текстовой детекции бессеточных таблиц: {e}")

        return regions

    def _detect_bordered_tables(
        self,
        image: np.ndarray,
        ocr_blocks: List[Any],
        page_num: int = 1
    ) -> List[TableRegion]:
        """Морфологическая детекция линий таблицы в градациях серого."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        h, w = gray.shape[:2]

        # Бинаризация с инверсией
        thresh = cv2.adaptiveThreshold(
            ~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2
        )

        # Выделение горизонтальных линий
        h_size = max(int(w / 30), 20)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=2)

        # Выделение вертикальных линий
        v_size = max(int(h / 35), 20)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
        v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=2)

        # Объединение сетки таблицы
        table_grid = cv2.add(h_lines, v_lines)

        # Поиск контуров таблицы
        contours, _ = cv2.findContours(table_grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Фильтрация: таблица должна занимать значительную ширину и иметь достаточную высоту
            if cw > w * 0.40 and ch > 60:
                # Находим блоки OCR внутри этой таблицы
                inner_blocks = [
                    b for b in ocr_blocks
                    if getattr(b, 'page', 1) == page_num
                    and x <= b.bbox[0] and b.bbox[2] <= x + cw
                    and y <= b.bbox[1] and b.bbox[3] <= y + ch
                ]

                # Пытаемся выделить колонки и заголовки
                headers, col_spans, header_y = self._extract_columns_from_blocks(inner_blocks, (y, y + ch))
                if len(col_spans) >= 2:
                    regions.append(
                        TableRegion(
                            bbox=[x, y, x + cw, y + ch],
                            headers=headers,
                            col_spans=col_spans,
                            header_y=header_y,
                            footer_y=y + ch,
                            page=page_num,
                            is_bordered=True
                        )
                    )

        return regions

    def _detect_borderless_tables(
        self,
        ocr_blocks: List[Any],
        page_num: int = 1
    ) -> List[TableRegion]:
        """Детекция таблиц по геометрическому анализу заголовков колонок."""
        page_blocks = [b for b in ocr_blocks if getattr(b, 'page', 1) == page_num]
        if len(page_blocks) < 5:
            return []

        # Группируем блоки в строки по схожему Y
        sorted_by_y = sorted(page_blocks, key=lambda b: b.bbox[1])

        # Ищем строку-кандидат на заголовок таблицы
        best_header_row = None
        best_match_count = 0
        header_y_span = (0, 0)

        for i, block in enumerate(sorted_by_y):
            b_y1, b_y2 = block.bbox[1], block.bbox[3]
            line_height = max(b_y2 - b_y1, 10)

            # Находим все блоки на этой же горизонтальной полосе
            row_blocks = [
                b for b in sorted_by_y
                if abs(b.bbox[1] - b_y1) < line_height * 0.8
                or abs((b.bbox[1] + b.bbox[3]) / 2 - (b_y1 + b_y2) / 2) < line_height * 0.6
            ]

            # Проверяем, сколько ключевых слов заголовков таблицы найдено в этой строке
            row_blocks_sorted = sorted(row_blocks, key=lambda b: b.bbox[0])
            matched_count = 0
            for rb in row_blocks_sorted:
                txt = rb.text.strip().lower()
                for pattern in TABLE_HEADER_KEYWORDS:
                    if re.search(r'\b' + pattern + r'\b', txt):
                        matched_count += 1
                        break

            # Если найдено 2 или более ключевых слов заголовка (например, № + Наименование + Сумма)
            if matched_count >= 2 and matched_count > best_match_count:
                best_match_count = matched_count
                best_header_row = row_blocks_sorted
                min_y = min(b.bbox[1] for b in row_blocks_sorted)
                max_y = max(b.bbox[3] for b in row_blocks_sorted)
                header_y_span = (min_y, max_y)

        if not best_header_row or best_match_count < 2:
            return []

        # Формируем колонки из найденного заголовка
        headers = [b.text.strip() for b in best_header_row]
        col_spans = []
        for i, b in enumerate(best_header_row):
            x1, x2 = b.bbox[0], b.bbox[2]
            # Расширяем диапазон колонки до середины расстояния до соседних колонок
            prev_x2 = best_header_row[i - 1].bbox[2] if i > 0 else max(0, x1 - 50)
            next_x1 = best_header_row[i + 1].bbox[0] if i + 1 < len(best_header_row) else x2 + 100

            col_left = int((prev_x2 + x1) / 2) if i > 0 else max(0, x1 - 30)
            col_right = int((x2 + next_x1) / 2) if i + 1 < len(best_header_row) else x2 + 60
            col_spans.append((col_left, col_right))

        # Ищем нижнюю границу таблицы (футер: "Итого", "Всего", подписи)
        footer_y = None
        for b in sorted_by_y:
            if b.bbox[1] > header_y_span[1]:
                txt = b.text.strip().lower()
                for f_pat in TABLE_FOOTER_KEYWORDS:
                    if re.search(f_pat, txt):
                        footer_y = b.bbox[3] + 20
                        break
                if footer_y:
                    break

        if not footer_y:
            # Если явного футера нет, берём максимальный Y среди блоков, расположенных под колонками
            sub_blocks = [b for b in sorted_by_y if b.bbox[1] > header_y_span[1] and b.bbox[0] >= col_spans[0][0]]
            if sub_blocks:
                footer_y = max(b.bbox[3] for b in sub_blocks) + 15
            else:
                footer_y = header_y_span[1] + 150

        # Общий Bounding Box таблицы
        table_bbox = [
            min(span[0] for span in col_spans),
            header_y_span[0],
            max(span[1] for span in col_spans),
            footer_y
        ]

        return [
            TableRegion(
                bbox=table_bbox,
                headers=headers,
                col_spans=col_spans,
                header_y=header_y_span,
                footer_y=footer_y,
                page=page_num,
                is_bordered=False
            )
        ]

    def _extract_columns_from_blocks(
        self,
        blocks: List[Any],
        table_y_span: Tuple[int, int]
    ) -> Tuple[List[str], List[Tuple[int, int]], Tuple[int, int]]:
        """Извлечение колонок из блоков таблицы."""
        if not blocks:
            return [], [], (0, 0)

        # Сортируем блоки по вертикали
        sorted_blks = sorted(blocks, key=lambda b: b.bbox[1])

        # Кластеризуем в горизонтальные строки
        rows = []
        cur_row = [sorted_blks[0]]
        for b in sorted_blks[1:]:
            r_y1 = min(x.bbox[1] for x in cur_row)
            r_y2 = max(x.bbox[3] for x in cur_row)
            bc = (b.bbox[1] + b.bbox[3]) / 2
            if r_y1 - 6 <= bc <= r_y2 + 6:
                cur_row.append(b)
            else:
                rows.append(sorted(cur_row, key=lambda x: x.bbox[0]))
                cur_row = [b]
        if cur_row:
            rows.append(sorted(cur_row, key=lambda x: x.bbox[0]))

        # Первая строка — это заголовок таблицы
        header_blocks = rows[0]
        header_blocks.sort(key=lambda b: b.bbox[0])
        headers = [b.text.strip() for b in header_blocks]
        min_y = min(b.bbox[1] for b in header_blocks)
        max_y = max(b.bbox[3] for b in header_blocks)

        col_spans = []
        for i, b in enumerate(header_blocks):
            c_left = b.bbox[0] - 15 if i == 0 else col_spans[i - 1][1]
            c_right = header_blocks[i + 1].bbox[0] - 5 if i + 1 < len(header_blocks) else b.bbox[2] + 250
            col_spans.append((c_left, c_right))

        return headers, col_spans, (min_y, max_y)
