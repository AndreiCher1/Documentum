"""
Модуль умной коррекции и додумывания слов OCR (Spell Corrector & Lexical Normalizer).

Функции:
1. Устранение межъязыковых омоглифов (латиница <-> кириллица).
2. Исправление опечаток по словарю терминов российских документов (ПТС, паспорта, счета, договоры).
3. Восстановление разорванных или искажённых слов (например: 'AApec' -> 'Адрес', 'БВНЗИНОВЫЙ' -> 'БЕНЗИНОВЫЙ').
4. Опциональный интерфейс для вызова LLM с промптом по додумыванию контекста.
"""

import re
import logging
from typing import List, Tuple, Optional
from app.api.schemas import OcrResult

logger = logging.getLogger(__name__)

# Таблица замены латинских букв-двойников на русские (в русском контексте)
LATIN_TO_CYRILLIC_HOMOGLYPHS = {
    'A': 'А', 'a': 'а',
    'B': 'В',
    'C': 'С', 'c': 'с',
    'E': 'Е', 'e': 'е',
    'H': 'Н',
    'K': 'К', 'k': 'к',
    'M': 'М', 'm': 'м',
    'O': 'О', 'o': 'о',
    'P': 'Р', 'p': 'р',
    'T': 'Т',
    'X': 'Х', 'x': 'х',
    'y': 'у',
}

# Частотные термины российских документов (эталонный лексикон)
DOCUMENT_LEXICON = [
    # Реквизиты и адресная часть
    "Адрес", "Паспорт", "Транспортного", "Средства", "Собственник", "Наименование",
    "Идентификационный", "Двигатель", "Бензиновый", "Дизельный", "Категория",
    "Изготовитель", "Разрешенная", "Максимальная", "Масса", "Таможня", "Подпись",
    "Организация", "Руководитель", "Бухгалтер", "Сумма", "Количество", "Цена",
    "Товары", "Услуги", "Договор", "Счёт", "Накладная", "Акт", "Серия", "Номер",
    "Выдан", "Подразделение", "Код", "Российская", "Федерация", "Россия",
    "Свидетельство", "Регистрация", "Особые", "Отметки", "Страна", "Вывоза",
    "Экологический", "Класс", "Шасси", "Кузов", "Прицеп", "Мощность", "Объем",
    "Нагрузки", "Продажи", "Передачи", "Документ", "Право", "Собственности",
    "Прежнего", "Настоящего", "Государственный", "Регистрационный", "Знак",
    "Центральная", "Акцизная", "Таможня", "Инспекция", "Отделение", "Отделом",
    "Всего", "Итого", "Оплата", "Оплате", "Оплату", "Рублей", "Копеек", "НДС", "Без", "Ставка"
]

# Прямые правила замены частых артефактов OCR
DIRECT_REPLACEMENTS = {
    r'\b[Aa][Aa]pec\b': 'Адрес',
    r'\b[Aa]pec\b': 'Адрес',
    r'\bАДРес\b': 'Адрес',
    r'\bОсодые\b': 'Особые',
    r'\bОтрана\b': 'Страна',
    r'\bБВНЗИНОВЫЙ\b': 'БЕНЗИНОВЫЙ',
    r'\bнacпopтa\b': 'паспорта',
    r'\bПЯТЬIЙ\b': 'ПЯТЫЙ',
    r'\bдBИГАтЕЛ\b': 'ДВИГАТЕЛЬ',
    r'\bСобственнИK\b': 'Собственник',
    r'\bПокупатeль\b': 'Покупатель',
    r'\bПоставщик\b': 'Поставщик',
    r'\b[Вв]ылачи\b': 'выдачи',
    r'\b[Вв]ылача\b': 'выдача',
    r'\b[Фф]амианя\b': 'фамилия',
    r'\b[Фф]амиаия\b': 'фамилия',
    r'\bΔara\b': 'Дата',
    r'\bΔата\b': 'Дата',
    r'\b[Кк]од\s+подразделение\b': 'Код подразделения',
}


