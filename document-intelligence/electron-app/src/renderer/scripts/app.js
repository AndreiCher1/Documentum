/**
 * App — главный модуль пользовательского интерфейса.
 *
 * Отвечает за:
 * 1. Навигацию между страницами (Dashboard, Upload, Documents...)
 * 2. Обработку действий пользователя (клики, ввод)
 * 3. Обновление UI на основе данных от API
 *
 * Это "дирижёр" интерфейса — координирует все элементы на странице.
 */

const App = {
    /**
     * Инициализация приложения.
     * Вызывается при загрузке страницы.
     */
    init() {
        console.log('Document Intelligence v0.1.0 запущен');
        console.log('Платформа:', window.api ? window.api.platform : 'browser');

        this.setupNavigation();
        this.setupHealthCheck();
        this.setupSettings();

        // Автоматически проверяем здоровье при запуске
        this.checkHealth();
    },

    /**
     * Настройка навигации.
     *
     * При клике на пункт меню:
     * 1. Убираем класс 'active' со всех пунктов меню и страниц
     * 2. Добавляем 'active' нажатому пункту и соответствующей странице
     *
     * data-page атрибут связывает пункт меню с id страницы.
     * Например: data-page="dashboard" → id="page-dashboard"
     */
    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                // Убираем active со всех
                navItems.forEach(i => i.classList.remove('active'));
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

                // Добавляем active нажатому
                item.classList.add('active');
                const pageId = 'page-' + item.dataset.page;
                const page = document.getElementById(pageId);
                if (page) page.classList.add('active');
            });
        });
    },

    /**
     * Настройка кнопки проверки здоровья.
     */
    setupHealthCheck() {
        const btn = document.getElementById('btn-check-health');
        if (btn) {
            btn.addEventListener('click', () => this.checkHealth());
        }
    },

    /**
     * Проверка здоровья системы.
     *
     * 1. Отправляет запрос к Java Backend
     * 2. Java Backend проверяет Python AI-сервис
     * 3. Обновляет карточки статуса на Dashboard
     */
    async checkHealth() {
        const btn = document.getElementById('btn-check-health');
        const resultBox = document.getElementById('health-result');

        // Показываем "Проверка..."
        this.updateStatusBadge('status-java', 'checking', 'Проверка...');
        this.updateStatusBadge('status-ai', 'checking', 'Проверка...');
        this.updateStatusBadge('status-db', 'checking', 'Проверка...');

        if (btn) btn.disabled = true;

        try {
            const health = await ApiClient.checkHealth();

            // Обновляем карточки
            // Java Backend
            if (health.javaBackend === 'running') {
                this.updateStatusBadge('status-java', 'healthy', 'Работает ✓');
            } else {
                this.updateStatusBadge('status-java', 'error', 'Недоступен ✗');
            }

            // AI Service
            if (health.aiService && health.aiService.status === 'healthy') {
                this.updateStatusBadge('status-ai', 'healthy', 'Работает ✓');
            } else if (health.aiService && health.aiService.status === 'unavailable') {
                this.updateStatusBadge('status-ai', 'error', 'Недоступен ✗');
            } else {
                this.updateStatusBadge('status-ai', 'unavailable', 'Неизвестно');
            }

            // Database
            if (health.database === 'connected') {
                this.updateStatusBadge('status-db', 'healthy', 'Подключена ✓');
            } else {
                this.updateStatusBadge('status-db', 'unavailable', 'Не настроена');
            }

            // Показываем подробный результат
            if (resultBox) {
                resultBox.style.display = 'block';
                resultBox.className = 'result-box ' + (health.status === 'healthy' ? 'success' : 'error');
                resultBox.textContent = JSON.stringify(health, null, 2);
            }

        } catch (error) {
            this.updateStatusBadge('status-java', 'error', 'Ошибка ✗');
            this.updateStatusBadge('status-ai', 'unavailable', 'Неизвестно');
            this.updateStatusBadge('status-db', 'unavailable', 'Неизвестно');

            if (resultBox) {
                resultBox.style.display = 'block';
                resultBox.className = 'result-box error';
                resultBox.textContent = 'Ошибка подключения:\n' + error.message +
                    '\n\nУбедитесь, что Java Backend запущен на ' + ApiClient.baseUrl;
            }
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    /**
     * Обновить бейдж статуса на карточке.
     *
     * @param {string} cardId — id карточки (status-java, status-ai, status-db)
     * @param {string} status — CSS-класс (healthy, error, checking, unavailable)
     * @param {string} text — текст для отображения
     */
    updateStatusBadge(cardId, status, text) {
        const card = document.getElementById(cardId);
        if (!card) return;

        const badge = card.querySelector('.status-badge');
        if (badge) {
            badge.className = 'status-badge ' + status;
            badge.textContent = text;
        }
    },

    /**
     * Настройки.
     */
    setupSettings() {
        const btnSave = document.getElementById('btn-save-settings');
        if (btnSave) {
            btnSave.addEventListener('click', () => {
                const urlInput = document.getElementById('setting-backend-url');
                if (urlInput) {
                    ApiClient.setBaseUrl(urlInput.value);
                    alert('Настройки сохранены!\nJava Backend URL: ' + ApiClient.baseUrl);
                }
            });
        }
    }
};

/**
 * Запускаем приложение, когда DOM полностью загружен.
 *
 * DOMContentLoaded — событие, которое срабатывает,
 * когда HTML-документ полностью прочитан и построен.
 * Это гарантирует, что все элементы (кнопки, div-ы)
 * уже существуют, когда мы начинаем с ними работать.
 */
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
