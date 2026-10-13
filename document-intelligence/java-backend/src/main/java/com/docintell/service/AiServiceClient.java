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
