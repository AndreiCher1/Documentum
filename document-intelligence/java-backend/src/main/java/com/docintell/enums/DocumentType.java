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
    PASSPORT("Паспорт РФ"),
    PTS("Паспорт ТС (ПТС)"),
    STS("Свидетельство о регистрации ТС (СТС)"),
    DRIVER_LICENSE("Водительское удостоверение"),
    SNILS("СНИЛС"),
    INN("Свидетельство ИНН"),
    CONTRACT("Договор"),
    INVOICE("Счёт на оплату"),
    RECEIPT("Квитанция / Счёт ЖКУ"),
    ACT("Акт выполненных работ"),
    CASH_RECEIPT("Кассовый чек"),
    BANK_STATEMENT("Банковская выписка"),
    TECH_PASSPORT("Техпаспорт оборудования"),
    MEDICAL_REPORT("Медицинские анализы / Заключение"),
    LEGAL_HR("Судебный / Кадровый документ"),
    TAX_2NDFL("Справка 2-НДФЛ"),
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

    /**
     * Преобразование строкового идентификатора из AI-сервиса в enum DocumentType.
     * Защищает систему от сбоев при нестандартных ответах или синонимах.
     */
    public static DocumentType fromString(String value) {
        if (value == null || value.isBlank()) {
            return UNKNOWN;
        }
        String normalized = value.trim().toUpperCase();
        if (normalized.equals("PTS") || normalized.equals("VEHICLE_PASSPORT")) {
            return PTS;
        }
        if (normalized.equals("STS") || normalized.equals("VEHICLE_REGISTRATION")) {
            return STS;
        }
        if (normalized.equals("DRIVER_LICENSE") || normalized.equals("DRIVING_LICENSE") || normalized.equals("DRIVER_LICENCE")) {
            return DRIVER_LICENSE;
        }
        if (normalized.equals("SNILS")) {
            return SNILS;
        }
        if (normalized.equals("INN") || normalized.equals("INN_CERTIFICATE")) {
            return INN;
        }
        if (normalized.equals("CASH_RECEIPT") || normalized.equals("FISCAL_RECEIPT") || normalized.equals("CHECK")) {
            return CASH_RECEIPT;
        }
        if (normalized.equals("BANK_STATEMENT") || normalized.equals("ACCOUNT_STATEMENT")) {
            return BANK_STATEMENT;
        }
        if (normalized.equals("TECH_PASSPORT") || normalized.equals("TECHNICAL_PASSPORT")) {
            return TECH_PASSPORT;
        }
        if (normalized.equals("MEDICAL_REPORT") || normalized.equals("LAB_REPORT") || normalized.equals("MEDICAL_ANALYSIS")) {
            return MEDICAL_REPORT;
        }
        if (normalized.equals("LEGAL_HR") || normalized.equals("COURT_DECISION") || normalized.equals("ORDER")) {
            return LEGAL_HR;
        }
        if (normalized.equals("PASSPORT_RF") || normalized.equals("PASSPORT")) {
            return PASSPORT;
        }
        if (normalized.equals("CONTRACT") || normalized.equals("AGREEMENT")) {
            return CONTRACT;
        }
        if (normalized.equals("INVOICE") || normalized.equals("BILL")) {
            return INVOICE;
        }
        if (normalized.equals("RECEIPT") || normalized.equals("UTILITY_BILL") || normalized.equals("RECEIPT_UTILITY")) {
            return RECEIPT;
        }
        if (normalized.equals("ACT") || normalized.equals("WORK_ACT")) {
            return ACT;
        }
        if (normalized.equals("TAX_2NDFL") || normalized.equals("NDFL") || normalized.equals("2NDFL")) {
            return TAX_2NDFL;
        }
        for (DocumentType type : values()) {
            if (type.name().equalsIgnoreCase(normalized)) {
                return type;
            }
        }
        return UNKNOWN;
    }
}

