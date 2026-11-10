package com.docintell.dto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * DTO редактора документов: содержимое, версии, черновик, экспорт.
 */
public final class EditorDtos {

    private EditorDtos() {
    }

    /** Строка списка версий (без текста). */
    public record VersionMeta(Integer number, String source, String description, LocalDateTime createdAt, int length) {
    }

    /** Документ, открытый в редакторе. */
    public record EditorDocument(
            Long id,
            String title,
            String documentType,
            String documentTypeName,
            String originalFilename,
            String mimeType,
            Long fileSize,
            LocalDateTime createdAt,
            LocalDateTime updatedAt,
            String html,
            boolean hasUnsavedDraft,
            Integer currentVersion,
            List<VersionMeta> versions,
            List<String> warnings,
            CheckResult lastCheck,
            com.fasterxml.jackson.databind.JsonNode fields
    ) {
    }

    /** Результат проверки по правилам. findings — как вернул AI-сервис. */
    /** semantic и cross — сведения о проходе модели и сверке с базой; есть только в ответе на только что выполненную проверку. */
    public record CheckResult(com.fasterxml.jackson.databind.JsonNode findings, int critical, int warning, int info, LocalDateTime checkedAt,
                              com.fasterxml.jackson.databind.JsonNode semantic, com.fasterxml.jackson.databind.JsonNode cross) {
    }

    /** deep — добавить смысловую проверку языковой моделью (долго). */
    public record CheckRequest(String html, Boolean deep) {
    }

    /** Строка реестра. */
    public record RegistryItem(
            Long id,
            String title,
            String documentType,
            String documentTypeName,
            String originalFilename,
            Long fileSize,
            LocalDateTime createdAt,
            LocalDateTime updatedAt,
            Integer currentVersion,
            Integer checkCritical,
            Integer checkWarning,
            Integer checkInfo,
            LocalDateTime checkedAt,
            String number,
            java.time.LocalDate docDate,
            Double amount,
            List<String> counterparties,
            java.time.LocalDate validUntil
    ) {
    }

    /** Фрагмент найденного текста: номер блока, текст и подсветка (смещения внутри text). */
    public record SearchSnippet(int block, String text, boolean prefix, boolean suffix, List<List<Integer>> highlights, int start, int end) {
    }

    /** Результат поиска: документ (как в реестре), релевантность и фрагменты. */
    public record SearchHit(RegistryItem document, double score, boolean exact, List<SearchSnippet> snippets) {
    }

    public record VersionContent(Integer number, String source, String description, LocalDateTime createdAt, String html) {
    }

    /** Вопрос ассистенту. context — то, что вернул прошлый ответ (нужно для уточнений). */
    public record AssistantRequest(String question, com.fasterxml.jackson.databind.JsonNode context, Long docId) {
    }

    public record DraftRequest(String html) {
    }

    public record SaveVersionRequest(String html, String description, String source) {
    }

    public record RenameRequest(String title) {
    }

    public record ExportRequest(String html, String title) {
    }

    /** Ответ AI-сервиса /editor/import. */
    public record ConvertedContent(String html, String title, String sourceKind, List<String> warnings) {
    }
}
