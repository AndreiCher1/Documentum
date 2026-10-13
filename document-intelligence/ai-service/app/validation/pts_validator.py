"""
Валидатор реквизитов Паспорта транспортного средства (ПТС) и VIN (ISO 3779).
"""

import re
from datetime import date
from typing import List, Optional
from app.validation.models import RuleResult


def validate_vin(vin_str: str) -> RuleResult:
    """
    Проверяет валидность VIN номера (17 символов, буквы кроме I, O, Q по стандарту ISO 3779).
    """
    clean_vin = re.sub(r'[^A-HJ-NPR-Z0-9]', '', (vin_str or "").upper())

    if not clean_vin:
        return RuleResult(
            rule_id="VIN_FORMAT",
            rule_name="Формат VIN",
            status="WARN",
            message="VIN номер не найден",
            field_name="vin"
        )

    if len(clean_vin) != 17:
        return RuleResult(
            rule_id="VIN_FORMAT",
            rule_name="Формат VIN",
            status="FAIL",
            message=f"VIN должен содержать ровно 17 символов (получено: {len(clean_vin)})",
            field_name="vin"
        )

    # Проверка на запрещённые буквы I, O, Q
    forbidden = [c for c in (vin_str or "").upper() if c in ('I', 'O', 'Q')]
    if forbidden:
        return RuleResult(
            rule_id="VIN_CHARACTERS",
            rule_name="Символы VIN",
            status="WARN",
            message=f"В VIN обнаружены недопустимые по стандарту ISO буквы ({', '.join(set(forbidden))})",
            field_name="vin"
        )

    return RuleResult(
        rule_id="VIN_VALID",
        rule_name="Стандарт VIN (ISO 3779)",
        status="PASS",
        message=f"VIN {clean_vin} соответствует международному стандарту ISO 3779 ✓",
        field_name="vin"
    )


def validate_pts_fields(fields_dict: dict) -> List[RuleResult]:
    """
    Проверяет согласованность полей ПТС: год выпуска, массы, мощности.
    """
    results: List[RuleResult] = []

    # 1. VIN
    if "vin" in fields_dict:
        results.append(validate_vin(fields_dict["vin"]))

    # 2. Год выпуска
    year_val = fields_dict.get("manufacture_year")
    if year_val:
        m = re.search(r'\b(19\d{2}|20\d{2})\b', year_val)
        if m:
            yr = int(m.group(1))
            cur_yr = date.today().year
            if 1950 <= yr <= cur_yr + 1:
                results.append(
                    RuleResult(
                        rule_id="PTS_YEAR_VALID",
                        rule_name="Год изготовления ТС",
                        status="PASS",
                        message=f"Год выпуска {yr} находится в допустимом диапазоне ✓",
                        field_name="manufacture_year"
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id="PTS_YEAR_VALID",
                        rule_name="Год изготовления ТС",
                        status="WARN",
                        message=f"Подозрительный год выпуска ТС: {yr}",
                        field_name="manufacture_year"
                    )
                )

    # 3. Соотношение масс (Разрешенная >= Масса без нагрузки)
    max_w_str = fields_dict.get("max_weight")
    unl_w_str = fields_dict.get("unladen_weight")
    if max_w_str and unl_w_str:
        mw = [int(s) for s in re.findall(r'\d+', max_w_str)]
        uw = [int(s) for s in re.findall(r'\d+', unl_w_str)]
        if mw and uw:
            m_weight = mw[0]
            u_weight = uw[0]
            if m_weight >= u_weight:
                results.append(
                    RuleResult(
                        rule_id="PTS_WEIGHT_LOGIC",
                        rule_name="Проверка масс ТС",
                        status="PASS",
                        message=f"Масса корректна: разрешенная ({m_weight} кг) >= масса без нагрузки ({u_weight} кг) ✓",
                        field_name="max_weight"
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id="PTS_WEIGHT_LOGIC",
                        rule_name="Проверка масс ТС",
                        status="WARN",
                        message=f"Нестыковка: разрешенная масса ({m_weight} кг) меньше массы без нагрузки ({u_weight} кг)",
                        field_name="max_weight"
                    )
                )

    return results

