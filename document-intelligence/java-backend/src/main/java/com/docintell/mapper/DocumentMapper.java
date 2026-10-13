package com.docintell.mapper;

import com.docintell.dto.DocumentFieldResponse;
import com.docintell.dto.DocumentListItemResponse;
import com.docintell.dto.DocumentResponse;
import com.docintell.dto.DocumentUploadResponse;
import com.docintell.entity.Document;
import com.docintell.entity.DocumentField;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Преобразователь объектов: DocumentMapper
 *
 * ЧТО ТАКОЕ MAPPER?
 * Слой маппинга переводит внутренние JPA-сущности (Entity) во внешние DTO,
 * которые безопасно отдавать клиенту через REST API.
 *
 * ЗАЧЕМ ЭТО ВЫНОСИТСЯ В ОТДЕЛЬНЫЙ КЛАСС?
 * 1. Чистый код: сущность Document отвечает только за данные в БД,
 *    а не за то, как эти данные будут отрисованы в браузере или Electron.
 * 2. Предотвращение утечки лишних данных: например, клиент не должен видеть
 *    абсолютный путь к файлу на сервере (filePath).
 * 3. Локализация: маппер добавляет понятные русские названия (displayName) к enum.
 */
@Component
public class DocumentMapper {

    public DocumentUploadResponse toUploadResponse(Document doc) {
        return new DocumentUploadResponse(
                doc.getId(),
                doc.getOriginalFilename(),
                doc.getFileSize(),
                doc.getMimeType(),
                doc.getDocumentType(),
                doc.getDocumentType().getDisplayName(),
                doc.getStatus(),
                doc.getCreatedAt()
        );
    }

    public DocumentListItemResponse toListItemResponse(Document doc) {
        int fieldsCount = doc.getFields() != null ? doc.getFields().size() : 0;
        return new DocumentListItemResponse(
                doc.getId(),
                doc.getOriginalFilename(),
                doc.getFileSize(),
                doc.getMimeType(),
                doc.getDocumentType(),
                doc.getDocumentType().getDisplayName(),
                doc.getStatus(),
                doc.getOverallConfidence(),
                fieldsCount,
                doc.getCreatedAt()
        );
    }

    public DocumentResponse toDocumentResponse(Document doc) {
        List<DocumentFieldResponse> fieldResponses = Collections.emptyList();
        if (doc.getFields() != null) {
            fieldResponses = doc.getFields().stream()
                    .map(this::toFieldResponse)
                    .collect(Collectors.toList());
        }

        return new DocumentResponse(
                doc.getId(),
                doc.getOriginalFilename(),
                doc.getStoredFilename(),
                doc.getFileSize(),
                doc.getMimeType(),
                doc.getDocumentType(),
                doc.getDocumentType().getDisplayName(),
                doc.getStatus(),
                doc.getOverallConfidence(),
                doc.getCreatedAt(),
                doc.getUpdatedAt(),
                fieldResponses
        );
    }

    public DocumentFieldResponse toFieldResponse(DocumentField field) {
        return new DocumentFieldResponse(
                field.getId(),
                field.getFieldName(),
                field.getDisplayName(),
                field.getFieldValue(),
                field.getFieldType(),
                field.getFieldType().getTitle(),
                field.getConfidence(),
                field.getBbox(),
                field.getPageNumber(),
                field.getValidated()
        );
    }
}

