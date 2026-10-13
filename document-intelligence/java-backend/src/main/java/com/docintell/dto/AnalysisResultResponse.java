package com.docintell.dto;

import com.docintell.dto.ai.AiAnalyzeResponse.QualityMetricsDto;
import com.docintell.dto.ai.AiAnalyzeResponse.OcrResultDto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * DTO ответа о результатах анализа документа для фронтенда (Electron).
 */
public record AnalysisResultResponse(
        Long id,
        Long documentId,
        String status,
        Double processingTimeMs,
        String detectedType,
        String detectedTypeDisplayName,
        Double typeConfidence,
        String explanation,
        Double overallConfidence,
        Integer totalPages,
        QualityMetricsDto quality,
        List<OcrResultDto> ocrBlocks,
        List<DocumentFieldResponse> fields,
        com.docintell.dto.ai.AiAnalyzeResponse.ValidationSummaryDto validation,
        LocalDateTime analyzedAt,
        String errorMessage
) {}

