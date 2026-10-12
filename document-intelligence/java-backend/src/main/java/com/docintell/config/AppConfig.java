package com.docintell.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

/**
 * Общая конфигурация приложения.
 *
 * @Bean — это аннотация, которая говорит Spring:
 * "Создай этот объект и сохрани его. Когда кто-то попросит RestTemplate,
 *  отдай именно этот экземпляр."
 *
 * RestTemplate — это HTTP-клиент Spring для выполнения запросов к другим сервисам.
 * Java backend использует его для вызова Python AI-сервиса.
 *
 * Аналогия: RestTemplate — это как встроенный "браузер" внутри Java,
 * который умеет отправлять HTTP-запросы и получать ответы.
 */
@Configuration
public class AppConfig {

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
