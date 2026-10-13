"""
Модуль вопросно-ответной системы по документам (Document Q&A Engine with Visual Grounding).

Архитектурная роль:
- Позволяет пользователю задавать естественные вопросы на русском языке к любому документу
  (например: «Кто собственник?», «Какая сумма к оплате?», «Какой VIN номер?», «Когда выдан?», «Какой диагноз?»).
- Выполняет семантико-лексический анализ вопроса (Intent & Slot Extraction).
- Сопоставляет вопрос со структурированными полями документа (ExtractedField) и блоками OCR (OcrResult).
- Возвращает точный лаконичный ответ, контекстную цитату (snippet), степень уверенности и
  координаты Bounding Box [x1, y1, x2, y2] на конкретной странице для мгновенного подсвечивания в просмотрщике.
"""

import logging
import re
from typing import List, Optional, Tuple, Dict, Any

from app.api.schemas import OcrResult, ExtractedField, AskQuestionResponse

logger = logging.getLogger(__name__)


# Словарь семантических интентов и синонимов для вопросно-ответной системы
INTENT_SYNONYMS: Dict[str, Dict[str, Any]] = {
    "OWNER_PERSON": {
        "keywords": [
            "кто", "кому", "кем", "собственник", "владелец", "фио", "фамилия", "имя",
            "отчество", "гражданин", "гражданка", "получатель", "плательщик", "заказчик",
            "исполнитель", "покупатель", "пациент", "водитель", "директор", "руководитель"
        ],
        "field_names": [
            "full_name", "owner", "owner_name", "fio", "payer_name", "customer_name",
            "contractor_name", "patient_name", "driver_name", "director", "recipient"
        ],
        "text_anchors": [
            (r"([^\n\r,«\"]+)[,\s«\"]+именуем\w*\s+в\s+дальнейшем\s+[«\"]?заказчик", ["заказчик"]),
            (r"заказчик\s*:\s*([^\n\r,]+)", ["заказчик"]),
            (r"([^\n\r,«\"]+)[,\s«\"]+именуем\w*\s+в\s+дальнейшем\s+[«\"]?исполнитель", ["исполнитель"]),
            (r"исполнитель\s*:\s*([^\n\r,]+)", ["исполнитель"]),
            (r"собственник\s*[:\s]+([^\n\r,]+)", ["собственник"]),
            (r"владелец\s*[:\s]+([^\n\r,]+)", ["владелец"]),
            (r"фамилия\s*[:\s]+([^\n\r,]+)", ["фамилия", "фио"]),
            (r"паспорт\s+выдан\s*[:\s]+([^\n\r]+)", ["паспорт", "выдан"]),
            (r"пациент\s*[:\s]+([^\n\r,]+)", ["пациент"]),
            (r"водитель\s*[:\s]+([^\n\r,]+)", ["водитель"])
        ]
    },
    "VEHICLE_AUTO": {
        "keywords": [
            "vin", "вин", "шасси", "кузов", "рама", "марка", "модель", "госномер",
            "регистрационный", "знак", "двигатель", "мощность", "масса", "год выпуска",
            "автомобиль", "машина", "тс", "птс", "стс", "объем"
        ],
        "field_names": [
            "vin", "model", "vehicle_model", "body_number", "chassis_number", "engine_model",
            "power_hp", "engine_volume", "year_of_manufacture", "reg_number", "pts_series_number"
        ],
        "text_anchors": [
            r"идентификационный\s+номер(?:\s*\(vin\))?[:\s]*([A-HJ-NPR-Z0-9]{17})",
            r"\bvin[:\s]*([A-HJ-NPR-Z0-9]{17})",
            r"марка,?\s*модель\s*тс[:\s]*([^\n\r]+)",
            r"шасси\s*\(рама\)[:\s]*([^\n\r]+)",
            r"кузов\s*\(кабина\)[:\s]*([^\n\r]+)",
            r"мощность\s+двигателя[:\s]*([^\n\r]+)",
            r"год\s+изготовления\s*тс[:\s]*(\d{4})"
        ]
    },
    "FINANCIAL_AMOUNT": {
        "keywords": [
            "сколько", "сумма", "стоимость", "цена", "к оплате", "всего", "итог",
            "итого", "рублей", "руб", "ндс", "долг", "начислено", "оплачено", "тариф",
            "пеня", "перерасчет", "расход", "приход"
        ],
        "field_names": [
            "total_amount", "amount_to_pay", "total", "charged_amount", "sum", "vat_amount",
            "paid_amount", "debt_amount", "price"
        ],
        "text_anchors": [
            r"(?:общая\s+)?сумма\s*(?:договора)?\s*(?:составляет)?[:\s]*([\d\s]+(?:\([^\)]+\))?\s*(?:рублей|руб\.?|\u20bd)?)",
            r"итого\s+к\s+оплате[:\s]*([\d\s]+(?:[,\.]\d{2})?)",
            r"всего\s+к\s+оплате[:\s]*([\d\s]+(?:[,\.]\d{2})?)",
            r"сумма\s+к\s+оплате[:\s]*([\d\s]+(?:[,\.]\d{2})?)",
            r"начислено[:\s]*([\d\s]+(?:[,\.]\d{2})?)",
            r"итого[:\s]*([\d\s]+(?:[,\.]\d{2})?)",
            r"сумма[:\s]*([\d\s]+(?:[,\.]\d{2})?)"
        ]
    },
    "DATES_VALIDITY": {
        "keywords": [
            "когда", "дата", "срок", "выдан", "рождения", "действителен", "окончания",
            "период", "число", "год"
        ],
        "field_names": [
            "issue_date", "birth_date", "valid_until", "date", "registration_date",
            "period", "start_date", "end_date"
        ],
        "text_anchors": [
            r"дата\s+выдачи[:\s]*(\d{2}\.\d{2}\.\d{4})",
            r"дата\s+рождения[:\s]*(\d{2}\.\d{2}\.\d{4})",
            r"действителен\s+до[:\s]*(\d{2}\.\d{2}\.\d{4})",
            r"дата[:\s]*(\d{2}\.\d{2}\.\d{4})"
        ]
    },
    "IDENTIFIERS_CODES": {
        "keywords": [
            "номер", "код", "серия", "инн", "снилс", "бик", "паспорт", "подразделения",
            "расчетный", "лицевой", "счет", "кпп", "огрн"
        ],
        "field_names": [
            "series_number", "subdivision_code", "inn", "snils", "bik", "account_number",
            "corr_account", "account_no", "personal_account", "passport_number"
        ],
        "text_anchors": [
            r"код\s+подразделения[:\s]*(\d{3}[\-\s]?\d{3})",
            r"инн[:\s]*(\d{10}|\d{12})",
            r"снилс[:\s]*(\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2})",
            r"бик[:\s]*(\d{9})",
            r"лицевой\s+счет[:\s]*(\d+)",
            r"л[\/\.]?сч?[:\s]*(\d+)"
        ]
    },
    "ORGANIZATION_ISSUER": {
        "keywords": [
            "кем", "орган", "выдал", "уфмс", "мвд", "гибдд", "банк", "организация",
            "изготовитель", "компания", "фирма", "налоговая", "фнс"
        ],
        "field_names": [
            "issued_by", "manufacturer", "bank_name", "inn_recipient", "authority"
        ],
        "text_anchors": [
            r"паспорт\s+выдан[:\s]*([^\n\r]+)",
            r"орган\s+выдачи[:\s]*([^\n\r]+)",
            r"организация[\-\s]*изготовитель[:\s]*([^\n\r]+)",
            r"наименование\s+банка[:\s]*([^\n\r]+)"
        ]
    },
    "MEDICAL_HEALTH": {
        "keywords": [
            "диагноз", "анализ", "заключение", "показатель", "результат", "норма",
            "исследование", "глюкоза", "гемоглобин", "холестерин", "лейкоциты", "врач"
        ],
        "field_names": [
            "diagnosis", "medical_conclusion", "lab_result", "doctor"
        ],
        "text_anchors": [
            r"диагноз[:\s]*([^\n\r]+)",
            r"заключение[:\s]*([^\n\r]+)",
            r"результат[:\s]*([^\n\r]+)"
        ]
    }
}

