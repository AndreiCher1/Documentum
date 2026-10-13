package com.docintell.controller;

import com.docintell.service.AiServiceClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * Контроллер экспериментов и оценки качества (Этап 12: Experiments & Evaluation).
 * Предоставляет API для запуска стресс-тестирования моделей, искажений и получения
 * метрик устойчивости (CER, WER, F1).
 */
@RestController
@RequestMapping("/api/experiments")
public class ExperimentController {

    private static final Logger logger = LoggerFactory.getLogger(ExperimentController.class);

    private final AiServiceClient aiServiceClient;

    public ExperimentController(AiServiceClient aiServiceClient) {
        this.aiServiceClient = aiServiceClient;
    }

    /**
     * GET /api/experiments/latest — получить последние результаты бенчмарка.
     */
    @GetMapping(value = "/latest", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> getLatestResults() {
        logger.info("Запрос результатов последнего эксперимента");
        String json = aiServiceClient.getLatestExperiments();
        return ResponseEntity.ok(json);
    }

    /**
     * POST /api/experiments/run — запустить стресс-тестирование и бенчмарк моделей.
     *
     * @param quickMode быстрый режим (2 образца, 4 типа искажений) vs полный режим (все типы)
     */
    @PostMapping(value = "/run", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> runBenchmark(@RequestParam(defaultValue = "true") boolean quickMode) {
        logger.info("Запуск стресс-теста моделей (quickMode={})", quickMode);
        String reportJson = aiServiceClient.runExperiments(quickMode);
        return ResponseEntity.ok(reportJson);
    }
}

