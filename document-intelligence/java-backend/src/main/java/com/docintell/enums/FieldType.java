package com.docintell.enums;

/**
 * Семантический тип извлечённого поля.
 *
 * Определяет правила валидации:
 * DATE   -> валидируется как календарная дата
 * AMOUNT -> числовое значение денежной суммы
 * INN    -> валидация длины ИНН (10 или 12 цифр)
 * VIN    -> 17 символов по стандарту ISO 3779
 * PHONE  -> формат телефонного номера
 * EMAIL  -> формат электронной почты
 */
public enum FieldType {
    TEXT("Текст"),
    DATE("Дата"),
    NUMBER("Число"),
    AMOUNT("Денежная сумма"),
    EMAIL("Email"),
    PHONE("Телефон"),
    INN("ИНН"),
    VIN("VIN-номер"),
    ORGANIZATION("Организация"),
    PERSON("ФИО"),
    TABLE("Таблица");

    private final String title;

    FieldType(String title) {
        this.title = title;
    }

    public String getTitle() {
        return title;
    }

    public static FieldType fromString(String value) {
        if (value == null || value.isBlank()) {
            return TEXT;
        }
        String normalized = value.trim().toUpperCase();
        for (FieldType type : values()) {
            if (type.name().equalsIgnoreCase(normalized)) {
                return type;
            }
        }
        return TEXT;
    }
}

