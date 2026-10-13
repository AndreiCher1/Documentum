package com.docintell.dto;

import java.util.List;
import java.util.Map;

/**
 * DTO расширенной аналитики и сводной статистики Dashboard (Этап 11).
 */
public record DashboardStatsResponse(
        long totalDocuments,
        long totalFileSizeBytes,
        long completedCount,
        long processingCount,
        long failedCount,
        long uploadedCount,
        double averageConfidence,
        double successRate,
        Map<String, CategoryStatDto> categories,
        List<DocumentListItemResponse> recentDocuments
) {
    public record CategoryStatDto(
            String type,
            String displayName,
            long count,
            double percentage
    ) {}
}
