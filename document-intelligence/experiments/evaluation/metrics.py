"""
Модуль вычисления метрик качества OCR и структурирования документов.

Реализует международные метрики оценки систем распознавания документов:
- CER (Character Error Rate) — посимвольная ошибка распознавания через расстояние Левенштейна.
- WER (Word Error Rate) — пословная ошибка распознавания.
- Precision, Recall, F1-Score для извлечённых именованных сущностей / полей.
- Normalized Edit Distance (NED) — сходство строк от 0.0 до 1.0.
- Classification Accuracy — точность классификатора документов.
"""

from typing import List, Dict, Any, Tuple
import re


def levenshtein_distance(s1: str, s2: str) -> int:
    """Классическое расстояние Левенштейна между двумя строками."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

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


def normalize_text_for_eval(text: str) -> str:
    """Нормализация текста для справедливого сравнения (удаление лишних пробелов, единый регистр)."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Character Error Rate (CER).
    CER = (Substitutions + Deletions + Insertions) / Total Reference Characters * 100%
    """
    ref_norm = normalize_text_for_eval(reference)
    hyp_norm = normalize_text_for_eval(hypothesis)

    if not ref_norm and not hyp_norm:
        return 0.0
    if not ref_norm:
        return 100.0

    distance = levenshtein_distance(ref_norm, hyp_norm)
    cer = (distance / len(ref_norm)) * 100.0
    return min(round(cer, 2), 100.0)


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Word Error Rate (WER).
    Расстояние Левенштейна на уровне последовательности слов.
    """
    ref_words = normalize_text_for_eval(reference).split()
    hyp_words = normalize_text_for_eval(hypothesis).split()

    if not ref_words and not hyp_words:
        return 0.0
    if not ref_words:
        return 100.0

    # Матрица расстояний на массивах токенов
    n = len(ref_words)
    m = len(hyp_words)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref_words[i - 1].lower() == hyp_words[j - 1].lower() else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,       # deletion
                dp[i][j - 1] + 1,       # insertion
                dp[i - 1][j - 1] + cost # substitution
            )

    wer = (dp[n][m] / n) * 100.0
    return min(round(wer, 2), 100.0)


def normalized_similarity(s1: str, s2: str) -> float:
    """Нормализованное сходство двух строк [0.0..1.0]."""
    s1_norm = normalize_text_for_eval(s1).lower()
    s2_norm = normalize_text_for_eval(s2).lower()
    if not s1_norm and not s2_norm:
        return 1.0
    max_len = max(len(s1_norm), len(s2_norm))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(s1_norm, s2_norm)
    return max(0.0, 1.0 - dist / max_len)


def calculate_field_metrics(
    ground_truth: Dict[str, str],
    predictions: Dict[str, str],
    similarity_threshold: float = 0.80
) -> Dict[str, Any]:
    """
    Оценка точности извлечения ключевых полей (Precision, Recall, F1).
    Поле считается верно извлечённым, если его нормализованное сходство >= 80%.
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    field_evaluations = {}

    all_keys = set(ground_truth.keys()).union(set(predictions.keys()))

    for key in all_keys:
        gt_val = str(ground_truth.get(key, '')).strip()
        pred_val = str(predictions.get(key, '')).strip()

        if gt_val and pred_val:
            sim = normalized_similarity(gt_val, pred_val)
            matched = sim >= similarity_threshold
            if matched:
                true_positives += 1
            else:
                false_positives += 1
                false_negatives += 1

            field_evaluations[key] = {
                'ground_truth': gt_val,
                'predicted': pred_val,
                'similarity': round(sim * 100, 1),
                'match': matched
            }
        elif gt_val and not pred_val:
            false_negatives += 1
            field_evaluations[key] = {
                'ground_truth': gt_val,
                'predicted': '',
                'similarity': 0.0,
                'match': False
            }
        elif not gt_val and pred_val:
            false_positives += 1
            field_evaluations[key] = {
                'ground_truth': '',
                'predicted': pred_val,
                'similarity': 0.0,
                'match': False
            }

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'precision': round(precision * 100, 1),
        'recall': round(recall * 100, 1),
        'f1_score': round(f1 * 100, 1),
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'fields': field_evaluations
    }

