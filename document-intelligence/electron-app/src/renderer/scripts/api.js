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
     * Загрузка документа на сервер (POST /api/documents).
     *
     * @param {File} file — объект файла из input или drop события
     * @returns {Promise<Object>} метаданные загруженного документа
     */
    async uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseUrl}/api/documents`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `Ошибка загрузки (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Получение постраничного списка документов (GET /api/documents).
     */
    async getDocuments(page = 0, size = 20) {
        const response = await fetch(`${this.baseUrl}/api/documents?page=${page}&size=${size}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Ошибка получения списка документов (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Получение последних документов для Dashboard (GET /api/documents/recent).
     */
    async getRecentDocuments(limit = 5) {
        const response = await fetch(`${this.baseUrl}/api/documents/recent?limit=${limit}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Ошибка получения последних документов (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Получение деталей документа по ID (GET /api/documents/{id}).
     */
    async getDocument(id) {
        const response = await fetch(`${this.baseUrl}/api/documents/${id}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Документ #${id} не найден (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Удаление документа (DELETE /api/documents/{id}).
     */
    async deleteDocument(id) {
        const response = await fetch(`${this.baseUrl}/api/documents/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok && response.status !== 204) {
            throw new Error(`Ошибка при удалении документа #${id}`);
        }

        return true;
    },

    /**
     * Получение URL для прямого отображения скана файла.
     */
    getDocumentFileUrl(id) {
        return `${this.baseUrl}/api/documents/${id}/file`;
    },

    /**
     * Получение URL превью страницы документа (для растрирования PDF или кэшированного превью).
     */
    getDocumentPreviewUrl(id, page = 1) {
        return `${this.baseUrl}/api/documents/${id}/preview?page=${page}`;
    },

    /**
     * Запуск AI-анализа документа (POST /api/documents/{id}/analyze).
     */
    async analyzeDocument(id) {
        const response = await fetch(`${this.baseUrl}/api/documents/${id}/analyze`, {
            method: 'POST',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `Ошибка анализа документа #${id} (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Получение результатов анализа документа (GET /api/documents/{id}/analysis).
     */
    async getDocumentAnalysis(id) {
        const response = await fetch(`${this.baseUrl}/api/documents/${id}/analysis`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            if (response.status === 404) return null;
            throw new Error(`Ошибка получения анализа документа #${id} (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Полнотекстовый и параметрический поиск документов (POST /api/search).
     * @param {Object} params — параметры запроса (query, documentType, dateFrom, dateTo, minConfidence, status, page, size)
     */
    async searchDocuments(params = {}) {
        const payload = {
            query: params.query || '',
            documentType: params.documentType && params.documentType !== 'ALL' ? params.documentType : null,
            dateFrom: params.dateFrom || null,
            dateTo: params.dateTo || null,
            minConfidence: params.minConfidence !== undefined && params.minConfidence !== '' ? parseFloat(params.minConfidence) : null,
            status: params.status && params.status !== 'ALL' ? params.status : null,
            page: params.page !== undefined ? params.page : 0,
            size: params.size !== undefined ? params.size : 20
        };

        const response = await fetch(`${this.baseUrl}/api/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `Ошибка выполнения поиска (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Получить сводную статистику системы для Dashboard (GET /api/analytics/dashboard).
     */
    async getDashboardStats() {
        const response = await fetch(`${this.baseUrl}/api/analytics/dashboard`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Ошибка получения аналитики (${response.status})`);
        }

        return await response.json();
    },

    /**
     * URL для скачивания всего реестра в формате Excel CSV (UTF-8 BOM).
     */
    getExportRegistryCsvUrl() {
        return `${this.baseUrl}/api/documents/export/csv`;
    },

    /**
     * URL для скачивания всего реестра в JSON.
     */
    getExportRegistryJsonUrl() {
        return `${this.baseUrl}/api/documents/export/json`;
    },

    /**
     * URL для скачивания реквизитов документа в CSV.
     */
    getDocumentExportCsvUrl(id) {
        return `${this.baseUrl}/api/documents/${id}/export/csv`;
    },

    /**
     * URL для скачивания документа в JSON.
     */
    getDocumentExportJsonUrl(id) {
        return `${this.baseUrl}/api/documents/${id}/export/json`;
    },

    /**
     * Получение результатов последнего эксперимента/бенчмарка (GET /api/experiments/latest).
     */
    async getLatestExperiments() {
        const response = await fetch(`${this.baseUrl}/api/experiments/latest`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`Ошибка получения результатов экспериментов (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Запуск стресс-тестирования моделей (POST /api/experiments/run).
     * @param {boolean} quickMode — быстрый или полный бенчмарк
     */
    async runExperiments(quickMode = true) {
        const response = await fetch(`${this.baseUrl}/api/experiments/run?quickMode=${quickMode}`, {
            method: 'POST',
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `Ошибка запуска эксперимента (${response.status})`);
        }

        return await response.json();
    },

    /**
     * Задать вопрос к документу (POST /api/documents/{id}/ask).
     * @param {number} id — ID документа
     * @param {string} question — текст вопроса
     */
    async askQuestion(id, question) {
        const response = await fetch(`${this.baseUrl}/api/documents/${id}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ question })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `Ошибка вопросно-ответной системы (${response.status})`);
        }

        return await response.json();
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
