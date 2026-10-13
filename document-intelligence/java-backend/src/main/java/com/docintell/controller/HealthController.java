package com.docintell.controller;

import com.docintell.dto.HealthStatusResponse;
import com.docintell.dto.HealthStatusResponse.AiServiceStatus;
import com.docintell.service.AiServiceClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

/**
 * Контроллер проверки здоровья системы.
 *
 * @RestController — комбинация @Controller + @ResponseBody.
 * Говорит Spring: "Все методы этого класса возвращают данные (JSON),
 * а не HTML-страницы."
 *
 * @RequestMapping("/api") — все URL в этом контроллере начинаются с /api.
 *
 * Контроллер — это "входная дверь" backend.
 * Он принимает HTTP-запросы, вызывает нужный сервис
 * и возвращает ответ клиенту.
 *
 * ВАЖНО: Controller НЕ должен содержать бизнес-логику.
 * Он только:
 * 1. Принимает запрос
 * 2. Вызывает Service
 * 3. Возвращает ответ
 *
 * Почему? Потому что если логика в Controller:
 * - Её нельзя переиспользовать в другом месте
 * - Её сложно тестировать
 * - Код становится огромным и запутанным
 */
@RestController
@RequestMapping("/api")
public class HealthController {

    private static final Logger logger = LoggerFactory.getLogger(HealthController.class);

    private final AiServiceClient aiServiceClient;
    private final com.docintell.service.DatabaseHealthService databaseHealthService;

    public HealthController(
            AiServiceClient aiServiceClient,
            com.docintell.service.DatabaseHealthService databaseHealthService
    ) {
        this.aiServiceClient = aiServiceClient;
        this.databaseHealthService = databaseHealthService;
    }

    /**
     * GET /api/health — проверка здоровья всей системы.
     *
     * Этот endpoint проверяет:
     * 1. Java backend
     * 2. Python AI-сервис (вызываем его /health)
     * 3. База данных (проверяем реальное соединение через DatabaseHealthService)
     */
    @GetMapping("/health")
    public ResponseEntity<HealthStatusResponse> healthCheck() {
        logger.info("Запрос проверки здоровья системы");

        // Проверяем AI-сервис
        AiServiceStatus aiStatus = aiServiceClient.checkHealth();

        // Проверяем базу данных
        String dbStatus = databaseHealthService.checkStatus();

        String overallStatus;
        if (aiStatus != null && dbStatus.startsWith("connected")) {
            overallStatus = "healthy";
        } else {
            overallStatus = "degraded"; // Работаем, но один из компонентов недоступен
            if (aiStatus == null) {
                aiStatus = new AiServiceStatus("unavailable", false, false, "unknown");
            }
        }

        HealthStatusResponse response = new HealthStatusResponse(
                overallStatus,
                "running",
                aiStatus,
                dbStatus,
                LocalDateTime.now()
        );

        logger.info("Статус системы: {}", overallStatus);
        return ResponseEntity.ok(response);
    }
}
