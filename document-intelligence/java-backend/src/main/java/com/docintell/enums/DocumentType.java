package com.docintell.enums;

/**
 * Типы поддерживаемых документов.
 *
 * Архитектурный выбор:
 * Мы используем Enum на английском языке (PASSPORT, CONTRACT, INVOICE и т.д.),
 * чтобы не зависеть от локализации в коде и в базе данных.
 *
 * Метод getDisplayName() возвращает понятное русское название
 * для отображения в интерфейсе пользователя.
 *
 * Если тип документа не удалось определить уверенно — используется UNKNOWN.
 */
public enum DocumentType {
    PASSPORT("Паспорт"),
    CONTRACT("Договор"),
    INVOICE("Счёт на оплату"),
    CERTIFICATE("Свидетельство / Справка"),
    APPLICATION("Заявление"),
    STATEMENT("Выписка"),
    VEHICLE_DOCUMENT("Автомобильный документ (СТС / ПТС)"),
    WAYBILL("Накладная"),
    UNKNOWN("Не определен");

    private final String displayName;

    DocumentType(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
