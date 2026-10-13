/**
 * Main Process — главный процесс Electron.
 *
 * ЧТО ТАКОЕ ELECTRON?
 * Electron — это фреймворк, который позволяет создавать настольные (desktop)
 * приложения, используя веб-технологии: HTML, CSS, JavaScript.
 *
 * Electron состоит из ДВУХ процессов:
 *
 * 1. MAIN PROCESS (этот файл) — "мозг" приложения.
 *    - Управляет окнами
 *    - Имеет доступ к операционной системе (файлы, сеть и т.д.)
 *    - Работает на Node.js
 *    - Создаёт BrowserWindow (окно приложения)
 *
 * 2. RENDERER PROCESS (index.html + скрипты) — "лицо" приложения.
 *    - Отображает интерфейс (HTML/CSS)
 *    - Работает как обычная веб-страница в браузере
 *    - НЕ имеет прямого доступа к Node.js (из соображений безопасности)
 *
 * ПОЧЕМУ ДВА ПРОЦЕССА?
 * Безопасность. Если renderer process имеет доступ к Node.js,
 * то любой XSS (вредоносный скрипт) может читать файлы,
 * удалять данные и т.д. Разделение защищает от этого.
 *
 * КАК ОНИ ОБЩАЮТСЯ?
 * Через preload.js — специальный скрипт-мост, который
 * предоставляет renderer process только БЕЗОПАСНЫЕ функции.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

/**
 * Создание главного окна приложения.
 *
 * BrowserWindow — это одно окно приложения (как вкладка в браузере,
 * но в отдельном окне операционной системы).
 */
function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        title: 'Document Intelligence',
        webPreferences: {
            /**
             * preload — путь к скрипту-мосту.
             * Этот скрипт выполняется ДО загрузки страницы
             * и предоставляет безопасный API для renderer.
             */
            preload: path.join(__dirname, 'preload.js'),

            /**
             * nodeIntegration: false — ОЧЕНЬ ВАЖНО!
             *
             * Если включить nodeIntegration: true, то JavaScript на странице
             * получит доступ ко ВСЕМ возможностям Node.js:
             * - чтение/запись файлов (fs)
             * - выполнение команд (child_process)
             * - доступ к сети
             *
             * Это катастрофа с точки зрения безопасности.
             * Любой XSS-скрипт или вредоносный код может:
             * - Удалить файлы пользователя
             * - Установить вирус
             * - Украсть данные
             *
             * ВСЕГДА оставляйте false.
             */
            nodeIntegration: false,

            /**
             * contextIsolation: true — вторая линия защиты.
             *
             * Изолирует контекст preload-скрипта от контекста веб-страницы.
             * Даже если вредоносный код попадёт на страницу,
             * он не сможет модифицировать функции preload.
             */
            contextIsolation: true,
        }
    });

    // Загружаем главную HTML-страницу
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));

    // В режиме разработки открываем DevTools
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }

    // Клавиша F12 для переключения инструментов разработчика
    mainWindow.webContents.on('before-input-event', (event, input) => {
        if (input.key === 'F12' && input.type === 'keyDown') {
            mainWindow.webContents.toggleDevTools();
        }
    });

    // Блокируем открытие пустых белых окон при скачивании файлов через window.open
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        const { shell } = require('electron');
        if (url.startsWith('https://') || (url.startsWith('http://') && !url.includes('localhost'))) {
            shell.openExternal(url);
        }
        return { action: 'deny' };
    });
}

/**
 * app.whenReady() — ждём, когда Electron полностью инициализируется.
 * После этого создаём окно.
 */
app.whenReady().then(() => {
    createWindow();

    /**
     * macOS: если все окна закрыты, но приложение ещё работает,
     * при клике на иконку в dock — создаём новое окно.
     */
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

/**
 * Закрытие приложения при закрытии всех окон (кроме macOS).
 */
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
