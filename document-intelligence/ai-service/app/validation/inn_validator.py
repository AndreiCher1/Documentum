"""
Валидатор ИНН и КПП по официальным контрольным суммам ФНС РФ.
"""

from typing import Optional
from app.validation.models import RuleResult


def validate_inn(inn_str: str) -> RuleResult:
    """
    Проверяет корректность 10-значного (юрлица) или 12-значного (физлица/ИП) ИНН
    по официальному алгоритму ФНС РФ с весовыми коэффициентами.
    """
    clean_inn = "".join(c for c in (inn_str or "") if c.isdigit())

    if not clean_inn:
        return RuleResult(
            rule_id="INN_FORMAT",
            rule_name="Формат ИНН",
            status="WARN",
            message="ИНН не заполнен или не содержит цифр",
            field_name="inn"
        )

    if len(clean_inn) not in (10, 12):
        return RuleResult(
            rule_id="INN_FORMAT",
            rule_name="Формат ИНН",
            status="FAIL",
            message=f"Длина ИНН должна быть 10 или 12 цифр (получено: {len(clean_inn)})",
            field_name="inn"
        )

    digits = [int(c) for c in clean_inn]

    # Валидация 10-значного ИНН (Юридические лица)
    if len(digits) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        control_num = sum(d * w for d, w in zip(digits[:9], weights)) % 11
        if control_num > 9:
            control_num %= 10

        if control_num == digits[9]:
            return RuleResult(
                rule_id="INN_CHECKSUM",
                rule_name="Контрольная сумма ИНН (ЮЛ)",
                status="PASS",
                message=f"ИНН {clean_inn} корректен (контрольный разряд {control_num} совпал) ✓",
                field_name="inn"
            )
        else:
            return RuleResult(
                rule_id="INN_CHECKSUM",
                rule_name="Контрольная сумма ИНН (ЮЛ)",
                status="FAIL",
                message=f"Ошибка контрольного разряда ИНН {clean_inn}: ожидался {control_num}, получен {digits[9]}",
                field_name="inn"
            )

    # Валидация 12-значного ИНН (Физлица и ИП)
    weights11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    control11 = sum(d * w for d, w in zip(digits[:10], weights11)) % 11
    if control11 > 9:
        control11 %= 10

    weights12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    control12 = sum(d * w for d, w in zip(digits[:11], weights12)) % 11
    if control12 > 9:
        control12 %= 10

    if control11 == digits[10] and control12 == digits[11]:
        return RuleResult(
            rule_id="INN_CHECKSUM",
            rule_name="Контрольная сумма ИНН (ИП/ФЛ)",
            status="PASS",
            message=f"ИНН {clean_inn} корректен (контрольные разряды {control11}, {control12} совпали) ✓",
            field_name="inn"
        )
    else:
        return RuleResult(
            rule_id="INN_CHECKSUM",
            rule_name="Контрольная сумма ИНН (ИП/ФЛ)",
            status="FAIL",
            message=f"Ошибка контрольных цифр ИНН {clean_inn}: ожид. [{control11}, {control12}], получ. [{digits[10]}, {digits[11]}]",
            field_name="inn"
        )

