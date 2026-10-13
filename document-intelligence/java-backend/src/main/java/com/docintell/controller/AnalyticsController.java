package com.docintell.controller;

import com.docintell.dto.DashboardStatsResponse;
import com.docintell.service.AnalyticsService;
import com.docintell.service.ExportService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST Контроллер аналитики и экспорта данных (Этап 11).
 */
@RestController
@RequestMapping("/api")
public class AnalyticsController {

    private static final Logger logger = LoggerFactory.getLogger(AnalyticsController.class);

    private final AnalyticsService analyticsService;
    private final ExportService exportService;

    public AnalyticsController(AnalyticsService analyticsService, ExportService exportService) {
        this.analyticsService = analyticsService;
        this.exportService = exportService;
    }

    /**
     * GET /api/analytics/dashboard — Сводная статистика и аналитика для главного экрана.
     */
    @GetMapping("/analytics/dashboard")
    public ResponseEntity<DashboardStatsResponse> getDashboardStats() {
        return ResponseEntity.ok(analyticsService.getDashboardStats());
    }

    /**
     * GET /api/documents/export/csv — Экспорт всего реестра документов в CSV.
     */
    @GetMapping("/documents/export/csv")
    public ResponseEntity<byte[]> exportRegistryCsv() {
        byte[] csvBytes = exportService.exportAllDocumentsCsv();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"documents_registry.csv\"")
                .contentType(MediaType.parseMediaType("text/csv; charset=UTF-8"))
                .body(csvBytes);
    }

    /**
     * GET /api/documents/export/json — Экспорт всех документов с полями в JSON.
     */
    @GetMapping("/documents/export/json")
    public ResponseEntity<byte[]> exportRegistryJson() {
        byte[] jsonBytes = exportService.exportAllDocumentsJson();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"documents_export.json\"")
                .contentType(MediaType.APPLICATION_JSON)
                .body(jsonBytes);
    }

    /**
     * GET /api/documents/{id}/export/csv — Экспорт извлеченных реквизитов документа в CSV.
     */
    @GetMapping("/documents/{id}/export/csv")
    public ResponseEntity<byte[]> exportDocumentCsv(@PathVariable Long id) {
        byte[] csvBytes = exportService.exportDocumentFieldsCsv(id);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"document_" + id + "_fields.csv\"")
                .contentType(MediaType.parseMediaType("text/csv; charset=UTF-8"))
                .body(csvBytes);
    }

    /**
     * GET /api/documents/{id}/export/json — Экспорт документа со всеми полями в JSON.
     */
    @GetMapping("/documents/{id}/export/json")
    public ResponseEntity<byte[]> exportDocumentJson(@PathVariable Long id) {
        byte[] jsonBytes = exportService.exportDocumentJson(id);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"document_" + id + ".json\"")
                .contentType(MediaType.APPLICATION_JSON)
                .body(jsonBytes);
    }
}
