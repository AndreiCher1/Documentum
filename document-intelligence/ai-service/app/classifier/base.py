"""
Базовые абстракции и типы классификации документов.

Что делает этот модуль:
- Определяет поддерживаемые типы документов (PASSPORT_RF, CONTRACT, INVOICE, ACT, TAX_2NDFL, UNKNOWN).
- Описывает структуру результата классификации (ClassificationResult) с вероятностями,
  сработавшими якорными маркерами и понятным объяснением для человека (Explainable AI).
- Задаёт контракт BaseDocumentClassifier.

Почему это важно (Архитектурный принцип Explainability):
- В корпоративных системах (банки, бухгалтерия, документооборот) классификатор не должен
  быть «чёрным ящиком».
- Аудитор или пользователь должен видеть: «Документ классифицирован как ПАСПОРТ РФ с точностью 98%,
  потому что найдены якоря: "российская федерация", "паспорт выдан", "код подразделения"».
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class DocumentCategory(str, Enum):
    """Категории документов, распознаваемые системой."""
    PASSPORT_RF = "PASSPORT_RF"
    PTS = "PTS"
    STS = "STS"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    SNILS = "SNILS"
    INN = "INN"
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    ACT = "ACT"
    CASH_RECEIPT = "CASH_RECEIPT"
    BANK_STATEMENT = "BANK_STATEMENT"
    TECH_PASSPORT = "TECH_PASSPORT"
    MEDICAL_REPORT = "MEDICAL_REPORT"
    LEGAL_HR = "LEGAL_HR"
    TAX_2NDFL = "TAX_2NDFL"
    UNKNOWN = "UNKNOWN"

    @property
    def display_name(self) -> str:
        """Русскоязычное название категории для UI."""
        names = {
            self.PASSPORT_RF: "Паспорт РФ",
            self.PTS: "Паспорт ТС (ПТС)",
            self.STS: "Свидетельство о регистрации ТС (СТС)",
            self.DRIVER_LICENSE: "Водительское удостоверение",
            self.SNILS: "Страховое свидетельство (СНИЛС)",
            self.INN: "Свидетельство ИНН",
            self.CONTRACT: "Договор",
            self.INVOICE: "Счёт на оплату / УПД",
            self.RECEIPT: "Квитанция / Счёт ЖКУ",
            self.ACT: "Акт выполненных работ",
            self.CASH_RECEIPT: "Кассовый чек",
            self.BANK_STATEMENT: "Банковская выписка",
            self.TECH_PASSPORT: "Технический паспорт оборудования",
            self.MEDICAL_REPORT: "Медицинские анализы / Заключение",
            self.LEGAL_HR: "Судебное решение / Приказ / Заявление",
            self.TAX_2NDFL: "Справка 2-НДФЛ",
            self.UNKNOWN: "Не определён"
        }
        return names.get(self, "Не определён")


@dataclass
class ClassificationResult:
    """Результат классификации документа."""
    predicted_type: str                   # Код категории (например, PASSPORT_RF)
    display_name: str                     # Название на русском (Паспорт РФ)
    confidence: float                     # Уверенность от 0.0 до 1.0
    probabilities: Dict[str, float]       # Распределение вероятностей по всем классам
    matched_keywords: List[str]           # Якорные токены, вызвавшие срабатывание
    explanation: str                      # Текстовое обоснование решения для аудита


class BaseDocumentClassifier(ABC):
    """Абстрактный интерфейс классификатора документов."""

    @abstractmethod
    def classify(self, text: str, ocr_blocks: Optional[list] = None) -> ClassificationResult:
        """
        Классифицирует документ по распознанному тексту и/или блокам OCR.

        :param text: Полный распознанный текст документа в виде одной строки.
        :param ocr_blocks: Список блоков OcrBlock с координатами и страницами.
        :return: ClassificationResult с определённой категорией и обоснованием.
        """
        pass

