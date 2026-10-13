"""
Модели данных для модуля валидации бизнес-правил (Validation Models).
"""

from typing import List, Optional
from pydantic import BaseModel


class RuleResult(BaseModel):
    """Результат проверки одного бизнес-правила."""
    rule_id: str                      # Например: "INN_CHECKSUM", "TABLE_ROW_SUM"
    rule_name: str                    # Человекочитаемое название правила
    status: str                       # "PASS", "WARN", "FAIL"
    message: str                      # Описание результата (например: "ИНН 7701234567 проверен по алгоритму ФНС РФ ✓")
    field_name: Optional[str] = None  # Имя поля, к которому относится проверка


class ValidationSummary(BaseModel):
    """Сводный отчёт проверки документа."""
    overall_status: str               # "VALID", "WARNING", "INVALID"
    total_rules: int
    passed_rules: int
    warning_rules: int
    failed_rules: int
    rules: List[RuleResult] = []

