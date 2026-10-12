package com.docintell;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Точка входа приложения.
 *
 * @SpringBootApplication — это аннотация-комбинация, которая включает:
 * - @Configuration — этот класс может содержать настройки Spring
 * - @EnableAutoConfiguration — Spring автоматически настраивает компоненты
 * - @ComponentScan — Spring сканирует пакет com.docintell и находит
 *   все классы с аннотациями @Controller, @Service, @Repository и т.д.
 *
 * Проще говоря: Spring Boot видит эту аннотацию и понимает:
 * "Мне нужно найти все компоненты, настроить веб-сервер и запустить приложение."
 */
@SpringBootApplication
public class DocIntelligenceApplication {

    public static void main(String[] args) {
        SpringApplication.run(DocIntelligenceApplication.class, args);
    }
}
