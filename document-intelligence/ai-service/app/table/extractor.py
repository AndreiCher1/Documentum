"""
Главный координатор извлечения таблиц (Table Extractor).
"""

import json
import logging
from typing import Any, List, Optional
import numpy as np

from app.table.detector import TableDetector
from app.table.parser import TableParser
from app.table.models import ExtractedTable

logger = logging.getLogger(__name__)


class TableExtractor:
    """Оркестратор извлечения таблиц из документов."""

    def __init__(self):
        self.detector = TableDetector()
        self.parser = TableParser()

    def extract_tables(
        self,
        images: Optional[List[np.ndarray]],
        ocr_blocks: List[Any]
    ) -> List[ExtractedTable]:
        """
        Извлекает все таблицы со всех страниц документа.
        """
        all_tables: List[ExtractedTable] = []

        # Определяем список страниц в документе
        pages = sorted(list(set(getattr(b, 'page', 1) for b in ocr_blocks))) or [1]

        for p_idx, page_num in enumerate(pages):
            img = images[p_idx] if images and p_idx < len(images) else None

            # 1. Детектируем области таблиц
            regions = self.detector.detect(img, ocr_blocks, page_num=page_num)

            # 2. Парсим каждую область
            for r in regions:
                table = self.parser.parse(r, ocr_blocks)
                if table and table.rows:
                    table.table_id = len(all_tables) + 1
                    all_tables.append(table)
                    logger.info(
                        f"Обнаружена таблица {table.table_id} на стр. {table.page}: "
                        f"{len(table.headers)} колонок, {len(table.rows)} строк, "
                        f"сетчатая={table.is_bordered}"
                    )

        return all_tables

    def to_field_value(self, table: ExtractedTable) -> str:
        """Сериализует ExtractedTable в JSON-строку для сохранения в DocumentField."""
        payload = {
            "table_id": table.table_id,
            "page": table.page,
            "headers": table.headers,
            "rows": table.rows,
            "row_objects": table.row_objects,
            "summary": table.summary,
            "is_bordered": table.is_bordered
        }
        return json.dumps(payload, ensure_ascii=False)
