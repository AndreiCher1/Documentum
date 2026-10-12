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

            AiServiceStatus response = restTemplate.getForObject(
                    aiServiceUrl + "/health",
                    AiServiceStatus.class
            );

            logger.info("AI-сервис доступен: {}", response);
            return response;

        } catch (RestClientException e) {
            logger.warn("AI-сервис недоступен: {}", e.getMessage());
            return null;
        }
    }
}
