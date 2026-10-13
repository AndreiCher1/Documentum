package com.docintell.dto;

import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;

import java.time.LocalDateTime;

/**
 * DTO ответа после успешной загрузки файла.
 */
public record DocumentUploadResponse(
        Long id,
        String originalFilename,
        Long fileSize,
        String mimeType,
        DocumentType documentType,
        String documentTypeDisplayName,
        AnalysisStatus status,
        LocalDateTime createdAt
) {}

