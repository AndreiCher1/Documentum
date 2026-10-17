"""
Единый движок проверки бизнес-правил (Validation Engine).

Координирует запуск валидаторов:
- ИНН (ФНС контрольные разряды для ЮЛ и ИП)
- Календарные даты и временные интервалы
- Табличные математические соотношения (Количество x Цена = Сумма)
- Сверка суммы строк таблицы с итогом к оплате
- Проверка стандартов VIN и данных ПТС
"""

import logging
from typing import List, Optional
from app.api.schemas import ExtractedField
from app.table.models import ExtractedTable
from app.validation.models import ValidationSummary, RuleResult
from app.validation.inn_validator import validate_inn
from app.validation.date_validator import validate_document_date
from app.validation.math_validator import validate_table_mathematics, validate_total_consistency
from app.validation.pts_validator import validate_pts_fields
from app.validation.snils_validator import validate_snils

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Оркестратор проверки бизнес-правил документа."""

    def validate(
        self,
        document_type: str,
        fields: List[ExtractedField],
        tables: Optional[List[ExtractedTable]] = None
    ) -> ValidationSummary:
        rules: List[RuleResult] = []
        fields_map = {f.name: f.value for f in fields}

        # 1. Валидация ИНН (если поле присутствует)
        for f in fields:
            if f.field_type == "INN" or "inn" in f.name:
                rules.append(validate_inn(f.value))

        # 1.1 Валидация СНИЛС (если поле присутствует)
        for f in fields:
            if f.field_type == "SNILS" or "snils" in f.name:
                rules.append(validate_snils(f.value))

        # 2. Валидация дат
        for f in fields:
            if f.field_type == "DATE" or "date" in f.name:
                rules.append(validate_document_date(f.value, field_name=f.name, label=f.display_name))

        # 3. Валидация таблиц и сумм (для счетов, актов, накладных)
        total_amount_val = fields_map.get("total_amount")
        if tables:
            for tbl in tables:
                # Математика ячеек: Количество x Цена = Сумма
                rules.extend(validate_table_mathematics(tbl))
                # Сверка суммы таблицы с итогом
                if total_amount_val:
                    rules.extend(validate_total_consistency(tbl, total_amount_val))

        # 4. Специфичные правила для ПТС
        if document_type in ("PTS", "VEHICLE_PASSPORT", "VEHICLE_DOCUMENT"):
            rules.extend(validate_pts_fields(fields_map))

        # Подсчёт итоговой статистики
        total = len(rules)
        passed = sum(1 for r in rules if r.status == "PASS")
        warns = sum(1 for r in rules if r.status == "WARN")
        fails = sum(1 for r in rules if r.status == "FAIL")

        if fails > 0:
            overall = "INVALID"
        elif warns > 0:
            overall = "WARNING"
        elif total > 0:
            overall = "VALID"
        else:
            overall = "VALID"

        logger.info(
            f"Валидация бизнес-правил ({document_type}): статус={overall}, "
            f"всего={total}, пройдено={passed}, пред={warns}, ошибок={fails}"
        )

        return ValidationSummary(
            overall_status=overall,
            total_rules=total,
            passed_rules=passed,
            warning_rules=warns,
            failed_rules=fails,
            rules=rules
        )


validation_engine = ValidationEngine()

