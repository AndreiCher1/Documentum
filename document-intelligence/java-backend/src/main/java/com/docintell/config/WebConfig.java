package com.docintell.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Настройка CORS (Cross-Origin Resource Sharing).
 *
 * Когда Electron (который работает как браузер) отправляет запросы
 * к Java backend, браузер проверяет, разрешает ли сервер такие запросы.
 *
 * Без CORS-настройки браузер заблокирует запросы от Electron,
 * потому что Electron работает на одном порту (например, localhost:3000),
 * а Java — на другом (localhost:8080).
 *
 * Эта конфигурация говорит: "Разрешаю запросы от Electron".
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("*") // В production ограничить конкретным адресом
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .maxAge(3600); // Кеширование CORS preflight на 1 час
    }
}
