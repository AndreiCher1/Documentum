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
            CheckResult lastCheck
    ) {
    }

    /** Результат проверки по правилам. findings — как вернул AI-сервис. */
    public record CheckResult(com.fasterxml.jackson.databind.JsonNode findings, int critical, int warning, int info, LocalDateTime checkedAt) {
    }

    public record CheckRequest(String html) {
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
            LocalDateTime checkedAt
    ) {
    }

    public record VersionContent(Integer number, String source, String description, LocalDateTime createdAt, String html) {
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
