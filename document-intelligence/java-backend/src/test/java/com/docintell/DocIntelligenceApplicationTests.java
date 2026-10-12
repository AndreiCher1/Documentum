package com.docintell;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * Базовый тест — проверяет, что Spring Boot контекст загружается без ошибок.
 */
@SpringBootTest
class DocIntelligenceApplicationTests {

    @Test
    void contextLoads() {
        // Если этот тест проходит — значит Spring Boot нашёл все компоненты
        // и смог создать ApplicationContext.
    }
}
