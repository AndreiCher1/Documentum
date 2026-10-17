"""
Валидатор СНИЛС (Страховой номер индивидуального лицевого счета).

Реализует официальный алгоритм проверки контрольного числа Пенсионного фонда РФ (ПФР / СФР):
1. СНИЛС состоит из 11 цифр: первые 9 — порядковый номер, последние 2 — контрольное число.
2. Проверка контрольного числа проводится только для номеров больше 001-001-998.
3. Каждая из первых 9 цифр умножается на позиционный вес от 9 до 1 (d1*9 + d2*8 + ... + d9*1).
4. Правила контрольной суммы:
   - Если сумма < 100: контрольное число = сумме;
   - Если сумма == 100 или 101: контрольное число = 00;
   - Если сумма > 101: берется остаток от деления суммы на 101:
       * если остаток < 100: контрольное число = остатку;
       * если остаток == 100 или 101: контрольное число = 00.
"""

import re
from app.validation.models import RuleResult


def validate_snils(snils_str: str) -> RuleResult:
    """
    Проверяет валидность строки СНИЛС по официальному алгоритму ПФР.
    """
    rule_id = "SNILS_CHECKSUM"
    rule_name = "Контрольное число СНИЛС"

    if not snils_str:
        return RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status="WARN",
            message="Номер СНИЛС не указан",
            field_name="snils_number"
        )

    digits = re.sub(r'\D', '', str(snils_str))

    if len(digits) != 11:
        return RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status="FAIL",
            message=f"СНИЛС должен содержать ровно 11 цифр (получено: {len(digits)})",
            field_name="snils_number"
        )

    # Для номеров <= 001001998 контрольная сумма не рассчитывается
    base_num = int(digits[:9])
    check_num = int(digits[9:])

    if base_num <= 1001998:
        return RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status="PASS",
            message="СНИЛС из раннего диапазона (контрольное число не проверяется)",
            field_name="snils_number"
        )

    # Расчет контрольной суммы: d1*9 + d2*8 + ... + d9*1
    total_sum = sum(int(digits[i]) * (9 - i) for i in range(9))

    if total_sum < 100:
        expected_check = total_sum
    elif total_sum in (100, 101):
        expected_check = 0
    else:
        rem = total_sum % 101
        if rem < 100:
            expected_check = rem
        else:
            expected_check = 0

    if check_num == expected_check:
        formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
        return RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status="PASS",
            message=f"Контрольная сумма СНИЛС ({formatted}) корректна",
            field_name="snils_number"
        )
    else:
        return RuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status="FAIL",
            message=f"Неверное контрольное число СНИЛС (ожидалось: {expected_check:02d}, получено: {check_num:02d})",
            field_name="snils_number"
        )

