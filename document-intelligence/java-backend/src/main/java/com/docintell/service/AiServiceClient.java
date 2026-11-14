package com.docintell.service;

import com.docintell.dto.HealthStatusResponse.AiServiceStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/**
 * Клиент для общения с Python AI-сервисом.
 *
 * @Service — аннотация, которая говорит Spring:
 * "Этот класс содержит бизнес-логику, создай его и управляй им."
 *
 * Этот класс — единственное место, откуда Java вызывает Python.
 * Вся логика общения с AI-сервисом сосредоточена здесь.
 *
 * Зачем отдельный класс?
 * - Controller не должен знать, как устроен вызов Python
 * - Если адрес Python-сервиса изменится — меняем только этот класс
 * - Легко добавить retry-логику, таймауты, fallback
 *
 * Аналогия: это как "телефонная книга + телефон" — знает номер Python
 * и умеет позвонить ему.
 */
@Service
public class AiServiceClient {

    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);

    private final RestTemplate restTemplate;
    private final String aiServiceUrl;

    /**
     * Конструктор.
     *
     * @Value — Spring подставляет значение из application.yml.
     * Это dependency injection (внедрение зависимости):
     * Spring сам создаёт RestTemplate и передаёт его сюда.
     *
     * Мы НЕ пишем new RestTemplate() — Spring делает это за нас.
     * Почему? Потому что Spring управляет жизненным циклом объектов
     * и может, например, создать один RestTemplate для всего приложения.
     */
    public AiServiceClient(
            RestTemplate restTemplate,
            @Value("${ai.service.url}") String aiServiceUrl
    ) {
        this.restTemplate = restTemplate;
        this.aiServiceUrl = aiServiceUrl;
    }

    /**
     * Проверяет, доступен ли Python AI-сервис.
     *
     * @return статус AI-сервиса или null, если сервис недоступен
     */
    public AiServiceStatus checkHealth() {
        try {
            logger.info("Проверка доступности AI-сервиса: {}", aiServiceUrl);

            org.springframework.http.client.SimpleClientHttpRequestFactory healthFactory =
                    new org.springframework.http.client.SimpleClientHttpRequestFactory();
            healthFactory.setConnectTimeout(2000);
            healthFactory.setReadTimeout(3000);
            RestTemplate healthRestTemplate = new RestTemplate(healthFactory);

            AiServiceStatus response = healthRestTemplate.getForObject(
                    aiServiceUrl + "/health",
                    AiServiceStatus.class
            );

            logger.info("AI-сервис доступен: {}", response);
            return response;
        } catch (Exception e) {
            logger.warn("AI-сервис недоступен: {}", e.getMessage());
            return null;
        }
    }

    /**
     * Отправляет файл в Python AI-сервис для анализа (предобработка + OCR).
     *
     * @param fileBytes        байты документа
     * @param originalFilename исходное имя файла (для определения расширения)
     * @return структурированный результат анализа
     */
    public com.docintell.dto.ai.AiAnalyzeResponse analyzeDocument(byte[] fileBytes, String originalFilename) {
        try {
            logger.info("Отправка документа '{}' ({} байт) в AI-сервис: {}/analyze",
                    originalFilename, fileBytes.length, aiServiceUrl);

            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.MULTIPART_FORM_DATA);

            org.springframework.util.MultiValueMap<String, Object> body = new org.springframework.util.LinkedMultiValueMap<>();
            org.springframework.core.io.ByteArrayResource fileResource = new org.springframework.core.io.ByteArrayResource(fileBytes) {
                @Override
                public String getFilename() {
                    return originalFilename;
                }
            };
            body.add("file", fileResource);

            org.springframework.http.HttpEntity<org.springframework.util.MultiValueMap<String, Object>> requestEntity =
                    new org.springframework.http.HttpEntity<>(body, headers);

            com.docintell.dto.ai.AiAnalyzeResponse response = restTemplate.postForObject(
                    aiServiceUrl + "/analyze",
                    requestEntity,
                    com.docintell.dto.ai.AiAnalyzeResponse.class
            );

            logger.info("Ответ от AI-сервиса успешно получен: status={}, блоков OCR={}",
                    response != null ? response.status() : "null",
                    response != null && response.ocrResults() != null ? response.ocrResults().size() : 0);

            return response;

        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /analyze: {}", e.getMessage(), e);
            throw new RuntimeException("AI-сервис временно недоступен: " + e.getMessage(), e);
        }
    }

    /**
     * Преобразует файл в HTML для редактора (AI-сервис /editor/import).
     * Понятные пользователю ошибки AI-сервиса (415/422) превращаются в ConversionException.
     */
    public com.docintell.dto.EditorDtos.ConvertedContent convertForEditor(byte[] fileBytes, String originalFilename) {
        org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
        headers.setContentType(org.springframework.http.MediaType.MULTIPART_FORM_DATA);
        org.springframework.util.MultiValueMap<String, Object> body = new org.springframework.util.LinkedMultiValueMap<>();
        body.add("file", new org.springframework.core.io.ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return originalFilename;
            }
        });
        try {
            return restTemplate.postForObject(aiServiceUrl + "/editor/import",
                    new org.springframework.http.HttpEntity<>(body, headers),
                    com.docintell.dto.EditorDtos.ConvertedContent.class);
        } catch (org.springframework.web.client.HttpClientErrorException e) {
            throw new com.docintell.exception.ConversionException(extractDetail(e.getResponseBodyAsString(java.nio.charset.StandardCharsets.UTF_8), "Формат файла не поддерживается"));
        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /editor/import: {}", e.getMessage());
            throw new com.docintell.exception.ConversionException("Сервис преобразования документов недоступен. Попробуйте ещё раз через минуту.");
        }
    }

    /** Проверка текста по правилам (AI-сервис /editor/check). */
    public com.fasterxml.jackson.databind.JsonNode checkDocument(String html, String documentType, Long docId, boolean deep) {
        try {
            // docId — для сверки с остальными документами базы, deep — смысловая проверка языковой моделью
            return restTemplate.postForObject(aiServiceUrl + "/editor/check",
                    java.util.Map.of("html", html == null ? "" : html, "documentType", documentType == null ? "" : documentType,
                            "docId", docId, "deep", deep),
                    com.fasterxml.jackson.databind.JsonNode.class);
        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /editor/check: {}", e.getMessage());
            throw new com.docintell.exception.ConversionException("Проверка недоступна: сервис анализа не отвечает");
        }
    }

    /** Индексирует документ для поиска; в ответе — поля карточки ({"fields": {...}}). */
    public com.fasterxml.jackson.databind.JsonNode indexDocument(Long id, String title, String html) {
        return restTemplate.postForObject(aiServiceUrl + "/search/index",
                java.util.Map.of("id", id, "title", title == null ? "" : title, "html", html == null ? "" : html),
                com.fasterxml.jackson.databind.JsonNode.class);
    }

    public void removeFromIndex(Long id) {
        restTemplate.delete(aiServiceUrl + "/search/index/" + id);
    }

    /** Сверка индекса с базой: в ответе — missing (каких документов не хватает). */
    public com.fasterxml.jackson.databind.JsonNode syncIndex(java.util.List<Long> ids) {
        return restTemplate.postForObject(aiServiceUrl + "/search/sync", java.util.Map.of("ids", ids),
                com.fasterxml.jackson.databind.JsonNode.class);
    }

    public com.fasterxml.jackson.databind.JsonNode search(String q, String mode, java.util.List<Long> ids, int limit) {
        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("q", q);
        body.put("mode", mode);
        body.put("ids", ids);
        body.put("limit", limit);
        try {
            return restTemplate.postForObject(aiServiceUrl + "/search/query", body, com.fasterxml.jackson.databind.JsonNode.class);
        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /search/query: {}", e.getMessage());
            throw new com.docintell.exception.ConversionException("Поиск недоступен: сервис анализа не отвечает");
        }
    }

    /** Вопрос ассистенту по базе: карточки документов передаём мы, текст AI-сервис берёт из индекса. */
    public com.fasterxml.jackson.databind.JsonNode askAssistant(String question, com.fasterxml.jackson.databind.JsonNode context,
                                                                java.util.List<java.util.Map<String, Object>> docs, Long docId) {
        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("question", question == null ? "" : question);
        body.put("context", context == null || context.isNull() ? null : context);
        body.put("docs", docs);
        body.put("docId", docId);
        try {
            return restTemplate.postForObject(aiServiceUrl + "/assistant/ask", body, com.fasterxml.jackson.databind.JsonNode.class);
        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /assistant/ask: {}", e.getMessage());
            throw new com.docintell.exception.ConversionException("Ассистент недоступен: сервис анализа не отвечает");
        }
    }

    /** Состояние языковой модели ({"available", "model", "reason"}). */
    public com.fasterxml.jackson.databind.JsonNode assistantStatus() {
        try {
            return restTemplate.getForObject(aiServiceUrl + "/assistant/status", com.fasterxml.jackson.databind.JsonNode.class);
        } catch (RestClientException e) {
            throw new com.docintell.exception.ConversionException("Сервис анализа не отвечает");
        }
    }

    /** Собирает DOCX из HTML редактора (AI-сервис /editor/export-docx). */
    public byte[] exportDocx(String html, String title) {
        try {
            return restTemplate.postForObject(aiServiceUrl + "/editor/export-docx",
                    java.util.Map.of("html", html == null ? "" : html, "title", title == null ? "" : title), byte[].class);
        } catch (RestClientException e) {
            logger.error("Ошибка при вызове AI-сервиса /editor/export-docx: {}", e.getMessage());
            throw new com.docintell.exception.ConversionException("Не удалось собрать DOCX: сервис преобразования недоступен");
        }
    }

    /** Достаёт поле "detail" из JSON-ответа FastAPI. */
    private static String extractDetail(String json, String fallback) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\"detail\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(json == null ? "" : json);
        if (!m.find()) {
            return fallback;
        }
        String s = m.group(1).replace("\\\"", "\"");
        // FastAPI экранирует кириллицу как \\uXXXX
        java.util.regex.Matcher u = java.util.regex.Pattern.compile("\\\\u([0-9a-fA-F]{4})").matcher(s);
        StringBuilder sb = new StringBuilder();
        while (u.find()) {
            u.appendReplacement(sb, java.util.regex.Matcher.quoteReplacement(String.valueOf((char) Integer.parseInt(u.group(1), 16))));
        }
        u.appendTail(sb);
        return sb.toString();
    }

    /**
     * Рендерит страницу документа (PDF) в PNG через AI-сервис.
     */
    public byte[] renderPage(byte[] fileBytes, String originalFilename, int page) {
        try {
            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.MULTIPART_FORM_DATA);

            org.springframework.util.MultiValueMap<String, Object> body = new org.springframework.util.LinkedMultiValueMap<>();
            org.springframework.core.io.ByteArrayResource fileResource = new org.springframework.core.io.ByteArrayResource(fileBytes) {
                @Override
                public String getFilename() {
                    return originalFilename;
                }
            };
            body.add("file", fileResource);

            String url = aiServiceUrl + "/render-page?page=" + page;
            org.springframework.http.HttpEntity<org.springframework.util.MultiValueMap<String, Object>> requestEntity =
                    new org.springframework.http.HttpEntity<>(body, headers);

            return restTemplate.postForObject(url, requestEntity, byte[].class);
        } catch (Exception e) {
            logger.warn("Ошибка вызова /render-page: {}", e.getMessage());
            throw new RuntimeException("Не удалось отрендерить страницу: " + e.getMessage(), e);
        }
    }

    /**
     * Получить результаты последнего эксперимента/бенчмарка.
     */
    public String getLatestExperiments() {
        try {
            return restTemplate.getForObject(aiServiceUrl + "/experiments/latest", String.class);
        } catch (Exception e) {
            logger.warn("Не удалось получить результаты экспериментов: {}", e.getMessage());
            return "{\"status\": \"not_run\", \"summary\": null, \"table\": []}";
        }
    }

    /**
     * Запустить стресс-тестирование и бенчмарк моделей.
     */
    public String runExperiments(boolean quickMode) {
        try {
            String url = aiServiceUrl + "/experiments/run?quick_mode=" + quickMode;
            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            org.springframework.http.HttpEntity<Void> entity = new org.springframework.http.HttpEntity<>(headers);
            return restTemplate.postForObject(url, entity, String.class);
        } catch (Exception e) {
            logger.error("Ошибка запуска эксперимента: {}", e.getMessage());
            throw new RuntimeException("Не удалось запустить эксперимент: " + e.getMessage(), e);
        }
    }

    /**
     * Задать вопрос к документу через вопросно-ответную систему AI-сервиса (Document Q&A).
     */
    public com.docintell.dto.ai.AskQuestionResponseDto askQuestion(com.docintell.dto.ai.AskQuestionRequestDto request) {
        try {
            String url = aiServiceUrl + "/qa/ask";
            logger.info("Отправка вопроса к документу в AI-сервис: '{}'", request.question());
            return restTemplate.postForObject(url, request, com.docintell.dto.ai.AskQuestionResponseDto.class);
        } catch (Exception e) {
            logger.error("Ошибка вызова /qa/ask: {}", e.getMessage(), e);
            throw new RuntimeException("Ошибка вопросно-ответного сервиса: " + e.getMessage(), e);
        }
    }
}
