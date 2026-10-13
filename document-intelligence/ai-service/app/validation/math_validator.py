"""
Математический валидатор табличных расчётов, сумм и НДС (Mathematical & Table Validator).
"""

import re
from typing import List, Optional
from app.validation.models import RuleResult
from app.table.models import ExtractedTable


def _parse_float(val: str) -> Optional[float]:
    """Преобразует строку с числом/суммой в float."""
    if not val:
        return None
    # Очищаем от пробелов, букв 'руб', заменяем запятую на точку
    cleaned = re.sub(r'[^\d\.,\-]', '', str(val)).replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def validate_table_mathematics(table: ExtractedTable) -> List[RuleResult]:
    """
    Проверяет математическое равенство для строк таблицы:
    Количество * Цена = Сумма (с допуском 0.05 руб.).
    """
    results: List[RuleResult] = []
    if not table or not table.rows or len(table.rows) == 0:
        return results

    headers = [h.lower() for h in table.headers]
    qty_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ('кол', 'к-во', 'qty'))), None)
    price_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ('цен', 'тариф', 'price'))), None)
    sum_idx = next((i for i, h in enumerate(headers) if any(k in h for k in ('сумм', 'всего', 'amount', 'стоим'))), None)

    if qty_idx is None or price_idx is None or sum_idx is None:
        return results

    row_discrepancies = 0
    checked_rows = 0

    for row_num, row in enumerate(table.rows, start=1):
        if len(row) <= max(qty_idx, price_idx, sum_idx):
            continue

        q = _parse_float(row[qty_idx])
        p = _parse_float(row[price_idx])
        s = _parse_float(row[sum_idx])

        if q is not None and p is not None and s is not None and q > 0 and p > 0:
            checked_rows += 1
            calc_s = q * p
            diff = abs(calc_s - s)

            if diff > 0.05:
                row_discrepancies += 1
                results.append(
                    RuleResult(
                        rule_id=f"TABLE_ROW_{row_num}_CALC",
                        rule_name=f"Расчёт строки {row_num}",
                        status="WARN",
                        message=f"Строка {row_num}: {q} × {p:,.2f} = {calc_s:,.2f}, но в строке указано {s:,.2f} (разница {diff:.2f} руб.)",
                        field_name="table"
                    )
                )

    if checked_rows > 0:
        if row_discrepancies == 0:
            results.append(
                RuleResult(
                    rule_id="TABLE_ROWS_CALC_OK",
                    rule_name="Математика строк таблицы",
                    status="PASS",
                    message=f"Все проверенные строки ({checked_rows} шт.) сошлись: Кол-во × Цена = Сумма ✓",
                    field_name="table"
                )
            )

    return results


def validate_total_consistency(table: Optional[ExtractedTable], extracted_total: Optional[str]) -> List[RuleResult]:
    """
    Сверяет сумму строк таблицы с итоговой суммой документа к оплате.
    """
    results: List[RuleResult] = []
    if not table or not table.summary or not extracted_total:
        return results

    if isinstance(table.summary, dict):
        table_total = table.summary.get('calculated_total')
    else:
        table_total = getattr(table.summary, 'calculated_total', None)
    doc_total = _parse_float(extracted_total)

    if table_total is not None and doc_total is not None:
        diff = abs(table_total - doc_total)
        if diff <= 0.05:
            results.append(
                RuleResult(
                    rule_id="TOTAL_CONSISTENCY",
                    rule_name="Сверка итоговой суммы",
                    status="PASS",
                    message=f"Сумма строк таблицы ({table_total:,.2f} руб.) полностью совпадает с итогом к оплате ({doc_total:,.2f} руб.) ✓",
                    field_name="total_amount"
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id="TOTAL_CONSISTENCY",
                    rule_name="Сверка итоговой суммы",
                    status="WARN",
                    message=f"Расхождение: сумма строк таблицы {table_total:,.2f} руб. отличается от итога {doc_total:,.2f} руб. (разница {diff:,.2f} руб.)",
                    field_name="total_amount"
                )
            )

    return results

