package com.docintell.dto;

import com.docintell.enums.FieldType;

/**
 * DTO для передачи извлечённого поля документа клиенту.
 */
public record DocumentFieldResponse(
        Long id,
        String fieldName,
        String displayName,
        String fieldValue,
        FieldType fieldType,
        String fieldTypeTitle,
        Double confidence,
        String bbox,
        Integer pageNumber,
        Boolean validated
) {}

