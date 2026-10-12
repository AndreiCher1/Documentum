/**
 * API Client — модуль для общения с Java Backend.
 *
 * Этот файл содержит все HTTP-запросы к серверу.
 * Все остальные скрипты используют этот модуль
 * вместо того, чтобы делать fetch() напрямую.
 *
 * Зачем отдельный файл?
 * 1. Одно место для изменения URL сервера
 * 2. Одно место для обработки ошибок сети
 * 3. Если API изменится — меняем только этот файл
 *
 * Аналогия: это как "телефонная книга" — содержит все адреса
 * и умеет правильно "звонить" серверу.
 */

const ApiClient = {
    /**
     * Базовый URL Java Backend.
     * По умолчанию: http://localhost:8085
     * Можно изменить в настройках.
     */
    baseUrl: 'http://localhost:8085',

    /**
     * Проверка здоровья всей системы.
     *
     * Вызывает GET /api/health на Java Backend.
     * Java сам проверяет Python AI-сервис и БД.
     *
     * @returns {Promise<Object>} Статус всех сервисов
     */
    async checkHealth() {
        try {
            const response = await fetch(`${this.baseUrl}/api/health`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            // Если Java backend недоступен — возвращаем объект с ошибкой
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                return {
                    status: 'unavailable',
                    javaBackend: 'unavailable',
                    aiService: { status: 'unknown' },
                    database: 'unknown',
                    error: 'Java Backend недоступен. Убедитесь, что сервер запущен на ' + this.baseUrl
                };
            }
            throw error;
        }
    },

    /**
     * Обновить базовый URL.
     * @param {string} url — новый URL
     */
    setBaseUrl(url) {
        this.baseUrl = url.replace(/\/$/, ''); // Убираем trailing slash
        console.log('API URL обновлён:', this.baseUrl);
    }
};
