package com.docintell;

import com.docintell.dto.AnalysisResultResponse;
import com.docintell.dto.ai.AiAnalyzeResponse;
import com.docintell.dto.ai.AiAnalyzeResponse.DocumentTypeDto;
import com.docintell.dto.ai.AiAnalyzeResponse.OcrResultDto;
import com.docintell.dto.ai.AiAnalyzeResponse.QualityMetricsDto;
import com.docintell.entity.Document;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.repository.DocumentRepository;
import com.docintell.service.AiServiceClient;
import com.docintell.service.FileStorageService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Collections;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class DocumentAnalysisTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DocumentRepository documentRepository;

    @MockitoBean
    private AiServiceClient aiServiceClient;

    @MockitoBean
    private FileStorageService fileStorageService;

    @Test
    @DisplayName("Запуск AI-анализа документа через POST /api/documents/{id}/analyze")
    void testAnalyzeDocumentEndpoint() throws Exception {
        // 1. Создаём тестовый документ в БД
        Document doc = new Document();
        doc.setOriginalFilename("test_passport.jpg");
        doc.setStoredFilename("stored_uuid_123.jpg");
        doc.setFilePath("/uploads/stored_uuid_123.jpg");
        doc.setFileSize(2048L);
        doc.setMimeType("image/jpeg");
        doc.setDocumentType(DocumentType.UNKNOWN);
        doc.setStatus(AnalysisStatus.UPLOADED);
        doc.setOverallConfidence(0.0);
        Document savedDoc = documentRepository.save(doc);

        // 2. Мокаем хранилище файлов
        Mockito.when(fileStorageService.loadAsResource("stored_uuid_123.jpg"))
                .thenReturn(new ByteArrayResource(new byte[]{1, 2, 3, 4}));

        // 3. Мокаем ответ от Python AI-сервиса
        QualityMetricsDto quality = new QualityMetricsDto(150.0, false, 200.0, 50.0, 1024, 768, 0.5);
        DocumentTypeDto docType = new DocumentTypeDto("PASSPORT_RF", 0.95);
        List<OcrResultDto> ocrBlocks = List.of(
                new OcrResultDto("ПАСПОРТ РОССИЙСКАЯ ФЕДЕРАЦИЯ", 0.99, List.of(50, 100, 400, 140), 1),
                new OcrResultDto("СЕРИЯ 45 10 НОМЕР 123456", 0.98, List.of(50, 150, 350, 180), 1)
        );

        AiAnalyzeResponse mockAiResponse = new AiAnalyzeResponse(
                "success",
                1250.0,
                1,
                quality,
                docType,
                ocrBlocks,
                Collections.emptyList(),
                null,
                0.985,
                "Успешно"
        );

        Mockito.when(aiServiceClient.analyzeDocument(any(byte[].class), eq("test_passport.jpg")))
                .thenReturn(mockAiResponse);

        // 4. Вызываем POST /api/documents/{id}/analyze
        mockMvc.perform(post("/api/documents/" + savedDoc.getId() + "/analyze"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("success"))
                .andExpect(jsonPath("$.documentId").value(savedDoc.getId()))
                .andExpect(jsonPath("$.ocrBlocks.length()").value(2))
                .andExpect(jsonPath("$.ocrBlocks[0].text").value("ПАСПОРТ РОССИЙСКАЯ ФЕДЕРАЦИЯ"))
                .andExpect(jsonPath("$.overallConfidence").value(0.985));

        // 5. Проверяем получение последнего анализа через GET /api/documents/{id}/analysis
        mockMvc.perform(get("/api/documents/" + savedDoc.getId() + "/analysis"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("success"))
                .andExpect(jsonPath("$.ocrBlocks.length()").value(2));
    }
}

