"""
Гибридный ансамблевый классификатор документов (Hybrid Ensemble Classifier).

Что делает этот модуль:
1. Объединяет два независимых подхода в ансамбль (Ensemble):
   - Экспертный сигнатурный классификатор (RuleBasedClassifier);
   - Статистический ML-классификатор (MachineLearningClassifier на TF-IDF).
2. Применяет взвешенное голосование (Weighted Voting):
   - При наличии явных юридических реквизитов и якорных фраз приоритет отдаётся правилам;
   - При зашумлённом тексте или нестандартной структуре документа решение выносится на основе
     частотного распределения терминов ML-модели.
3. Обеспечивает максимальную точность и защиту от ложных срабатываний (False Positives).

Архитектурное преимущество:
- Чистый Rule-based может пропустить документ, если в тексте опечатка в ключевом слове.
- Чистый ML может ошибиться на редком документе из-за смещения обучающей выборки.
- Гибридная модель даёт синергию: надёжность правил + обобщающую способность ML.
"""

import logging
from typing import Dict, List, Optional

from app.classifier.base import BaseDocumentClassifier, ClassificationResult, DocumentCategory
from app.classifier.rule_based_classifier import RuleBasedClassifier
from app.classifier.ml_classifier import MachineLearningClassifier

logger = logging.getLogger(__name__)


class HybridDocumentClassifier(BaseDocumentClassifier):
    """Ансамблевый гибридный классификатор."""

    def __init__(self, rule_weight: float = 0.65, ml_weight: float = 0.35):
        self.rule_classifier = RuleBasedClassifier()
        self.ml_classifier = MachineLearningClassifier()
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight

    def classify(self, text: str, ocr_blocks: Optional[list] = None) -> ClassificationResult:
        """
        Ансамблевая классификация документа.
        """
        if not text or not text.strip():
            return ClassificationResult(
                predicted_type=DocumentCategory.UNKNOWN.value,
                display_name=DocumentCategory.UNKNOWN.display_name,
                confidence=0.0,
                probabilities={cat.value: 0.0 for cat in DocumentCategory},
                matched_keywords=[],
                explanation="Документ не содержит текста."
            )

        # 1. Запуск обоих классификаторов
        rule_res = self.rule_classifier.classify(text, ocr_blocks)
        ml_res = self.ml_classifier.classify(text, ocr_blocks)

        logger.info(
            f"Классификация: Rule-based='{rule_res.predicted_type}' ({rule_res.confidence:.1%}), "
            f"ML='{ml_res.predicted_type}' ({ml_res.confidence:.1%})"
        )

        # 2. Объединение распределений вероятностей
        all_categories = [cat.value for cat in DocumentCategory if cat != DocumentCategory.UNKNOWN]
        blended_probs: Dict[str, float] = {}

        for cat in all_categories:
            p_rule = rule_res.probabilities.get(cat, 0.0)
            p_ml = ml_res.probabilities.get(cat, 0.0)
            blended_probs[cat] = round(p_rule * self.rule_weight + p_ml * self.ml_weight, 4)

        blended_probs[DocumentCategory.UNKNOWN.value] = 0.0

        # Сценарий 1: Оба классификатора согласны
        if rule_res.predicted_type == ml_res.predicted_type and rule_res.predicted_type != DocumentCategory.UNKNOWN.value:
            cat_enum = DocumentCategory(rule_res.predicted_type)
            combined_conf = min(0.99, (rule_res.confidence * 0.6 + ml_res.confidence * 0.4) + 0.05)
            explanation = (
                f"Высокая согласованность (Правила + ML): тип «{cat_enum.display_name}». "
                f"Обнаружены маркеры: {', '.join(rule_res.matched_keywords[:4])}."
            )
            return ClassificationResult(
                predicted_type=cat_enum.value,
                display_name=cat_enum.display_name,
                confidence=round(combined_conf, 4),
                probabilities=blended_probs,
                matched_keywords=rule_res.matched_keywords,
                explanation=explanation
            )

        # Сценарий 2: У правил сильный сигнал (например, найден заголовок документа или паспортные якоря)
        if rule_res.predicted_type != DocumentCategory.UNKNOWN.value and rule_res.confidence >= 0.70:
            cat_enum = DocumentCategory(rule_res.predicted_type)
            return ClassificationResult(
                predicted_type=cat_enum.value,
                display_name=cat_enum.display_name,
                confidence=rule_res.confidence,
                probabilities=blended_probs,
                matched_keywords=rule_res.matched_keywords,
                explanation=f"{rule_res.explanation} (подтверждено сигнатурным анализом)."
            )

        # Сценарий 3: Правила не уверены, но ML уверен
        if ml_res.predicted_type != DocumentCategory.UNKNOWN.value and ml_res.confidence >= 0.65:
            cat_enum = DocumentCategory(ml_res.predicted_type)
            return ClassificationResult(
                predicted_type=cat_enum.value,
                display_name=cat_enum.display_name,
                confidence=ml_res.confidence,
                probabilities=blended_probs,
                matched_keywords=rule_res.matched_keywords,
                explanation=f"{ml_res.explanation} (определено по словарному TF-IDF анализу)."
            )

        # Сценарий 4: Никто не уверен — безопасный fallback в UNKNOWN
        best_cat = max(blended_probs, key=blended_probs.get)
        best_val = blended_probs[best_cat]

        if best_val >= 0.50:
            cat_enum = DocumentCategory(best_cat)
            return ClassificationResult(
                predicted_type=cat_enum.value,
                display_name=cat_enum.display_name,
                confidence=best_val,
                probabilities=blended_probs,
                matched_keywords=rule_res.matched_keywords,
                explanation=f"Определено по взвешенному ансамблю: «{cat_enum.display_name}» ({best_val:.1%})."
            )

        return ClassificationResult(
            predicted_type=DocumentCategory.UNKNOWN.value,
            display_name=DocumentCategory.UNKNOWN.display_name,
            confidence=0.0,
            probabilities=blended_probs,
            matched_keywords=[],
            explanation="Документ не содержит достаточного количества признаков ни одного из известных типов."
        )

