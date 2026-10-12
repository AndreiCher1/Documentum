/**
 * Preload Script — безопасный мост между Main и Renderer процессами.
 *
 * ЗАЧЕМ НУЖЕН PRELOAD?
 *
 * Renderer process (HTML-страница) не имеет доступа к Node.js.
 * Но иногда ему нужно выполнить действия, которые требуют Node.js:
 * - Открыть диалог выбора файла
 * - Прочитать системные настройки
 *
 * Preload — это "мост":
 * - Он выполняется в контексте renderer, но С ДОСТУПОМ к некоторым API Node.js
 * - Через contextBridge он предоставляет renderer ТОЛЬКО те функции,
 *   которые мы явно разрешили
 *
 * Аналогия:
 * Preload — это как секретарь в приёмной.
 * Посетитель (renderer) не может зайти к директору (Node.js) напрямую.
 * Но может попросить секретаря (preload) передать записку.
 *
 * contextBridge.exposeInMainWorld('api', {...}) создаёт объект window.api
 * в renderer, который содержит только разрешённые функции.
 */

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('api', {
    /**
     * Информация о платформе — безопасно, не раскрывает файловую систему.
     */
    platform: process.platform,

    /**
     * Версия приложения.
     */
    appVersion: '0.1.0'
});
