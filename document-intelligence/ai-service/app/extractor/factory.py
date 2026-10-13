"""
Фабрика экстракторов полей документов (Information Extraction Factory).

Использует паттерн Factory Method для создания и кэширования специализированных
экстракторов под конкретный тип классифицированного документа.
"""

from typing import Dict
from app.extractor.base import BaseFieldExtractor
from app.extractor.passport_rf import PassportRfExtractor
from app.extractor.invoice import InvoiceExtractor
from app.extractor.contract import ContractExtractor
from app.extractor.act import ActExtractor
from app.extractor.tax_2ndfl import Tax2NdflExtractor
from app.extractor.pts import PtsExtractor
from app.extractor.receipt import ReceiptExtractor
from app.extractor.generic import GenericFieldExtractor

_extractors_cache: Dict[str, BaseFieldExtractor] = {}


def get_field_extractor(doc_type: str) -> BaseFieldExtractor:
    """
    Возвращает экземпляр экстрактора для указанного типа документа.
    """
    global _extractors_cache
    normalized_type = (doc_type or "").upper()

    if normalized_type not in _extractors_cache:
        if normalized_type in ("PTS", "VEHICLE_PASSPORT"):
            _extractors_cache[normalized_type] = PtsExtractor()
        elif normalized_type in ("RECEIPT", "UTILITY_BILL", "RECEIPT_UTILITY"):
            _extractors_cache[normalized_type] = ReceiptExtractor()
        elif normalized_type in ("PASSPORT_RF", "PASSPORT"):
            _extractors_cache[normalized_type] = PassportRfExtractor()
        elif normalized_type == "INVOICE":
            _extractors_cache[normalized_type] = InvoiceExtractor()
        elif normalized_type in ("CONTRACT", "AGREEMENT"):
            _extractors_cache[normalized_type] = ContractExtractor()
        elif normalized_type == "ACT":
            _extractors_cache[normalized_type] = ActExtractor()
        elif normalized_type in ("TAX_2NDFL", "2NDFL", "NDFL"):
            _extractors_cache[normalized_type] = Tax2NdflExtractor()
        else:
            _extractors_cache[normalized_type] = GenericFieldExtractor()

    return _extractors_cache[normalized_type]

