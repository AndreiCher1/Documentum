"""
Модуль извлечения таблиц и анализа структуры документов (Document Understanding).
"""

from app.table.models import ExtractedTable, TableRow, TableCell
from app.table.extractor import TableExtractor

__all__ = ["ExtractedTable", "TableRow", "TableCell", "TableExtractor"]
