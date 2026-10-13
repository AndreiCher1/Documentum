package com.docintell.dto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * DTO ответа поиска документов (Этап 10).
 */
public record SearchResponse(
        long totalElements,
        int totalPages,
        int currentPage,
        int pageSize,
        List<SearchResultItem> items
) {
    public record SearchResultItem(
            Long documentId,
            String originalFilename,
            String documentType,
            String documentTypeDisplayName,
            String status,
            Double overallConfidence,
            Long fileSize,
            LocalDateTime createdAt,
            List<MatchedFieldDto> matchedFields,
            List<String> snippets
    ) {}

    public record MatchedFieldDto(
            String fieldName,
            String displayName,
            String fieldValue,
            Double confidence
    ) {}
}

