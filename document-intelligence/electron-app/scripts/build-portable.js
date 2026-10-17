/**
 * Скрипт сборки автономной портативной версии Electron UI (Portable Build).
 *
 * Создаёт полностью готовую к переносу на флешку или другой компьютер папку 'portable-ui':
 * - Копирует готовый рантайм Electron (Chromium + Node) из node_modules/electron/dist
 * - Переименовывает electron.exe -> DocIntel-UI.exe
 * - Упаковывает исходный код (src/ и package.json) в resources/app/
 *
 * Полученная папка 'portable-ui' НЕ требует установленного Node.js или npm
 * и запускается в один клик на любой Windows 10/11 x64.
 */

const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..', '..');
const ELECTRON_APP_DIR = path.resolve(__dirname, '..');
const ELECTRON_DIST_DIR = path.join(ELECTRON_APP_DIR, 'node_modules', 'electron', 'dist');
const TARGET_PORTABLE_DIR = path.join(ROOT_DIR, 'portable-ui');

console.log('======================================================================');
console.log('       Сборка портативной версии Document Intelligence UI');
console.log('======================================================================');
console.log(`Исходная папка: ${ELECTRON_APP_DIR}`);
console.log(`Целевая папка:  ${TARGET_PORTABLE_DIR}`);
console.log('');

if (!fs.existsSync(ELECTRON_DIST_DIR)) {
    console.error(`[ОШИБКА] Рантайм Electron не найден по пути:\n${ELECTRON_DIST_DIR}`);
    console.error('Пожалуйста, сначала выполните "npm install" в папке electron-app.');
    process.exit(1);
}

// 1. Создание целевой директории
if (!fs.existsSync(TARGET_PORTABLE_DIR)) {
    fs.mkdirSync(TARGET_PORTABLE_DIR, { recursive: true });
}

// Рекурсивное копирование директории
function copyDirSync(src, dest, excludeNames = []) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
        if (excludeNames.includes(entry.name)) continue;
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
            copyDirSync(srcPath, destPath, excludeNames);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

// 2. Копирование рантайма Electron
console.log('[1/3] Копирование исполняемых компонентов Electron...');
copyDirSync(ELECTRON_DIST_DIR, TARGET_PORTABLE_DIR, ['default_app.asar']);

// 3. Переименование исполняемого файла
const oldExe = path.join(TARGET_PORTABLE_DIR, 'electron.exe');
const newExe = path.join(TARGET_PORTABLE_DIR, 'DocIntel-UI.exe');
if (fs.existsSync(oldExe)) {
    if (fs.existsSync(newExe)) {
        try { fs.unlinkSync(newExe); } catch (e) {}
    }
    fs.renameSync(oldExe, newExe);
    console.log('[OK] Создан исполняемый файл: DocIntel-UI.exe');
}

// 4. Копирование кода приложения в resources/app
console.log('[2/3] Упаковка исходного кода приложения в resources/app...');
const appResourcesDir = path.join(TARGET_PORTABLE_DIR, 'resources', 'app');
if (!fs.existsSync(appResourcesDir)) {
    fs.mkdirSync(appResourcesDir, { recursive: true });
}

// Копируем package.json
fs.copyFileSync(
    path.join(ELECTRON_APP_DIR, 'package.json'),
    path.join(appResourcesDir, 'package.json')
);

// Копируем src/
copyDirSync(
    path.join(ELECTRON_APP_DIR, 'src'),
    path.join(appResourcesDir, 'src')
);

console.log('[3/3] Финализация портативной сборки...');
console.log('');
console.log('======================================================================');
console.log('       [УСПЕХ] Портативная сборка успешно создана!');
console.log(`       Расположение: ${TARGET_PORTABLE_DIR}`);
console.log('       Запуск:       DocIntel-UI.exe (не требует Node.js и npm)');
console.log('======================================================================');

