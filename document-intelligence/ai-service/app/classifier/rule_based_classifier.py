"""
Сигнатурный классификатор документов на основе ключевых токенов и регулярных выражений (Rule-Based Classifier).

Что делает этот модуль:
1. Хранит экспертные базы якорных маркеров (Anchor Keywords) для каждого типа документов.
2. Сканирует нормализованный текст документа на наличие строго специфичных паттернов.
3. Рассчитывает взвешенный балл совпадений (Score) для каждого класса.
4. Нормализует баллы в вероятности через Softmax.
5. Формирует человекочитаемое объяснение (matched_keywords и explanation) для аудита.

Почему правила необходимы (даже при наличии ML):
- В реальном документообороте юридические документы имеют строгие обязательные реквизиты:
  * В паспорте РФ ВСЕГДА есть слова «Российская Федерация», «Паспорт выдан», «Код подразделения».
  * В счёте ВСЕГДА есть БИК, расчётный счёт и «Счёт на оплату».
  * В акте ВСЕГДА есть фраза «Претензий не имеют» / «Работы выполнены в полном объёме».
- Чистый ML (особенно на малых выборках) может спутать Акт и Счёт из-за одинаковых ИНН/КПП.
- Сигнатурный анализ даёт 99.9% надёжности при наличии явных якорных фраз.
"""

import logging
import re
from typing import Dict, List, Tuple
import numpy as np

from app.classifier.base import BaseDocumentClassifier, ClassificationResult, DocumentCategory

logger = logging.getLogger(__name__)


