"""
Валидатор календарных дат документов.
"""

from datetime import datetime, date
import re
from app.validation.models import RuleResult


def validate_document_date(date_str: str, field_name: str = "date", label: str = "Дата документа") -> RuleResult:
    """
    Проверяет валидность даты, реальность календарного дня и временные границы.
    """
    if not date_str:
        return RuleResult(
            rule_id="DATE_EMPTY",
            rule_name=f"Проверка: {label}",
            status="WARN",
            message=f"{label} отсутствует",
            field_name=field_name
        )

    # Ищем стандартный паттерн ДД.ММ.ГГГГ
    m = re.search(r'(\d{2})[\.\/\-](\d{2})[\.\/\-](\d{4})', date_str)
    if not m:
        return RuleResult(
            rule_id="DATE_FORMAT",
            rule_name=f"Формат: {label}",
            status="WARN",
            message=f"Нестандартный формат даты: '{date_str}' (ожидается ДД.ММ.ГГГГ)",
            field_name=field_name
        )

    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))

    try:
        parsed_d = date(year, month, day)
    except ValueError as e:
        return RuleResult(
            rule_id="DATE_CALENDAR",
            rule_name=f"Календарь: {label}",
            status="FAIL",
            message=f"Несуществующая дата: {day:02d}.{month:02d}.{year:04d} ({str(e)})",
            field_name=field_name
        )

    today = date.today()

    # Дата выдачи документа не может быть далеко в будущем
    if "выдач" in label.lower() or "рождения" in label.lower() or "паспорт" in label.lower():
        if parsed_d > today:
            return RuleResult(
                rule_id="DATE_BOUNDS",
                rule_name=f"Временной диапазон: {label}",
                status="FAIL",
                message=f"{label} ({parsed_d.strftime('%d.%m.%Y')}) находится в будущем",
                field_name=field_name
            )

    if year < 1920:
        return RuleResult(
            rule_id="DATE_BOUNDS",
            rule_name=f"Временной диапазон: {label}",
            status="WARN",
            message=f"Год даты слишком ранний: {year}",
            field_name=field_name
        )

    return RuleResult(
        rule_id="DATE_VALID",
        rule_name=f"Корректность: {label}",
        status="PASS",
        message=f"{label} ({parsed_d.strftime('%d.%m.%Y')}) проверена ✓",
        field_name=field_name
    )

