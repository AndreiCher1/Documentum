package com.docintell.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;

/**
 * Сервис проверки доступности базы данных: DatabaseHealthService
 *
 * Проверяет активность соединения с СУБД (PostgreSQL / H2).
 * Используется в HealthController для отображения актуального
 * статуса на панели Dashboard в приложении Electron.
 */
@Service
public class DatabaseHealthService {

    private static final Logger logger = LoggerFactory.getLogger(DatabaseHealthService.class);

    private final DataSource dataSource;

    public DatabaseHealthService(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    /**
     * Проверяет соединение с базой данных.
     *
     * @return строка со статусом: "connected (PostgreSQL ...)" или "unavailable"
     */
    public String checkStatus() {
        try (Connection connection = dataSource.getConnection()) {
            if (connection.isValid(2)) {
                DatabaseMetaData meta = connection.getMetaData();
                String dbName = meta.getDatabaseProductName();
                String dbVersion = meta.getDatabaseProductVersion();
                logger.debug("Успешное соединение с БД: {} {}", dbName, dbVersion);
                return "connected (" + dbName + ")";
            }
        } catch (Exception e) {
            logger.warn("Ошибка подключения к базе данных: {}", e.getMessage());
        }
        return "unavailable";
    }
}