def _levenshtein(s1: str, s2: str) -> int:
    """Вычисление расстояния Левенштейна между двумя строками."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def normalize_homoglyphs(word: str) -> str:
    """
    Заменяет латинские омоглифы на кириллицу, если слово преимущественно русское.
    Например: 'AApec' -> 'ААрес', 'Poccия' -> 'Россия'.
    """
    cyr_count = sum(1 for c in word if 'а' <= c.lower() <= 'я' or c.lower() == 'ё')
    lat_count = sum(1 for c in word if 'a' <= c.lower() <= 'z')

    # Если слово явно русское с вкраплениями латиницы или похоже на адрес
    if cyr_count > 0 or word.lower() in ('aapec', 'apec', 'aapec:'):
        chars = [LATIN_TO_CYRILLIC_HOMOGLYPHS.get(c, c) for c in word]
        return "".join(chars)
    return word


def correct_word_by_lexicon(word: str, max_dist: int = 1) -> str:
    """
    Ищет ближайшее слово в эталонном лексиконе документов.
    """
    clean_w = re.sub(r'[^\w\s]', '', word)
    if len(clean_w) < 4:
        return word

    is_upper = clean_w.isupper()
    is_title = clean_w.istitle()

    best_match = None
    min_d = max_dist + 1

    for lex in DOCUMENT_LEXICON:
        if abs(len(lex) - len(clean_w)) > max_dist:
            continue
        d = _levenshtein(clean_w.lower(), lex.lower())
        if d < min_d:
            min_d = d
            best_match = lex

    if best_match and min_d <= max_dist:
        # Сохраняем исходный регистр
        punct_tail = word[len(clean_w):] if word.endswith((':', '.', ',')) else ''
        if is_upper:
            return best_match.upper() + punct_tail
        elif is_title:
            return best_match.capitalize() + punct_tail
        else:
            return best_match.lower() + punct_tail

    return word


def restore_monetary_commas(text: str) -> str:
    """
    Восстанавливает пропущенную запятую в суммах и тарифах (например: '81 36' -> '81,36', '162 72 руб' -> '162,72 руб', 'py6. 8136' -> 'руб. 81,36').
    """
    if not text:
        return text

    # 1. Перед 'руб', 'руб.', 'р.', 'коп': '81 36 руб.' -> '81,36 руб.'
    text = re.sub(r'\b(\d{1,7})\s+(\d{2})\s*(руб|р\.?|\u20bd|py6|рублей)\b', r'\1,\2 \3', text, flags=re.IGNORECASE)

    # 1b. После 'руб', 'руб.', 'р.', 'py6': 'руб. 81 36' -> 'руб. 81,36' или 'руб. 8136' -> 'руб. 81,36'
    text = re.sub(r'\b(руб|р\.?|\u20bd|py6)\.?\s*(\d{1,6})\s+(\d{2})\b', r'\1. \2,\3', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(руб|р\.?|\u20bd|py6)\.?\s*(\d{2,4})(\d{2})\b', r'\1. \2,\3', text, flags=re.IGNORECASE)

    # 2. Рядом с денежными маркерами: 'Начислено: 81 36' -> 'Начислено: 81,36'
    text = re.sub(r'(цена|начислено|оплачено|перерасч[её]т|долг|аванс|итого|всего|к\s*оплат\w*|сумма|тариф)[:\s]+(\d{1,7})\s+(\d{2})\b', r'\1: \2,\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(цена|начислено|оплачено|перерасч[её]т|долг|аванс|итого|всего|к\s*оплат\w*|сумма|тариф)[:\s]+(\d{2,4})(\d{2})\b', r'\1: \2,\3', text, flags=re.IGNORECASE)

    # 3. Число из 1-6 цифр пробел 2 цифры в изолированном блоке ячейки (например '81 36' -> '81,36')
    text = re.sub(r'^\s*(\d{1,6})\s+(\d{2})\s*$', r'\1,\2', text)

    return text


class SpellCorrector:
    """Интеллектуальный корректор текста и OCR-блоков."""

    def __init__(self, prompt_template: Optional[str] = None):
        self.prompt_template = prompt_template or (
            "Ты эксперт по распознаванию документов. "
            "Исправь ошибки OCR, восстанови слова русского языка (например: AApec -> Адрес, БВНЗИНОВЫЙ -> БЕНЗИНОВЫЙ). "
            "Сохраняй структуру и цифры."
        )

    def correct_text(self, text: str) -> str:
        """
        Комплексная коррекция строки:
        1. Восстановление пропущенных запятых в суммах и ценах.
        2. Применение прямых regex правил (AApec -> Адрес).
        3. Нормализация омоглифов.
        4. Пословное сравнение с лексиконом.
        """
        if not text:
            return text

        # 1. Восстановление пропущенных запятых в суммах
        result = restore_monetary_commas(text)

        # 2. Прямые замены
        for pattern, replacement in DIRECT_REPLACEMENTS.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # 2. Пословная обработка
        words = result.split()
        corrected_words = []
        for w in words:
            # Омоглифы
            norm_w = normalize_homoglyphs(w)
            # Додумывание по словарю
            fixed_w = correct_word_by_lexicon(norm_w, max_dist=1)
            corrected_words.append(fixed_w)

        return " ".join(corrected_words)

    def correct_blocks(self, ocr_results: List[OcrResult]) -> List[OcrResult]:
        """
        Применяет умную коррекцию ко всем блокам OCR.
        """
        corrected = []
        for b in ocr_results:
            new_text = self.correct_text(b.text)
            if new_text != b.text:
                logger.info(f"Коррекция OCR: '{b.text}' -> '{new_text}' [bbox={b.bbox}]")
                corrected.append(
                    OcrResult(
                        text=new_text,
                        confidence=min(1.0, b.confidence + 0.05),
                        bbox=b.bbox,
                        page=b.page
                    )
                )
            else:
                corrected.append(b)
        return corrected


# Синглтон корректора
spell_corrector = SpellCorrector()

