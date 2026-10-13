package com.docintell.dto;

import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;

import java.time.LocalDateTime;

/**
 * Компактный DTO для отображения в таблице списка документов.
 */
public record DocumentListItemResponse(
        Long id,
        String originalFilename,
        Long fileSize,
        String mimeType,
        DocumentType documentType,
        String documentTypeDisplayName,
        AnalysisStatus status,
        Double overallConfidence,
        int fieldsCount,
        LocalDateTime createdAt
) {}

