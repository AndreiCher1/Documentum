package com.docintell.controller;

import com.docintell.dto.EditorDtos.*;
import com.docintell.service.EditorService;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * API редактора документов.
 *
 * POST   /api/editor/documents                  — загрузить файл и открыть в редакторе
 * GET    /api/editor/documents                  — реестр
 * GET    /api/editor/documents/{id}             — содержимое и список версий
 * PATCH  /api/editor/documents/{id}             — переименовать
 * PUT    /api/editor/documents/{id}/draft       — автосохранение
 * POST   /api/editor/documents/{id}/versions    — сохранить версию
 * GET    /api/editor/documents/{id}/versions/{n}— текст версии
 * POST   /api/editor/documents/{id}/export/docx — выгрузить DOCX
 * POST   /api/editor/documents/assistant        — вопрос ассистенту по базе
 * GET    /api/editor/documents/assistant/status — состояние языковой модели
 */
@RestController
@RequestMapping("/api/editor/documents")
public class EditorController {

    private final EditorService editorService;

    public EditorController(EditorService editorService) {
        this.editorService = editorService;
    }

    /**
     * Поиск: q — запрос (может быть пустым), mode — words | sem, фильтры по полям карточки.
     * types — названия типов через запятую («Договор,Приказ»), from/to — период, cp — часть названия контрагента.
     */
    @GetMapping("/search")
    public List<SearchHit> search(@RequestParam(defaultValue = "") String q,
                                  @RequestParam(defaultValue = "words") String mode,
                                  @RequestParam(required = false) List<String> types,
                                  @RequestParam(required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate from,
                                  @RequestParam(required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate to,
                                  @RequestParam(required = false) String cp,
                                  @RequestParam(required = false) Double min,
                                  @RequestParam(required = false) Double max) {
        return editorService.search(q, mode, types, from, to, cp, min, max);
    }

    /** Вопрос ассистенту по базе документов. */
    @PostMapping(value = "/assistant", consumes = MediaType.APPLICATION_JSON_VALUE)
    public com.fasterxml.jackson.databind.JsonNode assistant(@RequestBody AssistantRequest request) {
        return editorService.askAssistant(request);
    }

    /** Подключена ли языковая модель. */
    @GetMapping("/assistant/status")
    public com.fasterxml.jackson.databind.JsonNode assistantStatus() {
        return editorService.assistantStatus();
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<EditorDocument> importFile(@RequestParam("file") MultipartFile file) {
        return ResponseEntity.status(HttpStatus.CREATED).body(editorService.importFile(file));
    }

    @GetMapping
    public List<RegistryItem> list() {
        return editorService.list();
    }

    @GetMapping("/{id}")
    public EditorDocument open(@PathVariable Long id) {
        return editorService.open(id);
    }

    @PatchMapping("/{id}")
    public ResponseEntity<Void> rename(@PathVariable Long id, @RequestBody RenameRequest request) {
        editorService.rename(id, request.title());
        return ResponseEntity.noContent().build();
    }

    @PutMapping("/{id}/draft")
    public ResponseEntity<Void> saveDraft(@PathVariable Long id, @RequestBody DraftRequest request) {
        editorService.saveDraft(id, request.html());
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/versions")
    public ResponseEntity<VersionMeta> saveVersion(@PathVariable Long id, @RequestBody SaveVersionRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(editorService.saveVersion(id, request));
    }

    @GetMapping("/{id}/versions/{number}")
    public VersionContent getVersion(@PathVariable Long id, @PathVariable Integer number) {
        return editorService.getVersion(id, number);
    }

    /** Проверить документ по правилам. В теле — текущий HTML редактора (необязательно). */
    @PostMapping("/{id}/check")
    public CheckResult check(@PathVariable Long id, @RequestBody(required = false) CheckRequest request) {
        return editorService.check(id, request == null ? null : request.html(), request != null && Boolean.TRUE.equals(request.deep()));
    }

    @PostMapping("/{id}/export/docx")
    public ResponseEntity<byte[]> exportDocx(@PathVariable Long id, @RequestBody(required = false) ExportRequest request) {
        byte[] data = editorService.exportDocx(id, request);
        String filename = editorService.titleOf(id).replaceAll("[\\\\/:*?\"<>|]", "_") + ".docx";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(filename, StandardCharsets.UTF_8).build().toString())
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                .body(data);
    }
}