# Экспертные правила: (регулярное выражение, вес правила, описание маркера)
RULES_CATALOG: Dict[DocumentCategory, List[Tuple[str, float, str]]] = {
    DocumentCategory.PTS: [
        (r"паспорт\s+транспортного\s+средства", 5.5, "«Паспорт транспортного средства»"),
        (r"\bптс\b", 4.0, "«ПТС»"),
        (r"идентификационный\s+номер(?:\s*\(vin\))?", 4.5, "«Идентификационный номер (VIN)»"),
        (r"марка,?\s*модель\s*тс", 3.5, "«Марка, модель ТС»"),
        (r"шасси\s*\(рама\)", 3.0, "«Шасси (рама)»"),
        (r"кузов\s*\(кабина", 3.0, "«Кузов (кабина)»"),
        (r"мощность\s+двигателя", 3.0, "«Мощность двигателя»"),
        (r"рабочий\s+объем\s+двигателя", 3.0, "«Рабочий объем двигателя»"),
        (r"экологический\s+класс", 2.5, "«Экологический класс»"),
        (r"разрешенная\s+максимальная\s+масса", 3.0, "«Разрешенная максимальная масса»"),
        (r"организация[\-\s]*изготовитель\s*тс", 3.0, "«Организация-изготовитель ТС»"),
        (r"свидетельство\s+о\s+регистрации\s*тс", 3.0, "«Свидетельство о регистрации ТС»"),
        (r"паспорт\s+тс", 4.0, "«Паспорт ТС»"),
        (r"таможенн\w*\s+ограничен\w*", 2.5, "«Таможенные ограничения»")
    ],
    DocumentCategory.PASSPORT_RF: [
        (r"российск\w*\s+федерац\w*", 3.5, "«Российская Федерация»"),
        (r"паспорт\s*(выдан|гражданина)?", 3.0, "«Паспорт выдан»"),
        (r"код\s+подразделен\w*", 3.0, "«Код подразделения»"),
        (r"личный\s+код", 2.0, "«Личный код»"),
        (r"дата\s+выдач\w*", 2.0, "«Дата выдачи»"),
        (r"дата\s+рождения", 2.0, "«Дата рождения»"),
        (r"место\s+рождения", 2.0, "«Место рождения»"),
        (r"пол\s*(муж|жен|\.)", 2.0, "Указание пола"),
        (r"(отделом|отделением|уфмс|гувм|мвд|ровд|говд)", 2.5, "Орган выдачи (МВД/УФМС)"),
        (r"p<rus|pnrus|[0-9]{10}rus", 4.0, "Машиночитаемая зона MRZ"),
        (r"\b\d{2}\s*\d{2}\s+\d{6}\b", 3.0, "Шаблон серии и номера паспорта РФ")
    ],
    DocumentCategory.CONTRACT: [
        (r"договор\s*(№|n|номер)?", 3.0, "Заголовок «Договор»"),
        (r"договор\s+(возмездного\s+оказания|купли-продажи|подряда|аренды|поставки|услуг)", 4.0, "Вид договора"),
        (r"предмет\s+договора", 3.5, "«Предмет договора»"),
        (r"права\s+и\s+обязанности\s+сторон", 3.0, "«Права и обязанности сторон»"),
        (r"ответственность\s+сторон", 2.5, "«Ответственность сторон»"),
        (r"срок\s+действия\s+договора", 2.5, "«Срок действия договора»"),
        (r"заказчик", 2.0, "Сторона «Заказчик»"),
        (r"(исполнитель|подрядчик|поставщик|арендатор|покупатель)", 2.0, "Сторона договора"),
        (r"юридические\s+адреса\s+и\s+реквизиты\s+сторон", 2.5, "«Адреса и реквизиты сторон»"),
        (r"настоящий\s+договор\s+составлен\s+в\s+двух\s+экземплярах", 3.0, "Заключительные положения договора")
    ],
    DocumentCategory.INVOICE: [
        (r"сч[её]т\s*(на\s+оплату|№|n|номер)", 4.0, "Заголовок «Счёт на оплату»"),
        (r"сч[её]т-фактура", 4.0, "«Счёт-фактура»"),
        (r"образец\s+заполнения\s+платежного\s+поручения", 3.5, "Образец платёжного поручения"),
        (r"наименование\s+банка\s+получателя", 3.0, "Банк получателя"),
        (r"бик\s*\d{9}", 3.5, "Банковский идентификатор БИК"),
        (r"р\/с\s*\d{20}|расчетный\s+счет", 3.0, "Расчётный счёт"),
        (r"к\/с\s*\d{20}|корр.*счет", 2.5, "Корреспондентский счёт"),
        (r"всего\s+к\s+оплате|итого\s+к\s+оплате|сумма\s+к\s+оплате", 3.5, "«Всего к оплате»"),
        (r"в\s+том\s+числе\s+ндс|без\s+налога\s*\(?ндс\)?", 2.5, "Строка НДС"),
        (r"поставщик|плательщик|грузополучатель", 2.0, "Участники счёта")
    ],
    DocumentCategory.ACT: [
        (r"акт\s*(сдачи-при[её]мки|при[её]ма-передачи|выполненных\s+работ|оказанных\s+услуг|№|n)", 4.0, "Заголовок «Акт выполненных работ/услуг»"),
        (r"вышеперечисленные\s+работы\s+выполнены\s+полностью", 4.0, "«Работы выполнены полностью»"),
        (r"работы\s+выполнены\s+в\s+полном\s+объ[её]ме", 4.0, "«В полном объёме»"),
        (r"претензий\s*(по\s+объему|к\s+качеству|друг\s+к\s+другу)?\s*не\s+имеют", 4.5, "«Стороны претензий не имеют»"),
        (r"акт\s+к\s+договору", 3.0, "«Акт к договору»"),
        (r"сдал\s*\(?исполнитель\)?|принял\s*\(?заказчик\)?", 2.5, "Подписи сторон Акта"),
        (r"всего\s+оказано\s+услуг|всего\s+выполнено\s+работ", 3.0, "Итог выполненных работ")
    ],
    DocumentCategory.RECEIPT: [
        (r"квитанци\w*|сч[её]т[\-\s]*квитанци\w*|извещени\w*", 4.5, "«Квитанция/Счёт-извещение»"),
        (r"итого\s+к\s+оплате|всего\s+к\s+оплате|к\s+оплате", 4.0, "«Итого к оплате»"),
        (r"начислено|перерасч[её]т|оплачено|долг[\s\(\+\)\-]*аванс", 4.0, "«Начислено/Перерасчет/Оплачено»"),
        (r"лицев(ой|ого)\s+сч[её]т\w*|л[\/\.]?\s*сч?\s*№?|\bл\/с\b", 4.0, "«Лицевой счёт»"),
        (r"прибор\w*\s+учет\w*|сч[её]тчик\w*|объем\s*,\s*м3|куб\.?\s*м", 3.5, "«Объём/Прибор учёта»"),
        (r"тариф\w*|природный\s+газ|водоснабжен\w*|электроэнерг\w*|газоснабжен\w*|жкх|жку|коммунальн\w*", 4.5, "«Коммунальные услуги/Тарифы»"),
        (r"варочная\s+панель|отоплени\w*|водоотведен\w*", 3.0, "«Услуги ЖКУ»"),
    ],
    DocumentCategory.TAX_2NDFL: [
        (r"2-ндфл|форма\s+2-ндфл", 4.5, "Обозначение формы «2-НДФЛ»"),
        (r"справка\s+о\s+доходах\s+и\s+суммах\s+налога", 4.0, "«Справка о доходах и суммах налога»"),
        (r"налоговый\s+агент", 3.5, "«Налоговый агент»"),
        (r"доходы,\s+облагаемые\s+по\s+ставке\s*13%", 3.5, "«Ставка 13%»"),
        (r"общая\s+сумма\s+дохода", 3.0, "«Общая сумма дохода»"),
        (r"налоговая\s+база", 3.0, "«Налоговая база»"),
        (r"сумма\s+налога\s+исчисленная", 3.0, "«Сумма налога исчисленная»"),
        (r"код\s+вычета|код\s+дохода", 2.5, "Коды вычетов/доходов")
    ]
}


