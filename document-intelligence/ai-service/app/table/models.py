"""
Pydantic-модели для табличных данных.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TableCell(BaseModel):
    """Ячейка таблицы с координатами и уверенностью распознавания."""
    row_idx: int
    col_idx: int
    text: str
    confidence: float = 1.0
    bbox: Optional[List[int]] = None


class TableRow(BaseModel):
    """Строка таблицы с ячейками."""
    row_idx: int
    cells: List[str]
    raw_cells: Optional[List[TableCell]] = None
    bbox: Optional[List[int]] = None
    is_header: bool = False


class ExtractedTable(BaseModel):
    """Извлечённая таблица со структурой, строками, заголовками и метаданными."""
    table_id: int = 1
    page: int = 1
    bbox: Optional[List[int]] = None
    headers: List[str] = []
    rows: List[List[str]] = []
    row_objects: Optional[List[Dict[str, str]]] = None
    summary: Optional[Dict[str, Any]] = None
    confidence: float = 0.95
    is_bordered: bool = False
