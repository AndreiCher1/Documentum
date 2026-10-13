package com.docintell.repository;

import com.docintell.entity.AnalysisResult;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Репозиторий результатов AI-анализа: AnalysisResultRepository
 *
 * Хранит протоколы работы ML-конвейеров, метрики времени инференса и статус распознавания.
 */
@Repository
public interface AnalysisResultRepository extends JpaRepository<AnalysisResult, Long> {

    /**
     * Получить историю всех анализов конкретного документа, отсортированную по времени.
     */
    List<AnalysisResult> findByDocumentIdOrderByCreatedAtDesc(Long documentId);

    /**
     * Получить последний результат анализа документа.
     */
    Optional<AnalysisResult> findFirstByDocumentIdOrderByCreatedAtDesc(Long documentId);

    /**
     * Поиск по имени модели (например, для бенчмаркинга всех запусков "paddle_ocr").
     */
    List<AnalysisResult> findByAnalyzerName(String analyzerName);
}