STOP_WORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она",
    "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее",
    "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда",
    "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до",
    "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их", "чем",
    "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе", "под", "будет",
    "ж", "тогда", "кто", "этот", "того", "потому", "этого", "какой", "какая", "какое", "какие"
}


def _tokenize(text: str) -> List[str]:
    """Разбивает текст на очищенные токены строчными буквами."""
    tokens = re.findall(r'[а-яёa-z0-9]+', text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


class DocumentQaEngine:
    """Интеллектуальный движок ответов на вопросы по документу с привязкой к координатам."""

    def ask(
        self,
        question: str,
        ocr_results: List[OcrResult],
        fields: Optional[List[ExtractedField]] = None,
        document_type: Optional[str] = None
    ) -> AskQuestionResponse:
        """
        Отвечает на естественный вопрос пользователя по документу.
        """
        clean_q = (question or "").strip()
        if not clean_q:
            return AskQuestionResponse(
                status="empty_question",
                question="",
                answer="Вопрос не задан. Пожалуйста, напишите интересующий вас вопрос по документу.",
                confidence=0.0
            )

        q_tokens = _tokenize(clean_q)
        q_lower = clean_q.lower()
        logger.info(f"Document Q&A запрос: '{clean_q}', токенов: {len(q_tokens)}")

        # 1. Попытка сопоставления по структурированным полям документа
        best_field_match = self._match_against_fields(q_lower, q_tokens, fields or [])
        if best_field_match:
            field, score, reason = best_field_match
            if score >= 0.70:
                logger.info(f"Q&A найден точный ответ из структурированного поля: {field.display_name} = {field.value} (score={score:.2f})")
                snippet = f"{field.display_name}: {field.value}"
                return AskQuestionResponse(
                    status="success",
                    question=clean_q,
                    answer=field.value,
                    snippet=snippet,
                    confidence=round(score, 3),
                    bbox=field.bbox,
                    page=field.page,
                    matched_field=field.name,
                    message=f"Ответ найден в реквизите «{field.display_name}»"
                )

        # 2. Попытка сопоставления по семантическим текстовым якорям (Regex Text Anchors)
        anchor_match = self._match_by_text_anchors(q_lower, q_tokens, ocr_results)
        if anchor_match:
            ans_text, snippet, bbox, page, score = anchor_match
            if score >= 0.70:
                logger.info(f"Q&A найден ответ по текстовому якорю: {ans_text} (score={score:.2f})")
                return AskQuestionResponse(
                    status="success",
                    question=clean_q,
                    answer=ans_text,
                    snippet=snippet,
                    confidence=round(score, 3),
                    bbox=bbox,
                    page=page,
                    message="Ответ извлечён из строки документа"
                )

        # 3. Семантический поиск по блокам OCR (Sliding Window & Token Colocation)
        ocr_match = self._match_against_ocr_blocks(q_lower, q_tokens, ocr_results)
        if ocr_match:
            ans_text, snippet, bbox, page, score = ocr_match
            if score >= 0.45:
                logger.info(f"Q&A найден ответ в OCR блоках: {ans_text} (score={score:.2f})")
                return AskQuestionResponse(
                    status="success",
                    question=clean_q,
                    answer=ans_text,
                    snippet=snippet,
                    confidence=round(score, 3),
                    bbox=bbox,
                    page=page,
                    message="Ответ найден на основе текстового контекста документа"
                )

        # 4. Если точного ответа не найдено
        # Если есть хоть какое-то сопоставление по полям с невысоким баллом
        if best_field_match and best_field_match[1] >= 0.40:
            field, score, reason = best_field_match
            return AskQuestionResponse(
                status="partial",
                question=clean_q,
                answer=field.value,
                snippet=f"{field.display_name}: {field.value}",
                confidence=round(score * 0.8, 3),
                bbox=field.bbox,
                page=field.page,
                matched_field=field.name,
                message=f"Возможно, ответ содержится в поле «{field.display_name}»"
            )

        logger.info(f"Q&A не нашёл уверенного ответа на вопрос: '{clean_q}'")
        return AskQuestionResponse(
            status="not_found",
            question=clean_q,
            answer="В документе не найден прямой ответ на данный вопрос.",
            snippet=None,
            confidence=0.0,
            message="Попробуйте переформулировать вопрос или обратите внимание на вкладку «Извлечённые реквизиты»."
        )

    def _match_against_fields(
        self,
        q_lower: str,
        q_tokens: List[str],
        fields: List[ExtractedField]
    ) -> Optional[Tuple[ExtractedField, float, str]]:
        """Ищет совпадение вопроса со структурированными полями."""
        if not fields:
            return None

        best_field: Optional[ExtractedField] = None
        best_score = 0.0
        best_reason = ""

        # Вычисляем релевантность интентов
        matching_intents: List[str] = []
        for intent_name, intent_data in INTENT_SYNONYMS.items():
            for kw in intent_data["keywords"]:
                if kw in q_tokens or kw in q_lower:
                    matching_intents.append(intent_name)
                    break

        is_amount_question = any(w in q_lower for w in ["сумма", "стоимость", "цена", "к оплате", "сколько", "рублей"])
        is_date_question = any(w in q_lower for w in ["когда", "дата", "срок", "число", "период"])
        is_person_question = any(w in q_lower for w in ["кто", "кому", "кем", "собственник", "владелец", "фио", "заказчик", "исполнитель"])

        for field in fields:
            f_type = (field.field_type or "").upper()
            f_name_lower = (field.name or "").lower()
            f_disp_lower = (field.display_name or "").lower()

            # Защита: если вопрос про сумму, а поле — ДАТА, пропускаем
            if is_amount_question and not is_date_question and (f_type == "DATE" or "date" in f_name_lower or "дата" in f_disp_lower):
                continue
            # Защита: если вопрос про дату, а поле — СУММА, пропускаем
            if is_date_question and not is_amount_question and (f_type in ("AMOUNT", "MONEY", "PRICE") or "amount" in f_name_lower or "сумма" in f_disp_lower):
                continue
            # Защита: если вопрос про человека/организацию, а поле — ДАТА или СУММА, пропускаем
            if is_person_question and (f_type in ("DATE", "AMOUNT", "MONEY") or "date" in f_name_lower or "amount" in f_name_lower):
                continue

            f_disp_tokens = _tokenize(f_disp_lower)
            score = 0.0

            # 1. Прямое совпадение токенов из названия поля и вопроса
            overlap = set(q_tokens).intersection(set(f_disp_tokens))
            if overlap:
                score += 0.50 * len(overlap)

            # 2. Проверка соответствия семантическому интенту
            for intent_name in matching_intents:
                intent_fields = INTENT_SYNONYMS[intent_name]["field_names"]
                for ifield in intent_fields:
                    if ifield in f_name_lower:
                        score += 0.55
                        break

            # 3. Подстрочные совпадения в display_name (например "собственник" в "Собственник ТС")
            for token in q_tokens:
                if len(token) >= 4 and token in f_disp_lower:
                    score += 0.40

            # Повышаем уверенность, если само поле имеет высокую уверенность
            score = min(1.0, score) * (0.5 + 0.5 * (field.confidence or 0.8))

            if score > best_score:
                best_score = score
                best_field = field
                best_reason = f"Совпадение с полем {field.display_name}"

        if best_field and best_score >= 0.40:
            return best_field, best_score, best_reason
        return None

    def _match_by_text_anchors(
        self,
        q_lower: str,
        q_tokens: List[str],
        ocr_results: List[OcrResult]
    ) -> Optional[Tuple[str, str, List[int], int, float]]:
        """Ищет совпадение по регулярным шаблонам якорных фраз."""
        if not ocr_results:
            return None

        # 1. Специальное извлечение денежных сумм из блоков OCR
        if any(w in q_lower for w in ["сумма", "стоимость", "цена", "к оплате", "сколько", "руб"]):
            for block in ocr_results:
                b_text = block.text
                if any(kw in b_text.lower() for kw in ["сумма", "стоимость", "к оплате", "итого", "всего", "цена"]):
                    m = re.search(r'([\d\s]+(?:[,\.]\d{2})?\s*(?:\([^\)]+\)\s*)?(?:рублей|руб\.?|\u20bd))', b_text, re.IGNORECASE)
                    if not m:
                        m = re.search(r'(\d[\d\s]*(?:[,\.]\d{2})?)', b_text)
                    if m and len(m.group(1).strip()) >= 2:
                        ans_val = m.group(1).strip()
                        return ans_val, b_text, block.bbox, block.page, 0.94

        for intent_name, intent_data in INTENT_SYNONYMS.items():
            # Проверяем, относится ли вопрос к данному интенту
            matched_intent = any(kw in q_tokens or kw in q_lower for kw in intent_data["keywords"])
            if not matched_intent:
                continue

            patterns = intent_data.get("text_anchors", [])
            for item in patterns:
                if isinstance(item, tuple):
                    pattern, req_words = item
                    if not any(rw in q_lower for rw in req_words):
                        continue
                else:
                    pattern = item

                for block in ocr_results:
                    m = re.search(pattern, block.text, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip() if m.groups() else block.text.strip()
                        if val:
                            return val, block.text, block.bbox, block.page, 0.90

        return None

    def _match_against_ocr_blocks(
        self,
        q_lower: str,
        q_tokens: List[str],
        ocr_results: List[OcrResult]
    ) -> Optional[Tuple[str, str, List[int], int, float]]:
        """
        Ищет наиболее релевантный текстовый блок по совпадению ключевых слов и близости значений.
        """
        if not ocr_results or not q_tokens:
            return None

        best_block: Optional[OcrResult] = None
        best_score = 0.0
        best_ans = ""
        best_snippet = ""

        total_blocks = len(ocr_results)
        for i, block in enumerate(ocr_results):
            b_text = block.text.strip()
            b_tokens = _tokenize(b_text)
            overlap = set(q_tokens).intersection(set(b_tokens))
            if not overlap:
                continue

            # Базовый балл совпадения ключевых слов
            score = 0.35 * (len(overlap) / max(1, len(q_tokens))) + 0.25 * (len(overlap) / max(1, len(b_tokens)))

            # Если блок содержит двоеточие или дефис (формат "Ключ: Значение")
            if ":" in b_text or "-" in b_text:
                parts = re.split(r'[:\-]', b_text, maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    score += 0.30
                    ans_candidate = parts[1].strip()
                    if score > best_score:
                        best_score = score
                        best_ans = ans_candidate
                        best_snippet = b_text
                        best_block = block
                        continue

            # Если значение может находиться в следующем соседнем блоке (по координатам или порядку)
            if i + 1 < total_blocks:
                next_b = ocr_results[i + 1]
                # Если следующий блок на той же странице и близко по Y
                if next_b.page == block.page and abs(next_b.bbox[1] - block.bbox[1]) < 60:
                    ans_candidate = next_b.text.strip()
                    combined_score = score + 0.25
                    if combined_score > best_score:
                        best_score = combined_score
                        best_ans = ans_candidate
                        best_snippet = f"{b_text} {next_b.text}"
                        # Объединяем bounding boxes
                        merged_bbox = [
                            min(block.bbox[0], next_b.bbox[0]),
                            min(block.bbox[1], next_b.bbox[1]),
                            max(block.bbox[2], next_b.bbox[2]),
                            max(block.bbox[3], next_b.bbox[3]),
                        ]
                        best_block = OcrResult(
                            text=best_snippet,
                            confidence=max(block.confidence, next_b.confidence),
                            bbox=merged_bbox,
                            page=block.page
                        )
                        continue

            # Если сам блок содержит ответ
            if score > best_score:
                best_score = score
                best_ans = b_text
                best_snippet = b_text
                best_block = block

        if best_block and best_score >= 0.40:
            return best_ans, best_snippet, best_block.bbox, best_block.page, min(0.95, best_score)

        return None


# Единственный синглтон-экземпляр
document_qa_engine = DocumentQaEngine()
