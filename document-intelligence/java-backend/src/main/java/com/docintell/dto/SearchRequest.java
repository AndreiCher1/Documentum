package com.docintell.dto;

import java.time.LocalDate;

/**
 * DTO запроса на поиск и фильтрацию документов (Этап 10).
 */
public record SearchRequest(
        String query,
        String documentType,
        LocalDate dateFrom,
        LocalDate dateTo,
        Double minConfidence,
        String status,
        Integer page,
        Integer size
) {
    public SearchRequest {
        if (page == null || page < 0) page = 0;
        if (size == null || size <= 0) size = 20;
    }
}