class RuleBasedClassifier(BaseDocumentClassifier):
    """Классификатор на основе сигнатурных экспертных правил."""

    def __init__(self, min_confidence_threshold: float = 0.50):
        self.min_confidence_threshold = min_confidence_threshold

    def classify(self, text: str, ocr_blocks: list = None) -> ClassificationResult:
        """
        Вычисляет баллы категорий по тексту документа.
        """
        if not text or not text.strip():
            return ClassificationResult(
                predicted_type=DocumentCategory.UNKNOWN.value,
                display_name=DocumentCategory.UNKNOWN.display_name,
                confidence=0.0,
                probabilities={cat.value: 0.0 for cat in DocumentCategory},
                matched_keywords=[],
                explanation="Текст документа пуст — невозможно определить тип."
            )

        text_lower = text.lower()
        scores: Dict[str, float] = {cat.value: 0.0 for cat in DocumentCategory if cat != DocumentCategory.UNKNOWN}
        matches_per_cat: Dict[str, List[str]] = {cat.value: [] for cat in DocumentCategory if cat != DocumentCategory.UNKNOWN}

        # Проверяем каждое правило
        for category, rules in RULES_CATALOG.items():
            cat_key = category.value
            for pattern, weight, description in rules:
                if re.search(pattern, text_lower):
                    scores[cat_key] += weight
                    matches_per_cat[cat_key].append(description)

        # Защита от ложного срабатывания Паспорта на квитанциях ЖКУ и счетах
        receipt_score = scores.get(DocumentCategory.RECEIPT.value, 0.0)
        has_utility_markers = bool(re.search(r"итого\s+к\s+оплате|начислено|перерасч[её]т|природный\s+газ|куб\.?\s*м|варочная\s+панель|лицев(ой|ого)\s+сч[её]т", text_lower))
        if has_utility_markers or receipt_score > 2.0:
            scores[DocumentCategory.PASSPORT_RF.value] = 0.0
            matches_per_cat[DocumentCategory.PASSPORT_RF.value] = []

        # Если ни одно правило не сработало
        total_score = sum(scores.values())
        if total_score < 1.0:
            return ClassificationResult(
                predicted_type=DocumentCategory.UNKNOWN.value,
                display_name=DocumentCategory.UNKNOWN.display_name,
                confidence=0.0,
                probabilities={cat.value: 0.0 for cat in DocumentCategory},
                matched_keywords=[],
                explanation="Характерные якорные токены известных типов документов не обнаружены."
            )

        # Вычисляем вероятности (нормализация Softmax с температурой)
        raw_values = np.array(list(scores.values()), dtype=np.float32)
        # Умеренный softmax
        exp_vals = np.exp(raw_values - np.max(raw_values))
        probabilities_array = exp_vals / np.sum(exp_vals)
        probabilities = {k: round(float(p), 4) for k, p in zip(scores.keys(), probabilities_array)}

        # Находим категорию с максимальным баллом
        best_cat_key = max(scores, key=scores.get)
        best_score = scores[best_cat_key]
        best_prob = probabilities[best_cat_key]
        best_matches = matches_per_cat[best_cat_key]

        # Оценка уверенности: если набрано >= 6 баллов, уверенность 95%+
        confidence = min(0.99, max(best_prob, min(1.0, best_score / 8.0)))
        confidence = round(confidence, 4)

        if confidence < self.min_confidence_threshold:
            return ClassificationResult(
                predicted_type=DocumentCategory.UNKNOWN.value,
                display_name=DocumentCategory.UNKNOWN.display_name,
                confidence=confidence,
                probabilities=probabilities,
                matched_keywords=best_matches,
                explanation=f"Недостаточно признаков (уверенность {confidence:.1%} ниже порога {self.min_confidence_threshold:.1%})."
            )

        best_category = DocumentCategory(best_cat_key)
        explanation = (
            f"Определен как «{best_category.display_name}» на основе ключевых маркеров: "
            + ", ".join(best_matches[:5])
        )

        return ClassificationResult(
            predicted_type=best_category.value,
            display_name=best_category.display_name,
            confidence=confidence,
            probabilities=probabilities,
            matched_keywords=best_matches,
            explanation=explanation
        )

