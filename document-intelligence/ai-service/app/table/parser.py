"""
Парсер строк и ячеек таблицы (Table Parser).

Преобразует найденную область таблицы и блоки OCR в строгую матрицу строк и ячеек.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from app.table.detector import TableRegion
from app.table.models import ExtractedTable, TableCell, TableRow

logger = logging.getLogger(__name__)


class TableParser:
    """Парсер ячеек и строк таблицы."""

    def parse(self, region: TableRegion, ocr_blocks: List[Any]) -> Optional[ExtractedTable]:
        """
        Преобразует TableRegion в структурированный ExtractedTable.
        """
        if not region.headers or not region.col_spans:
            return None

        # Отбираем блоки, попадающие в тело таблицы (ниже заголовка и выше футера)
        body_blocks = [
            b for b in ocr_blocks
            if getattr(b, 'page', 1) == region.page
            and b.bbox[1] >= region.header_y[1] - 5
            and b.bbox[3] <= region.footer_y + 10
            and region.bbox[0] - 20 <= b.bbox[0] and b.bbox[2] <= region.bbox[2] + 20
        ]

        if not body_blocks:
            return None

        # Сортируем блоки по вертикали Y
        body_blocks.sort(key=lambda b: b.bbox[1])

        # Кластеризуем блоки по горизонтальным полосам (строкам таблицы)
        row_clusters = self._cluster_into_rows(body_blocks)

        parsed_rows: List[List[str]] = []
        parsed_row_objects: List[Dict[str, str]] = []
        num_cols = len(region.headers)

        for r_idx, row_blks in enumerate(row_clusters):
            # Создаём пустую строку
            row_cells = ["" for _ in range(num_cols)]

            # Распределяем блоки строки по колонкам
            for b in row_blks:
                bx_center = (b.bbox[0] + b.bbox[2]) / 2
                best_col = self._find_matching_column(bx_center, region.col_spans)

                if best_col is not None:
                    txt = b.text.strip()
                    if row_cells[best_col]:
                        row_cells[best_col] += " " + txt
                    else:
                        row_cells[best_col] = txt

            # Проверяем, не пустая ли строка и не является ли строкой футера/итого
            non_empty = [c for c in row_cells if c.strip()]
            if not non_empty:
                continue

            # Проверяем, не строка ли "Итого"
            first_text = " ".join(row_cells[:2]).lower()
            if any(re.search(pat, first_text) for pat in [r'итого', r'всего', r'в\s*т\.?ч\.?\s*ндс']):
                # Строка итогов — добавляем её или сохраняем в метаданные
                pass

            # Нормализуем пропущенные запятые в суммах ячеек
            from app.postprocessing.spell_corrector import restore_monetary_commas
            row_cells = [restore_monetary_commas(c) for c in row_cells]

            parsed_rows.append(row_cells)

            # Формируем объект {Заголовок: Значение}
            row_dict = {}
            for col_idx, h_name in enumerate(region.headers):
                row_dict[h_name] = row_cells[col_idx] if col_idx < len(row_cells) else ""
            parsed_row_objects.append(row_dict)

        if not parsed_rows:
            return None

        # Расчёт сводки по таблице (summary)
        summary = self._compute_summary(region.headers, parsed_rows)

        return ExtractedTable(
            table_id=1,
            page=region.page,
            bbox=region.bbox,
            headers=region.headers,
            rows=parsed_rows,
            row_objects=parsed_row_objects,
            summary=summary,
            confidence=0.94 if region.is_bordered else 0.88,
            is_bordered=region.is_bordered
        )

    def _cluster_into_rows(self, blocks: List[Any]) -> List[List[Any]]:
        """Группирует OCR-блоки в строки таблицы на основе перекрытия по Y."""
        if not blocks:
            return []

        rows: List[List[Any]] = []
        current_row = [blocks[0]]

        for b in blocks[1:]:
            # Проверяем вертикальное перекрытие с текущей строкой
            row_y1 = min(blk.bbox[1] for blk in current_row)
            row_y2 = max(blk.bbox[3] for blk in current_row)
            row_height = max(row_y2 - row_y1, 12)

            b_center_y = (b.bbox[1] + b.bbox[3]) / 2

            # Если центр блока находится в пределах текущей строки с допуском
            if row_y1 - 4 <= b_center_y <= row_y2 + 6:
                current_row.append(b)
            else:
                rows.append(sorted(current_row, key=lambda x: x.bbox[0]))
                current_row = [b]

        if current_row:
            rows.append(sorted(current_row, key=lambda x: x.bbox[0]))

        return rows

    def _find_matching_column(self, x_center: float, col_spans: List[tuple]) -> Optional[int]:
        """Находит индекс колонки, в которую попадает координата X."""
        # 1. Точное попадание в диапазон колонки
        for idx, (c_start, c_end) in enumerate(col_spans):
            if c_start <= x_center <= c_end:
                return idx

        # 2. Если между границами, ищем ближайший центр колонки
        min_dist = float('inf')
        best_col = None
        for idx, (c_start, c_end) in enumerate(col_spans):
            c_center = (c_start + c_end) / 2
            dist = abs(x_center - c_center)
            if dist < min_dist:
                min_dist = dist
                best_col = idx

        return best_col

    def _compute_summary(self, headers: List[str], rows: List[List[str]]) -> Dict[str, Any]:
        """Расчёт итоговых статистических показателей по таблице."""
        summary: Dict[str, Any] = {
            "total_rows": len(rows),
            "total_columns": len(headers),
        }

        # Ищем колонку с ценой / суммой
        amount_col_idx = None
        for i, h in enumerate(headers):
            h_low = h.lower()
            if any(w in h_low for w in ['сумма', 'всего', 'стоимость', 'цена']):
                amount_col_idx = i

        if amount_col_idx is not None:
            total_sum = 0.0
            sum_count = 0
            for r in rows:
                if amount_col_idx < len(r):
                    val_str = r[amount_col_idx]
                    # Извлекаем числа
                    clean_val = re.sub(r'[^\d,\.]', '', val_str).replace(',', '.')
                    try:
                        if clean_val:
                            val_float = float(clean_val)
                            total_sum += val_float
                            sum_count += 1
                    except ValueError:
                        pass

            if sum_count > 0:
                summary["calculated_total"] = round(total_sum, 2)
                summary["formatted_total"] = f"{total_sum:,.2f} руб.".replace(',', ' ')

        return summary
