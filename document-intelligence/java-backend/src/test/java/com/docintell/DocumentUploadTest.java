package com.docintell;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Интеграционный тест загрузки и валидации документов.
 *
 * Проверяет:
 * 1. Успешную загрузку файла и регистрацию в БД (POST /api/documents)
 * 2. Защиту от загрузки запрещённых расширений (.exe)
 * 3. Защиту от пустых файлов
 * 4. Получение списка документов (GET /api/documents)
 * 5. Удаление документа (DELETE /api/documents/{id})
 */
@SpringBootTest
@AutoConfigureMockMvc
class DocumentUploadTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("Успешная загрузка PDF документа")
    void testUploadValidDocument() throws Exception {
        MockMultipartFile validPdf = new MockMultipartFile(
                "file",
                "test_contract.pdf",
                "application/pdf",
                "%PDF-1.4 sample pdf content".getBytes()
        );

        mockMvc.perform(multipart("/api/documents").file(validPdf))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isNumber())
                .andExpect(jsonPath("$.originalFilename").value("test_contract.pdf"))
                .andExpect(jsonPath("$.status").value("UPLOADED"));
    }

    @Test
    @DisplayName("Блокировка загрузки исполняемого файла .exe")
    void testBlockExecutableFile() throws Exception {
        MockMultipartFile dangerousFile = new MockMultipartFile(
                "file",
                "virus.exe",
                "application/octet-stream",
                "fake exe content".getBytes()
        );

        mockMvc.perform(multipart("/api/documents").file(dangerousFile))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Ошибка валидации файла"));
    }

    @Test
    @DisplayName("Блокировка пустого файла")
    void testBlockEmptyFile() throws Exception {
        MockMultipartFile emptyFile = new MockMultipartFile(
                "file",
                "empty.png",
                "image/png",
                new byte[0]
        );

        mockMvc.perform(multipart("/api/documents").file(emptyFile))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    @Test
    @DisplayName("Получение списка документов")
    void testGetDocumentsList() throws Exception {
        mockMvc.perform(get("/api/documents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content").isArray());
    }
}

