package com.docintell.service;

import com.docintell.dto.DashboardStatsResponse;
import com.docintell.dto.DashboardStatsResponse.CategoryStatDto;
import com.docintell.dto.DocumentListItemResponse;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * Сервис сбора и вычисления аналитики Dashboard (Этап 11).
 */
@Service
public class AnalyticsService {

    private static final Logger logger = LoggerFactory.getLogger(AnalyticsService.class);

    private final DocumentRepository documentRepository;
    private final DocumentService documentService;

    public AnalyticsService(DocumentRepository documentRepository, DocumentService documentService) {
        this.documentRepository = documentRepository;
        this.documentService = documentService;
    }

    /**
     * Получить сводную статистику системы для главной страницы Dashboard.
     */
    @Transactional(readOnly = true)
    public DashboardStatsResponse getDashboardStats() {
        long total = documentRepository.count();
        Long totalSize = documentRepository.calculateTotalFileSize();
        if (totalSize == null) totalSize = 0L;

        long completed = documentRepository.countByStatus(AnalysisStatus.COMPLETED);
        long processing = documentRepository.countByStatus(AnalysisStatus.PROCESSING);
        long failed = documentRepository.countByStatus(AnalysisStatus.FAILED);
        long uploaded = documentRepository.countByStatus(AnalysisStatus.UPLOADED);

        Double avgConfRaw = documentRepository.calculateAverageConfidenceByStatus(AnalysisStatus.COMPLETED);
        double avgConfPct = (avgConfRaw != null) ? Math.round(avgConfRaw * 1000.0) / 10.0 : 0.0;

        double successRate = total > 0 ? Math.round(((double) completed / total) * 1000.0) / 10.0 : 0.0;

        // Распределение по типам документов
        Map<String, CategoryStatDto> categories = new LinkedHashMap<>();
        List<Object[]> grouped = documentRepository.countGroupedByDocumentType();
        for (Object[] row : grouped) {
            DocumentType type = (DocumentType) row[0];
            Long count = (Long) row[1];
            if (type != null && count != null && count > 0) {
                double pct = total > 0 ? Math.round(((double) count / total) * 1000.0) / 10.0 : 0.0;
                categories.put(type.name(), new CategoryStatDto(
                        type.name(),
                        type.getDisplayName(),
                        count,
                        pct
                ));
            }
        }

        List<DocumentListItemResponse> recent = documentService.getRecentDocuments(5);

        return new DashboardStatsResponse(
                total,
                totalSize,
                completed,
                processing,
                failed,
                uploaded,
                avgConfPct,
                successRate,
                categories,
                recent
        );
    }
}

