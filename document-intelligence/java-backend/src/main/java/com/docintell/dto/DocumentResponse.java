package com.docintell.dto;

import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Детальный DTO документа с полным списком извлечённых полей.
 */
public record DocumentResponse(
        Long id,
        String originalFilename,
        String storedFilename,
        Long fileSize,
        String mimeType,
        DocumentType documentType,
        String documentTypeDisplayName,
        AnalysisStatus status,
        Double overallConfidence,
        LocalDateTime createdAt,
        LocalDateTime updatedAt,
        List<DocumentFieldResponse> fields
) {}

