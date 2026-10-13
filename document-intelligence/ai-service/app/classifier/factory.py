"""
Фабрика классификаторов документов (Classifier Factory).

Обеспечивает кэширование единственного экземпляра классификатора (Singleton).
"""

import logging
from typing import Optional
from app.classifier.base import BaseDocumentClassifier
from app.classifier.hybrid_classifier import HybridDocumentClassifier

logger = logging.getLogger(__name__)

_classifier_instance: Optional[BaseDocumentClassifier] = None


def get_document_classifier() -> BaseDocumentClassifier:
    """Возвращает глобальный синглтон классификатора документов."""
    global _classifier_instance
    if _classifier_instance is None:
        logger.info("Инициализация гибридного классификатора документов...")
        _classifier_instance = HybridDocumentClassifier()
    return _classifier_instance

