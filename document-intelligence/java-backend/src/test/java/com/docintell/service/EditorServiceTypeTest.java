package com.docintell.service;

import com.docintell.enums.DocumentType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** Определение типа документа по названию и имени файла. */
class EditorServiceTypeTest {

    @Test
    void recognisesCorporateDocumentTypes() {
        assertEquals(DocumentType.CONTRACT, EditorService.guessType("ДОГОВОР ПОСТАВКИ № 124-А dogovor.docx"));
        assertEquals(DocumentType.SUPPLEMENTARY_AGREEMENT, EditorService.guessType("Дополнительное соглашение № 2 к договору подряда"));
        assertEquals(DocumentType.ORDER, EditorService.guessType("Приказ № 112 о назначении генерального директора"));
        assertEquals(DocumentType.BUDGET, EditorService.guessType("Приказ № 322 об утверждении бюджета маркетинга"));
        assertEquals(DocumentType.MEMO, EditorService.guessType("Служебная записка о закупке оргтехники"));
        assertEquals(DocumentType.REGULATION, EditorService.guessType("Регламент документооборота"));
        assertEquals(DocumentType.TECH_SPEC, EditorService.guessType("ТЗ на внедрение СЭД"));
        assertEquals(DocumentType.TECH_SPEC, EditorService.guessType("Техническое задание"));
        assertEquals(DocumentType.CLAIM, EditorService.guessType("Претензия о просрочке поставки"));
        assertEquals(DocumentType.INVOICE, EditorService.guessType("Счёт на оплату № 412"));
        assertEquals(DocumentType.ACT, EditorService.guessType("Акт приёма-передачи № 58"));
        assertEquals(DocumentType.UNKNOWN, EditorService.guessType("Фактура scan_001.jpg"));
    }
}
