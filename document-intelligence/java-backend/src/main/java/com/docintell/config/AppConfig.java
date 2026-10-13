package com.docintell.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

/**
 * Общая конфигурация приложения.
 */
@Configuration
public class AppConfig {

    @Bean
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) Duration.ofSeconds(5).toMillis());
        factory.setReadTimeout((int) Duration.ofSeconds(300).toMillis());
        return new RestTemplate(factory);
    }

    @Bean
    public org.springframework.boot.CommandLineRunner dbMigrationRunner(org.springframework.jdbc.core.JdbcTemplate jdbcTemplate) {
        return args -> {
            try {
                var constraints = jdbcTemplate.queryForList(
                    "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.CONSTRAINTS WHERE TABLE_NAME = 'DOCUMENT_FIELDS' AND CONSTRAINT_TYPE = 'CHECK'"
                );
                for (var c : constraints) {
                    String name = (String) c.get("CONSTRAINT_NAME");
                    try {
                        jdbcTemplate.execute("ALTER TABLE document_fields DROP CONSTRAINT " + name);
                    } catch (Exception ignored) {}
                }
            } catch (Exception ignored) {}

            try {
                jdbcTemplate.execute("ALTER TABLE document_fields ALTER COLUMN field_type VARCHAR(50)");
            } catch (Exception ignored) {}

            try {
                var docConstraints = jdbcTemplate.queryForList(
                    "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.CONSTRAINTS WHERE TABLE_NAME = 'DOCUMENTS' AND CONSTRAINT_TYPE = 'CHECK'"
                );
                for (var c : docConstraints) {
                    String name = (String) c.get("CONSTRAINT_NAME");
                    try {
                        jdbcTemplate.execute("ALTER TABLE documents DROP CONSTRAINT " + name);
                    } catch (Exception ignored) {}
                }
            } catch (Exception ignored) {}
        };
    }
}
