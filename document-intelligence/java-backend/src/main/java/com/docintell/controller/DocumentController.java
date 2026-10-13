package com.docintell.controller;

import com.docintell.dto.DocumentListItemResponse;
import com.docintell.dto.DocumentResponse;
import com.docintell.dto.DocumentUploadResponse;
import com.docintell.service.DocumentService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.Resource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * REST Контроллер управления документами: DocumentController
 *
 * ТОЧКА ВХОДА ДЛЯ ELECTRON:
 * - Загрузка документов (POST /api/documents)
 * - Список документов (GET /api/documents)
 * - Просмотр документа (GET /api/documents/{id})
 * - Превью файла (GET /api/documents/{id}/file)
 * - Удаление документа (DELETE /api/documents/{id})
 */
@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private static final Logger logger = LoggerFactory.getLogger(DocumentController.class);

    private final DocumentService documentService;

    public DocumentController(DocumentService documentService) {
        this.documentService = documentService;
    }

    /**
     * POST /api/documents — Загрузка нового файла в систему.
     *
     * Принимает: multipart/form-data с полем "file".
     * Возвращает: 201 Created и метаданные документа.
     */
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<DocumentUploadResponse> uploadDocument(@RequestParam("file") MultipartFile file) {
        logger.info("Получен HTTP запрос на загрузку файла: {}", file.getOriginalFilename());
        DocumentUploadResponse response = documentService.uploadDocument(file);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    /**
     * GET /api/documents — Постраничный список документов.
     *
     * Параметры query:
     * - page: номер страницы (по умолчанию 0)
     * - size: количество на странице (по умолчанию 20)
     * - sort: поле сортировки (по умолчанию createdAt,desc)
     */
    @GetMapping
    public ResponseEntity<Page<DocumentListItemResponse>> getDocuments(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt,desc") String sort
    ) {
        String[] sortParams = sort.split(",");
        Sort.Direction direction = sortParams.length > 1 && sortParams[1].equalsIgnoreCase("asc")
                ? Sort.Direction.ASC
                : Sort.Direction.DESC;
        String property = sortParams[0];

        Pageable pageable = PageRequest.of(page, size, Sort.by(direction, property));
        return ResponseEntity.ok(documentService.getAllDocuments(pageable));
    }

    /**
     * GET /api/documents/recent — Список последних загруженных документов для Dashboard.
     */
    @GetMapping("/recent")
    public ResponseEntity<List<DocumentListItemResponse>> getRecentDocuments(
            @RequestParam(defaultValue = "5") int limit
    ) {
        return ResponseEntity.ok(documentService.getRecentDocuments(limit));
    }

    /**
     * GET /api/documents/{id} — Детальная информация о документе со всеми полями.
     */
    @GetMapping("/{id}")
    public ResponseEntity<DocumentResponse> getDocument(@PathVariable Long id) {
        return ResponseEntity.ok(documentService.getDocumentById(id));
    }

    /**
     * GET /api/documents/{id}/file — Отдача исходного бинарного файла для отображения скана в UI.
     */
    @GetMapping("/{id}/file")
    public ResponseEntity<Resource> getDocumentFile(@PathVariable Long id) {
        DocumentResponse doc = documentService.getDocumentById(id);
        Resource fileResource = documentService.getDocumentFile(id);

        MediaType mediaType;
        try {
            mediaType = MediaType.parseMediaType(doc.mimeType());
        } catch (Exception e) {
            mediaType = MediaType.APPLICATION_OCTET_STREAM;
        }

        return ResponseEntity.ok()
                .contentType(mediaType)
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + doc.originalFilename() + "\"")
                .body(fileResource);
    }

    /**
     * GET /api/documents/{id}/preview — Рендер страницы документа в изображение (PNG) для UI просмотрщика.
     * Для PDF-файлов рендерит конкретную страницу в растр через PyMuPDF в AI-сервисе.
     */
    @GetMapping("/{id}/preview")
    public ResponseEntity<Resource> getDocumentPreview(
            @PathVariable Long id,
            @RequestParam(defaultValue = "1") int page
    ) {
        DocumentResponse doc = documentService.getDocumentById(id);
        Resource previewResource = documentService.getDocumentPreview(id, page);

        MediaType mediaType = MediaType.IMAGE_PNG;
        if (doc.mimeType() != null && !doc.mimeType().contains("pdf")) {
            try {
                mediaType = MediaType.parseMediaType(doc.mimeType());
            } catch (Exception ignored) {}
        }

        return ResponseEntity.ok()
                .contentType(mediaType)
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"preview_p" + page + ".png\"")
                .body(previewResource);
    }

    /**
     * DELETE /api/documents/{id} — Удаление документа и файла с диска.
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteDocument(@PathVariable Long id) {
        logger.info("Запрос на удаление документа с ID: {}", id);
        documentService.deleteDocument(id);
        return ResponseEntity.noContent().build();
    }

    /**
     * POST /api/documents/{id}/analyze — Запуск AI-анализа документа (предобработка + OCR).
     */
    @PostMapping("/{id}/analyze")
    public ResponseEntity<com.docintell.dto.AnalysisResultResponse> analyzeDocument(@PathVariable Long id) {
        logger.info("Запрос на запуск AI-анализа для документа ID: {}", id);
        com.docintell.dto.AnalysisResultResponse response = documentService.analyzeDocument(id);
        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/documents/{id}/analysis — Получение последнего результата анализа.
     */
    @GetMapping("/{id}/analysis")
    public ResponseEntity<com.docintell.dto.AnalysisResultResponse> getLatestAnalysis(@PathVariable Long id) {
        return documentService.getLatestAnalysis(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}

