package com.docintell.controller;

import com.docintell.dto.SearchRequest;
import com.docintell.dto.SearchResponse;
import com.docintell.service.SearchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

/**
 * REST Контроллер поиска и фильтрации документов (Этап 10).
 *
 * Предоставляет API для:
 * - Полнотекстового поиска по содержимому документов (имя файла, атрибуты, OCR-текст)
 * - Параметрической фильтрации (по типу документа, статусу, уверенности, датам)
 */
@RestController
@RequestMapping("/api/search")
public class SearchController {

    private static final Logger logger = LoggerFactory.getLogger(SearchController.class);

    private final SearchService searchService;

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    /**
     * POST /api/search — Полнотекстовый и параметрический поиск с телом запроса JSON.
     */
    @PostMapping
    public ResponseEntity<SearchResponse> searchDocuments(@RequestBody SearchRequest request) {
        logger.info("POST /api/search: query='{}'", request.query());
        SearchResponse response = searchService.search(request);
        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/search — Полнотекстовый и параметрический поиск через Query Parameters.
     */
    @GetMapping
    public ResponseEntity<SearchResponse> searchDocumentsGet(
            @RequestParam(required = false) String query,
            @RequestParam(required = false) String documentType,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateFrom,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate dateTo,
            @RequestParam(required = false) Double minConfidence,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "0") Integer page,
            @RequestParam(defaultValue = "20") Integer size
    ) {
        SearchRequest request = new SearchRequest(
                query,
                documentType,
                dateFrom,
                dateTo,
                minConfidence,
                status,
                page,
                size
        );
        SearchResponse response = searchService.search(request);
        return ResponseEntity.ok(response);
    }
}

