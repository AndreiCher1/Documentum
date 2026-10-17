/**
 * App — главный модуль пользовательского интерфейса.
 *
 * Отвечает за:
 * 1. Навигацию между страницами (Dashboard, Upload, Documents, Search, Settings)
 * 2. Загрузку файлов через Drag-and-Drop и файловый диалог
 * 3. Отображение списка документов и динамической статистики
 * 4. Удаление документов и проверку здоровья сервисов
 */

const App = {
    selectedFile: null,
    uploadQueue: [],
    isUploadingBatch: false,

    init() {
        console.log('Document Intelligence UI запущен');
        console.log('Платформа:', window.api ? window.api.platform : 'browser');

        this.setupNavigation();
        this.setupGlobalControls();
        this.setupHealthCheck();
        this.setupFileUpload();
        this.setupDocumentsPage();
        this.setupAnalysisModal();
        this.setupSearchPage();
        this.setupExperimentsPage();
        this.setupSettings();

        // Проверяем доступность сервисов и загружаем статистику
        this.checkHealth();
        this.loadDashboardData();
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${this.escapeHtml(message)}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 250);
        }, 3200);
    },

    setupGlobalControls() {
        // Global search Ctrl+K shortcut
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                const globalInput = document.getElementById('global-search-input');
                if (globalInput) {
                    globalInput.focus();
                    globalInput.select();
                }
            } else if (e.key === 'Escape') {
                const modal = document.getElementById('analysis-modal');
                if (modal && modal.style.display !== 'none') {
                    this.closeAnalysisModal();
                }
            }
        });

        const globalInput = document.getElementById('global-search-input');
        if (globalInput) {
            globalInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const q = globalInput.value.trim();
                    if (q) {
                        this.navigateTo('search');
                        const searchInput = document.getElementById('search-input');
                        if (searchInput) {
                            searchInput.value = q;
                            this.performSearch();
                        }
                    }
                }
            });
        }

        const topbarUpload = document.getElementById('btn-topbar-upload');
        if (topbarUpload) {
            topbarUpload.addEventListener('click', () => {
                this.navigateTo('upload');
                const fileInput = document.getElementById('file-input');
                if (fileInput) fileInput.click();
            });
        }
    },

    /**
     * Скачивание файла без создания пустого окна в Electron.
     */
    async downloadFile(url, defaultFilename) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;

            let filename = defaultFilename;
            const disposition = response.headers.get('content-disposition');
            if (disposition && disposition.includes('filename=')) {
                const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (match && match[1]) {
                    filename = match[1].replace(/['"]/g, '').trim();
                }
            }
            a.download = filename || 'download.json';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
        } catch (err) {
            console.error('Ошибка прямого скачивания файла:', err);
            const a = document.createElement('a');
            a.href = url;
            if (defaultFilename) a.download = defaultFilename;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    },

    /**
     * Настройка навигации по вкладкам.
     */
    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const targetPage = item.dataset.page;
                this.navigateTo(targetPage);
            });
        });

        // Быстрая кнопка перехода к загрузке с Dashboard
        const quickUploadBtn = document.getElementById('btn-quick-upload');
        if (quickUploadBtn) {
            quickUploadBtn.addEventListener('click', () => this.navigateTo('documents'));
        }
    },

    navigateTo(pageName) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

        const navItem = document.querySelector(`.nav-item[data-page="${pageName}"]`);
        const page = document.getElementById(`page-${pageName}`);

        if (navItem) navItem.classList.add('active');
        if (page) page.classList.add('active');

        // Обновляем хлебные крошки
        const breadcrumbEl = document.getElementById('breadcrumb-active-page');
        if (breadcrumbEl) {
            const pageTitles = {
                'dashboard': 'Обзор архива',
                'documents': 'Реестр документов',
                'upload': 'Загрузка и конвейер',
                'search': 'Интеллектуальный поиск',
                'experiments': 'Эксперименты и метрики',
                'settings': 'Настройки системы'
            };
            breadcrumbEl.textContent = pageTitles[pageName] || pageName;
        }

        // При переходе на вкладку документов — обновляем список
        if (pageName === 'documents') {
            this.loadDocuments();
        } else if (pageName === 'dashboard') {
            this.loadDashboardData();
        } else if (pageName === 'search') {
            this.performSearch();
        } else if (pageName === 'experiments') {
            this.loadExperimentsData();
        }
    },

    /**
     * Настройка проверки доступности сервисов.
     */
    setupHealthCheck() {
        const btn = document.getElementById('btn-check-health');
        if (btn) {
            btn.addEventListener('click', () => this.checkHealth());
        }
    },

    setLedState(name, state) {
        const led = document.getElementById(`led-${name}`);
        const popLed = document.getElementById(`pop-led-${name}`);
        if (led) led.className = `status-led ${state}`;
        if (popLed) popLed.className = `status-led ${state}`;
    },

    async checkHealth() {
        const btn = document.getElementById('btn-check-health');
        const resultBox = document.getElementById('health-result');

        this.setLedState('java', 'checking');
        this.setLedState('ai', 'checking');
        this.setLedState('db', 'checking');

        this.updateStatusBadge('status-java', 'checking', 'Проверка...');
        this.updateStatusBadge('status-ai', 'checking', 'Проверка...');
        this.updateStatusBadge('status-db', 'checking', 'Проверка...');

        if (btn) btn.disabled = true;

        try {
            const health = await ApiClient.checkHealth();

            const javaOk = health.javaBackend === 'running';
            const aiOk = health.aiService && health.aiService.status === 'healthy';
            const dbOk = health.database && (health.database.startsWith('connected') || health.database === 'connected');

            this.setLedState('java', javaOk ? 'healthy' : 'error');
            this.setLedState('ai', aiOk ? 'healthy' : 'error');
            this.setLedState('db', dbOk ? 'healthy' : 'error');

            const popValJava = document.getElementById('pop-val-java');
            const popValAi = document.getElementById('pop-val-ai');
            const popValDb = document.getElementById('pop-val-db');
            const popTime = document.getElementById('popover-timestamp');

            if (popValJava) popValJava.textContent = javaOk ? 'Online (:8085)' : 'Offline';
            if (popValAi) popValAi.textContent = aiOk ? `Online (:8000, v${health.aiService.version || '0.1.0'})` : 'Offline';
            if (popValDb) popValDb.textContent = dbOk ? `${health.database}` : 'Not connected';
            if (popTime) popTime.textContent = new Date().toLocaleTimeString('ru-RU');

            // Legacy badge support
            if (javaOk) {
                this.updateStatusBadge('status-java', 'healthy', 'Работает ✓');
            } else {
                this.updateStatusBadge('status-java', 'error', 'Недоступен ✗');
            }

            if (aiOk) {
                this.updateStatusBadge('status-ai', 'healthy', 'Работает ✓');
            } else {
                this.updateStatusBadge('status-ai', 'error', 'Недоступен ✗');
            }

            if (dbOk) {
                this.updateStatusBadge('status-db', 'healthy', 'Подключена ✓');
            } else {
                this.updateStatusBadge('status-db', 'error', 'Недоступна ✗');
            }

            if (resultBox) {
                resultBox.className = 'result-box ' + (health.status === 'healthy' ? 'success' : 'error');
                resultBox.textContent = JSON.stringify(health, null, 2);
            }
        } catch (error) {
            this.setLedState('java', 'error');
            this.setLedState('ai', 'error');
            this.setLedState('db', 'error');

            this.updateStatusBadge('status-java', 'error', 'Ошибка ✗');
            this.updateStatusBadge('status-ai', 'unavailable', 'Неизвестно');
            this.updateStatusBadge('status-db', 'unavailable', 'Неизвестно');

            if (resultBox) {
                resultBox.className = 'result-box error';
                resultBox.textContent = 'Ошибка подключения:\n' + error.message;
            }
        } finally {
            if (btn) btn.disabled = false;
        }
    },

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
     * Настройка страницы загрузки документов (Drag-and-Drop + Пакетная очередь).
     */
    setupFileUpload() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const btnBrowse = document.getElementById('btn-browse-file');
        const btnBatchUpload = document.getElementById('btn-batch-upload-all');
        const btnBatchClear = document.getElementById('btn-batch-clear-all');

        if (!dropZone || !fileInput) return;

        // Открытие файлового диалога
        btnBrowse.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });

        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                this.handleFilesAdded(Array.from(e.target.files));
                fileInput.value = ''; // сброс для повторного выбора тех же файлов
            }
        });

        // Drag-and-drop события
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt.files && dt.files.length > 0) {
                this.handleFilesAdded(Array.from(dt.files));
            }
        });

        if (btnBatchClear) {
            btnBatchClear.addEventListener('click', () => this.clearBatchQueue());
        }

        if (btnBatchUpload) {
            btnBatchUpload.addEventListener('click', () => this.startBatchUpload());
        }
    },

    handleFilesAdded(files) {
        if (!files || files.length === 0) return;

        files.forEach(file => {
            // Предотвращаем дублирование по имени и размеру в очереди
            const exists = this.uploadQueue.some(item => item.file.name === file.name && item.file.size === file.size);
            if (!exists) {
                this.uploadQueue.push({
                    id: 'queue_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
                    file: file,
                    status: 'pending', // pending, uploading, completed, failed
                    error: null,
                    result: null
                });
            }
        });

        this.renderBatchQueue();
    },

    removeQueueItem(queueId) {
        if (this.isUploadingBatch) return;
        this.uploadQueue = this.uploadQueue.filter(item => item.id !== queueId);
        this.renderBatchQueue();
    },

    clearBatchQueue() {
        if (this.isUploadingBatch) return;
        this.uploadQueue = [];
        this.renderBatchQueue();
        const statusEl = document.getElementById('upload-status');
        if (statusEl) statusEl.style.display = 'none';
        const overallProgress = document.getElementById('batch-overall-progress');
        if (overallProgress) overallProgress.style.display = 'none';
    },

    renderBatchQueue() {
        const container = document.getElementById('batch-upload-container');
        const countEl = document.getElementById('batch-file-count');
        const btnCountEl = document.getElementById('batch-upload-btn-count');
        const sizeEl = document.getElementById('batch-total-size');
        const listEl = document.getElementById('batch-files-list');

        if (!container || !listEl) return;

        if (this.uploadQueue.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';

        const totalBytes = this.uploadQueue.reduce((acc, item) => acc + item.file.size, 0);
        const pendingCount = this.uploadQueue.filter(item => item.status === 'pending').length;

        if (countEl) countEl.textContent = this.uploadQueue.length;
        if (btnCountEl) btnCountEl.textContent = pendingCount;
        if (sizeEl) sizeEl.textContent = 'Общий объём: ' + this.formatFileSize(totalBytes);

        listEl.innerHTML = this.uploadQueue.map(item => {
            let statusBadge = '';
            if (item.status === 'pending') {
                statusBadge = '<span class="status-pill info"><span class="dot"></span><span>В очереди</span></span>';
            } else if (item.status === 'uploading') {
                statusBadge = '<span class="status-pill info"><span class="dot"></span><span>Загрузка...</span></span>';
            } else if (item.status === 'completed') {
                statusBadge = `<span class="status-pill success"><span class="dot"></span><span>Загружен (#${item.result ? item.result.id : ''})</span></span>`;
            } else if (item.status === 'failed') {
                statusBadge = `<span class="status-pill danger" title="${this.escapeHtml(item.error || '')}"><span class="dot"></span><span>Ошибка</span></span>`;
            }

            const ext = item.file.name.split('.').pop().toLowerCase();
            let formatClass = 'txt';
            if (ext === 'pdf') formatClass = 'pdf';
            else if (['docx', 'doc'].includes(ext)) formatClass = 'docx';
            else if (['xlsx', 'xls', 'csv'].includes(ext)) formatClass = 'xlsx';
            else if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) formatClass = 'img';

            return `
                <div class="batch-file-item ${item.status}" id="queue-item-${item.id}">
                    <div class="batch-file-main">
                        <span class="format-badge ${formatClass}">${ext.toUpperCase()}</span>
                        <div class="batch-file-meta-col">
                            <span class="batch-file-name" title="${this.escapeHtml(item.file.name)}">${this.escapeHtml(item.file.name)}</span>
                            <span class="batch-file-sub">${this.formatFileSize(item.file.size)}</span>
                        </div>
                    </div>
                    <div class="batch-file-actions">
                        ${statusBadge}
                        ${item.status === 'pending' && !this.isUploadingBatch ? `
                            <button class="btn-remove-batch-item" onclick="App.removeQueueItem('${item.id}')" title="Удалить из очереди">&times;</button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    },

    async startBatchUpload() {
        if (this.isUploadingBatch) return;

        const pendingItems = this.uploadQueue.filter(item => item.status === 'pending');
        if (pendingItems.length === 0) {
            alert('Все файлы в очереди уже загружены или очередь пуста!');
            return;
        }

        this.isUploadingBatch = true;

        const btnBatchUpload = document.getElementById('btn-batch-upload-all');
        const btnBatchClear = document.getElementById('btn-batch-clear-all');
        const progressWrapper = document.getElementById('batch-overall-progress');
        const progressFill = document.getElementById('batch-progress-fill');
        const progressText = document.getElementById('batch-progress-text');
        const progressPercent = document.getElementById('batch-progress-percent');
        const statusEl = document.getElementById('upload-status');

        if (btnBatchUpload) btnBatchUpload.disabled = true;
        if (btnBatchClear) btnBatchClear.disabled = true;
        if (progressWrapper) progressWrapper.style.display = 'block';

        let completedSuccess = 0;
        let failedCount = 0;
        const totalToUpload = pendingItems.length;

        for (let i = 0; i < totalToUpload; i++) {
            const item = pendingItems[i];
            item.status = 'uploading';
            this.renderBatchQueue();

            const currentIdx = i + 1;
            const pct = Math.round((i / totalToUpload) * 100);
            if (progressFill) progressFill.style.width = pct + '%';
            if (progressPercent) progressPercent.textContent = pct + '%';
            if (progressText) progressText.textContent = `Загрузка файла ${currentIdx} из ${totalToUpload}: ${item.file.name}...`;

            try {
                const result = await ApiClient.uploadDocument(item.file);
                item.status = 'completed';
                item.result = result;
                completedSuccess++;
            } catch (err) {
                console.error(`Ошибка загрузки ${item.file.name}:`, err);
                item.status = 'failed';
                item.error = err.message || 'Ошибка сети';
                failedCount++;
            }

            this.renderBatchQueue();
        }

        if (progressFill) progressFill.style.width = '100%';
        if (progressPercent) progressPercent.textContent = '100%';
        if (progressText) progressText.textContent = `Завершено! Успешно: ${completedSuccess}, Ошибок: ${failedCount}`;

        if (statusEl) {
            statusEl.style.display = 'block';
            statusEl.className = 'alert-box ' + (failedCount === 0 ? 'success' : 'warning');
            statusEl.innerHTML = `Пакетная загрузка завершена. Загружено документов: <strong>${completedSuccess}</strong>${failedCount > 0 ? `, ошибок: <strong>${failedCount}</strong>` : ''}. <a href="#" style="color: var(--accent); margin-left: 10px;" onclick="App.navigateTo('documents'); return false;">Перейти в Реестр документов →</a>`;
        }

        this.isUploadingBatch = false;
        if (btnBatchUpload) btnBatchUpload.disabled = false;
        if (btnBatchClear) btnBatchClear.disabled = false;

        // Обновляем статистику Dashboard
        this.loadDashboardData();
    },

    /**
     * Настройка вкладки "Документы" и загрузка реестра.
     */
    setupDocumentsPage() {
        const btnRefresh = document.getElementById('btn-refresh-docs');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => this.loadDocuments());
        }

        const btnExportCsv = document.getElementById('btn-export-registry-csv');
        if (btnExportCsv) {
            btnExportCsv.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryCsvUrl(), 'registry_export.csv');
                this.showToast('Экспорт реестра в CSV начат', 'info');
            });
        }

        const btnExportJson = document.getElementById('btn-export-registry-json');
        if (btnExportJson) {
            btnExportJson.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryJsonUrl(), 'registry_export.json');
                this.showToast('Экспорт реестра в JSON начат', 'info');
            });
        }

        // Segment Tabs filtering
        const segTabs = document.querySelectorAll('#registry-segment-tabs .segment-btn');
        segTabs.forEach(btn => {
            btn.addEventListener('click', () => {
                segTabs.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentSegment = btn.dataset.segment;
                this.applyDocumentFilters();
            });
        });

        // Search input inside registry
        const searchInput = document.getElementById('table-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', () => this.applyDocumentFilters());
        }

        // Select All Checkbox
        const selectAll = document.getElementById('select-all-docs');
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                document.querySelectorAll('.doc-row-check').forEach(ch => ch.checked = e.target.checked);
                this.updateBulkSelection();
            });
        }

        // Floating Bulk Action Bar Buttons
        const bulkExportCsv = document.getElementById('bulk-btn-export-csv');
        if (bulkExportCsv) {
            bulkExportCsv.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryCsvUrl(), 'selected_export.csv');
                this.showToast('Экспорт выбранных документов в CSV', 'info');
            });
        }

        const bulkExportJson = document.getElementById('bulk-btn-export-json');
        if (bulkExportJson) {
            bulkExportJson.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryJsonUrl(), 'selected_export.json');
                this.showToast('Экспорт выбранных документов в JSON', 'info');
            });
        }

        const bulkDelete = document.getElementById('bulk-btn-delete');
        if (bulkDelete) {
            bulkDelete.addEventListener('click', async () => {
                const checked = Array.from(document.querySelectorAll('.doc-row-check:checked')).map(c => Number(c.dataset.id));
                if (checked.length === 0) return;
                if (!confirm(`Вы действительно хотите удалить ${checked.length} выбранных документов?`)) return;

                let deletedCount = 0;
                for (const id of checked) {
                    try {
                        await ApiClient.deleteDocument(id);
                        deletedCount++;
                    } catch (e) {
                        console.error('Ошибка удаления:', e);
                    }
                }
                this.showToast(`Успешно удалено документов: ${deletedCount}`, 'success');
                this.loadDocuments();
                this.loadDashboardData();
            });
        }

        const tbody = document.getElementById('documents-table-body');
        if (tbody) {
            tbody.addEventListener('change', (e) => {
                if (e.target.classList.contains('doc-row-check')) {
                    this.updateBulkSelection();
                }
            });

            tbody.addEventListener('click', (e) => {
                const btn = e.target.closest('button');
                if (!btn) return;
                const action = btn.dataset.action;
                const id = Number(btn.dataset.id);
                if (!action || !id) return;

                console.log(`Нажата кнопка '${action}' для документа #${id}`);
                if (action === 'analyze') {
                    this.openAnalysisModal(id);
                } else if (action === 'view') {
                    this.viewDocumentFile(id);
                } else if (action === 'export-csv') {
                    this.downloadFile(ApiClient.getDocumentExportCsvUrl(id), `document_${id}_export.csv`);
                } else if (action === 'export-json') {
                    this.downloadFile(ApiClient.getDocumentExportJsonUrl(id), `document_${id}_export.json`);
                } else if (action === 'delete') {
                    this.confirmDeleteDocument(id);
                }
            });
        }
    },

    updateBulkSelection() {
        const checks = document.querySelectorAll('.doc-row-check:checked');
        const bulkBar = document.getElementById('floating-bulk-bar');
        const countEl = document.getElementById('bulk-selected-count');
        if (!bulkBar) return;

        if (checks.length > 0) {
            bulkBar.classList.add('visible');
            if (countEl) countEl.textContent = `Выбрано: ${checks.length}`;
        } else {
            bulkBar.classList.remove('visible');
        }
    },

    async loadDocuments() {
        const tbody = document.getElementById('documents-table-body');
        if (!tbody) return;

        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 32px 0;">Загрузка реестра документов...</td></tr>`;

        try {
            const data = await ApiClient.getDocuments(0, 100);
            this.allDocuments = data.content || [];
            this.applyDocumentFilters();
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--danger-text); padding: 32px 0;">Ошибка загрузки реестра: ${this.escapeHtml(error.message)}</td></tr>`;
        }
    },

    applyDocumentFilters() {
        const tbody = document.getElementById('documents-table-body');
        if (!tbody || !this.allDocuments) return;

        const segment = this.currentSegment || 'all';
        const searchQuery = (document.getElementById('table-search-input')?.value || '').toLowerCase().trim();

        // Counts for segment buttons and sidebar
        const allCount = this.allDocuments.length;
        const reviewCount = this.allDocuments.filter(d => (d.overallConfidence || 0) < 0.85 || d.status === 'FAILED').length;
        const procCount = this.allDocuments.filter(d => d.status === 'PROCESSING' || d.status === 'UPLOADED').length;
        const compCount = this.allDocuments.filter(d => d.status === 'COMPLETED').length;

        const elAll = document.getElementById('segment-all-count');
        const elRev = document.getElementById('segment-review-count');
        const elProc = document.getElementById('segment-proc-count');
        const elComp = document.getElementById('segment-comp-count');
        const elNav = document.getElementById('nav-docs-count');

        if (elAll) elAll.textContent = allCount;
        if (elRev) elRev.textContent = reviewCount;
        if (elProc) elProc.textContent = procCount;
        if (elComp) elComp.textContent = compCount;
        if (elNav) elNav.textContent = allCount;

        let filtered = this.allDocuments.filter(doc => {
            if (segment === 'review') {
                return (doc.overallConfidence || 0) < 0.85 || doc.status === 'FAILED';
            } else if (segment === 'processing') {
                return doc.status === 'PROCESSING' || doc.status === 'UPLOADED';
            } else if (segment === 'completed') {
                return doc.status === 'COMPLETED';
            }
            return true;
        });

        if (searchQuery) {
            filtered = filtered.filter(doc => {
                const name = (doc.originalFilename || '').toLowerCase();
                const type = this.getDisplayDocType(doc).toLowerCase();
                return name.includes(searchQuery) || type.includes(searchQuery);
            });
        }

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px 0;">Документов в данной категории не найдено</td></tr>`;
            this.updateBulkSelection();
            return;
        }

        tbody.innerHTML = filtered.map(doc => {
            const conf = doc.overallConfidence ? Math.round(doc.overallConfidence * 100) : 0;
            const confClass = conf >= 85 ? 'high' : (conf >= 50 ? 'mid' : 'low');
            const statusClass = doc.status === 'COMPLETED' ? 'success' : (doc.status === 'FAILED' ? 'danger' : 'info');

            const ext = (doc.originalFilename || '').split('.').pop().toLowerCase();
            let formatClass = 'txt';
            if (ext === 'pdf') formatClass = 'pdf';
            else if (['docx', 'doc'].includes(ext)) formatClass = 'docx';
            else if (['xlsx', 'xls', 'csv'].includes(ext)) formatClass = 'xlsx';
            else if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) formatClass = 'img';

            return `
                <tr data-doc-id="${doc.id}">
                    <td><input type="checkbox" class="doc-row-check" data-id="${doc.id}" /></td>
                    <td>
                        <div class="doc-name-cell">
                            <span class="format-badge ${formatClass}">${ext.toUpperCase()}</span>
                            <div>
                                <div class="doc-title-link" onclick="App.openAnalysisModal(${doc.id})">
                                    ${this.escapeHtml(doc.originalFilename)}
                                </div>
                                <div class="doc-size-text">${this.formatFileSize(doc.fileSize)} • #${doc.id}</div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="category-badge">
                            ${this.escapeHtml(this.getDisplayDocType(doc))}
                        </span>
                    </td>
                    <td>
                        <span class="status-pill ${statusClass}">
                            <span class="dot"></span>
                            <span>${doc.status}</span>
                        </span>
                    </td>
                    <td>
                        <div class="confidence-cell">
                            <div class="conf-mini-track">
                                <div class="conf-mini-fill ${confClass}" style="width: ${conf}%;"></div>
                            </div>
                            <span class="conf-pct-text">${conf}%</span>
                        </div>
                    </td>
                    <td>
                        <span style="font-family: var(--font-mono); font-weight: 500;">
                            ${doc.fieldsCount || 0}
                        </span>
                    </td>
                    <td>
                        <span style="font-size: 11.5px; color: var(--text-secondary);" title="${doc.createdAt}">
                            ${this.formatDate(doc.createdAt)}
                        </span>
                    </td>
                    <td style="text-align: right;">
                        <div class="actions-cell" style="justify-content: flex-end;">
                            <button class="table-btn" onclick="App.openAnalysisModal(${doc.id})" title="Инспектор документа">
                                <svg><use href="#icon-eye"></use></svg>
                            </button>
                            <button class="table-btn" onclick="App.downloadFile(ApiClient.getDocumentExportCsvUrl(${doc.id}), 'document_${doc.id}_export.csv')" title="Экспорт CSV">
                                <svg><use href="#icon-download"></use></svg>
                            </button>
                            <button class="table-btn" onclick="App.downloadFile(ApiClient.getDocumentExportJsonUrl(${doc.id}), 'document_${doc.id}_export.json')" title="Экспорт JSON">
                                <span style="font-size: 9px; font-weight: 700; font-family: var(--font-mono);">JSON</span>
                            </button>
                            <button class="table-btn danger" onclick="App.confirmDeleteDocument(${doc.id})" title="Удалить">
                                <svg><use href="#icon-trash"></use></svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        this.updateBulkSelection();
    },

    viewDocumentFile(id) {
        this.openAnalysisModal(id);
    },

    async confirmDeleteDocument(id) {
        if (!confirm(`Вы действительно хотите удалить документ #${id}?`)) {
            return;
        }

        try {
            await ApiClient.deleteDocument(id);
            this.loadDocuments();
            this.loadDashboardData();
        } catch (error) {
            alert(`Ошибка при удалении: ${error.message}`);
        }
    },

    /**
     * Загрузка сводных данных и аналитики для Dashboard.
     */
    async loadDashboardData() {
        const countEl = document.getElementById('dashboard-total-count');
        const sizeEl = document.getElementById('dashboard-total-size');
        const confEl = document.getElementById('dashboard-avg-confidence');
        const rateEl = document.getElementById('dashboard-success-rate');
        const pillsEl = document.getElementById('dashboard-status-pills');
        const successSubEl = document.getElementById('dashboard-success-sub');
        const catContainer = document.getElementById('dashboard-categories-container');
        const catMeta = document.getElementById('dashboard-categories-meta');
        const recentContainer = document.getElementById('dashboard-recent-list');

        // Подключение кнопок экспорта на Dashboard
        const dashExportCsv = document.getElementById('btn-dashboard-export-csv');
        if (dashExportCsv && !dashExportCsv.dataset.bound) {
            dashExportCsv.dataset.bound = 'true';
            dashExportCsv.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryCsvUrl(), 'registry_export.csv');
            });
        }

        const dashExportJson = document.getElementById('btn-dashboard-export-json');
        if (dashExportJson && !dashExportJson.dataset.bound) {
            dashExportJson.dataset.bound = 'true';
            dashExportJson.addEventListener('click', () => {
                this.downloadFile(ApiClient.getExportRegistryJsonUrl(), 'registry_export.json');
            });
        }

        try {
            const stats = await ApiClient.getDashboardStats();

            if (countEl) countEl.textContent = stats.totalDocuments || 0;
            if (sizeEl) sizeEl.textContent = this.formatFileSize(stats.totalFileSizeBytes || 0);
            if (confEl) confEl.textContent = (stats.averageConfidence !== undefined ? stats.averageConfidence : 0) + '%';
            if (rateEl) rateEl.textContent = (stats.successRate !== undefined ? stats.successRate : 0) + '%';
            if (pillsEl) {
                pillsEl.textContent = `${stats.completedCount || 0} готово • ${(stats.processingCount || 0) + (stats.uploadedCount || 0)} в работе`;
            }
            if (successSubEl) {
                successSubEl.textContent = `${stats.completedCount || 0} из ${stats.totalDocuments || 0} без сбоев`;
            }

            // Расчет документов, требующих проверки оператором
            const reviewCount = (stats.recentDocuments || []).filter(d => (d.overallConfidence || 0) < 0.85 || d.status === 'FAILED').length;
            const reviewEl = document.getElementById('dashboard-review-count');
            if (reviewEl) reviewEl.textContent = reviewCount;

            // Рендер распределения документов по категориям
            if (catContainer) {
                const categories = stats.categories || {};
                const catEntries = Object.entries(categories);

                if (catEntries.length === 0 || stats.totalDocuments === 0) {
                    catContainer.innerHTML = `<p class="text-muted" style="padding: 12px 0;">Категории пока не сформированы. Загрузите и проанализируйте документы.</p>`;
                    if (catMeta) catMeta.textContent = '0 типов';
                } else {
                    if (catMeta) catMeta.textContent = `${catEntries.length} типов определено`;
                    catEntries.sort((a, b) => {
                        const cntA = typeof a[1] === 'object' ? (a[1].count || 0) : (a[1] || 0);
                        const cntB = typeof b[1] === 'object' ? (b[1].count || 0) : (b[1] || 0);
                        return cntB - cntA;
                    });

                    const categoryNames = {
                        'PASSPORT': 'Паспорт РФ',
                        'PASSPORT_RF': 'Паспорт РФ',
                        'PTS': 'Паспорт ТС (ПТС)',
                        'STS': 'Свидетельство ТС (СТС)',
                        'DRIVER_LICENSE': 'Водительское уд.',
                        'RECEIPT': 'Квитанция / ЖКУ',
                        'INVOICE': 'Счёт на оплату',
                        'CONTRACT': 'Договор',
                        'ACT': 'Акт выполненных работ',
                        'WAYBILL': 'Накладная',
                        'TAX_2NDFL': 'Справка 2-НДФЛ',
                        'CERTIFICATE': 'Свидетельство',
                        'UNKNOWN': 'Не определён'
                    };

                    const totalDocs = Math.max(stats.totalDocuments, 1);

                    catContainer.innerHTML = catEntries.map(([typeKey, catData]) => {
                        const count = typeof catData === 'object' ? (catData.count || 0) : (catData || 0);
                        const percent = typeof catData === 'object' && catData.percentage !== undefined
                            ? Math.round(catData.percentage)
                            : Math.round((count / totalDocs) * 100);
                        const name = (typeof catData === 'object' && catData.displayName && !catData.displayName.includes(''))
                            ? catData.displayName
                            : (categoryNames[typeKey] || typeKey);

                        return `
                            <div class="cat-bar-item">
                                <div class="cat-bar-header">
                                    <span class="cat-bar-name">${this.escapeHtml(name)}</span>
                                    <span class="cat-bar-stat">${count} шт. (${percent}%)</span>
                                </div>
                                <div class="cat-bar-track">
                                    <div class="cat-bar-fill" style="width: ${percent}%;"></div>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }

            // Последние обработанные документы
            if (recentContainer) {
                const recentDocs = stats.recentDocuments || [];
                if (recentDocs.length === 0) {
                    recentContainer.innerHTML = `<p class="text-muted" style="padding: 16px 0;">Загруженных документов пока нет.</p>`;
                } else {
                    recentContainer.innerHTML = recentDocs.map(doc => {
                        const conf = doc.overallConfidence ? Math.round(doc.overallConfidence * 100) : 0;
                        const confColor = conf >= 85 ? '#16A34A' : (conf >= 50 ? '#D97706' : '#DC2626');
                        const statusClass = doc.status === 'COMPLETED' ? 'success' : (doc.status === 'FAILED' ? 'danger' : 'info');

                        const ext = (doc.originalFilename || '').split('.').pop().toLowerCase();
                        let formatClass = 'txt';
                        if (ext === 'pdf') formatClass = 'pdf';
                        else if (['docx', 'doc'].includes(ext)) formatClass = 'docx';
                        else if (['xlsx', 'xls', 'csv'].includes(ext)) formatClass = 'xlsx';
                        else if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) formatClass = 'img';

                        return `
                            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); transition: background 0.12s ease;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span class="format-badge ${formatClass}">${ext.toUpperCase()}</span>
                                    <div>
                                        <div style="font-weight: 500; font-size: 12.5px; color: var(--text-primary); cursor: pointer;" onclick="App.openAnalysisModal(${doc.id})">
                                            ${this.escapeHtml(doc.originalFilename)}
                                        </div>
                                        <div style="font-size: 11px; color: var(--text-muted);">
                                            #${doc.id} • ${this.escapeHtml(this.getDisplayDocType(doc))} • ${this.formatDate(doc.createdAt)}
                                        </div>
                                    </div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span class="status-pill ${statusClass}">
                                        <span class="dot"></span>
                                        <span>${doc.status}</span>
                                    </span>
                                    <span style="font-family: var(--font-mono); font-size: 11.5px; font-weight: 600; color: ${confColor};">${conf}%</span>
                                    <button class="table-btn" onclick="App.openAnalysisModal(${doc.id})" title="Инспектор документа">
                                        <svg><use href="#icon-eye"></use></svg>
                                    </button>
                                </div>
                            </div>
                        `;
                    }).join('');
                }
            }

        } catch (e) {
            console.warn('Не удалось загрузить данные Dashboard:', e.message);
        }
    },

    getStatusBadgeClass(status) {
        switch (status) {
            case 'UPLOADED': return 'badge-uploaded';
            case 'PROCESSING': return 'badge-processing';
            case 'COMPLETED': return 'badge-completed';
            case 'FAILED': return 'badge-failed';
            default: return 'badge-uploaded';
        }
    },

    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 Б';
        const k = 1024;
        const sizes = ['Б', 'КБ', 'МБ', 'ГБ'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },

    formatDate(dateString) {
        if (!dateString) return '—';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('ru-RU', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    setupSettings() {
        const btnSave = document.getElementById('btn-save-settings');
        if (btnSave) {
            btnSave.addEventListener('click', () => {
                const urlInput = document.getElementById('setting-backend-url');
                if (urlInput) {
                    ApiClient.setBaseUrl(urlInput.value);
                    alert('Настройки сохранены!\nJava Backend URL: ' + ApiClient.baseUrl);
                    this.checkHealth();
                }
            });
        }
    },

    /**
     * === Эксперименты и Оценка моделей (Этап 12) ===
     */
    setupExperimentsPage() {
        const btnRun = document.getElementById('btn-run-experiments');
        if (btnRun) {
            btnRun.addEventListener('click', () => {
                const selectMode = document.getElementById('experiments-mode-select');
                const quickMode = selectMode ? selectMode.value === 'true' : true;
                this.executeExperimentsBenchmark(quickMode);
            });
        }
    },

    async loadExperimentsData() {
        try {
            const data = await ApiClient.getLatestExperiments();
            if (data && data.summary) {
                this.renderExperimentsReport(data);
            }
        } catch (e) {
            console.warn('Не удалось загрузить последние результаты экспериментов:', e.message);
        }
    },

    async executeExperimentsBenchmark(quickMode = true) {
        const btnRun = document.getElementById('btn-run-experiments');
        const progressBox = document.getElementById('experiments-progress-box');

        if (btnRun) {
            btnRun.disabled = true;
            btnRun.innerHTML = `<span class="status-led checking"></span> <span>Выполняется стресс-тест...</span>`;
        }
        if (progressBox) progressBox.style.display = 'block';

        try {
            const report = await ApiClient.runExperiments(quickMode);
            this.renderExperimentsReport(report);
            this.showToast('Бенчмарк успешно завершен', 'success');
        } catch (error) {
            alert('Ошибка при выполнении эксперимента:\n' + error.message);
        } finally {
            if (btnRun) {
                btnRun.disabled = false;
                btnRun.innerHTML = `<svg><use href="#icon-zap"></use></svg> <span>Запустить бенчмарк</span>`;
            }
            if (progressBox) progressBox.style.display = 'none';
        }
    },

    renderExperimentsReport(data) {
        if (!data || !data.summary) return;

        const s = data.summary;
        const cerVal = document.getElementById('exp-cer-value');
        const cerSub = document.getElementById('exp-cer-sub');
        const werVal = document.getElementById('exp-wer-value');
        const werSub = document.getElementById('exp-wer-sub');
        const f1Val = document.getElementById('exp-f1-value');
        const f1Sub = document.getElementById('exp-f1-sub');
        const accVal = document.getElementById('exp-acc-value');
        const timeSub = document.getElementById('exp-time-sub');
        const timeEl = document.getElementById('experiments-timestamp');
        const tbody = document.getElementById('experiments-table-body');

        if (cerVal) cerVal.textContent = (s.mean_enhanced_cer !== undefined ? s.mean_enhanced_cer : '—') + '%';
        if (cerSub) cerSub.textContent = `Без OpenCV: ${s.mean_baseline_cer || 0}% (снижение на -${s.cer_reduction_pct || 0}%)`;

        if (werVal) werVal.textContent = (s.mean_enhanced_wer !== undefined ? s.mean_enhanced_wer : '—') + '%';
        if (werSub) werSub.textContent = `Без OpenCV: ${s.mean_baseline_wer || 0}%`;

        if (f1Val) f1Val.textContent = (s.mean_enhanced_f1 !== undefined ? s.mean_enhanced_f1 : '—') + '%';
        if (f1Sub) f1Sub.textContent = `Прирост точности: +${s.f1_gain_pct || 0}% (было ${s.mean_baseline_f1 || 0}%)`;

        if (accVal) accVal.textContent = (s.mean_enhanced_accuracy !== undefined ? s.mean_enhanced_accuracy : '—') + '%';
        if (timeSub) timeSub.textContent = `Инференс CPU: ~${s.mean_enhanced_latency_ms || 0} мс`;

        if (timeEl) timeEl.textContent = `Дата запуска: ${s.timestamp || '—'} (исследовано ${s.conditions_count || 0} искажений)`;

        if (tbody && data.table && data.table.length > 0) {
            tbody.innerHTML = data.table.map(row => {
                const reduction = row.cer_reduction > 0
                    ? `<span class="status-badge healthy">-${row.cer_reduction}%</span>`
                    : `<span class="status-badge unavailable">0%</span>`;

                return `
                    <tr>
                        <td><strong>${this.escapeHtml(row.condition_ru || row.condition)}</strong></td>
                        <td style="color: var(--error);">${row.baseline_cer}%</td>
                        <td style="color: var(--success); font-weight: 700;">${row.enhanced_cer}%</td>
                        <td>${reduction}</td>
                        <td>${row.baseline_f1}%</td>
                        <td style="color: var(--accent); font-weight: 700;">${row.enhanced_f1}%</td>
                        <td><span class="status-badge ${row.enhanced_acc >= 80 ? 'healthy' : 'warning'}">${row.enhanced_acc}%</span></td>
                        <td>${row.enhanced_latency_ms} мс</td>
                    </tr>
                `;
            }).join('');
        }
    },

    /**
     * === Полнотекстовый и параметрический поиск (Этап 10) ===
     */
    searchDebounceTimer: null,

    setupSearchPage() {
        const searchInput = document.getElementById('search-input');
        const clearBtn = document.getElementById('search-clear-btn');
        const btnExec = document.getElementById('btn-search-exec');
        const btnReset = document.getElementById('btn-search-reset');
        const filterType = document.getElementById('search-filter-type');
        const filterStatus = document.getElementById('search-filter-status');
        const filterDateFrom = document.getElementById('search-filter-date-from');
        const filterDateTo = document.getElementById('search-filter-date-to');
        const filterConf = document.getElementById('search-filter-conf');
        const confLabel = document.getElementById('search-filter-conf-label');

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                if (clearBtn) clearBtn.style.display = searchInput.value ? 'block' : 'none';
                clearTimeout(this.searchDebounceTimer);
                this.searchDebounceTimer = setTimeout(() => this.performSearch(), 400);
            });

            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    clearTimeout(this.searchDebounceTimer);
                    this.performSearch();
                }
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                clearBtn.style.display = 'none';
                this.performSearch();
            });
        }

        if (filterConf && confLabel) {
            filterConf.addEventListener('input', () => {
                confLabel.textContent = `${filterConf.value}%`;
                clearTimeout(this.searchDebounceTimer);
                this.searchDebounceTimer = setTimeout(() => this.performSearch(), 300);
            });
        }

        [filterType, filterStatus, filterDateFrom, filterDateTo].forEach(el => {
            if (el) {
                el.addEventListener('change', () => this.performSearch());
            }
        });

        if (btnExec) {
            btnExec.addEventListener('click', () => this.performSearch());
        }

        if (btnReset) {
            btnReset.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                if (clearBtn) clearBtn.style.display = 'none';
                if (filterType) filterType.value = 'ALL';
                if (filterStatus) filterStatus.value = 'ALL';
                if (filterDateFrom) filterDateFrom.value = '';
                if (filterDateTo) filterDateTo.value = '';
                if (filterConf) filterConf.value = '0';
                if (confLabel) confLabel.textContent = '0%';
                this.performSearch();
            });
        }
    },

    async performSearch() {
        const searchInput = document.getElementById('search-input');
        const filterType = document.getElementById('search-filter-type');
        const filterStatus = document.getElementById('search-filter-status');
        const filterDateFrom = document.getElementById('search-filter-date-from');
        const filterDateTo = document.getElementById('search-filter-date-to');
        const filterConf = document.getElementById('search-filter-conf');
        const resultsContainer = document.getElementById('search-results-list');
        const resultsCountBadge = document.getElementById('search-results-count');

        if (!resultsContainer) return;

        const query = searchInput ? searchInput.value.trim() : '';
        const docType = filterType ? filterType.value : 'ALL';
        const status = filterStatus ? filterStatus.value : 'ALL';
        const dateFrom = filterDateFrom ? filterDateFrom.value : null;
        const dateTo = filterDateTo ? filterDateTo.value : null;
        const minConf = filterConf ? (parseInt(filterConf.value, 10) / 100.0) : 0;

        resultsContainer.innerHTML = `
            <div class="placeholder-box" style="padding: 40px;">
                <span class="placeholder-icon">⏳</span>
                <p>Выполняется поиск документов...</p>
            </div>
        `;

        try {
            const data = await ApiClient.searchDocuments({
                query,
                documentType: docType,
                status,
                dateFrom,
                dateTo,
                minConfidence: minConf,
                page: 0,
                size: 50
            });

            this.renderSearchResults(data, query);
        } catch (error) {
            console.error('Ошибка поиска документов:', error);
            resultsContainer.innerHTML = `
                <div class="alert-box error" style="display: block;">
                    Не удалось выполнить поиск: ${this.escapeHtml(error.message)}
                </div>
            `;
            if (resultsCountBadge) {
                resultsCountBadge.textContent = 'Ошибка выполнения запроса';
            }
        }
    },

    renderSearchResults(data, query) {
        const resultsContainer = document.getElementById('search-results-list');
        const resultsCountBadge = document.getElementById('search-results-count');

        if (!resultsContainer) return;

        const items = data.items || [];
        const total = data.totalElements !== undefined ? data.totalElements : items.length;

        if (resultsCountBadge) {
            resultsCountBadge.textContent = total > 0
                ? `Найдено документов: ${total}`
                : 'По запросу ничего не найдено';
        }

        if (items.length === 0) {
            resultsContainer.innerHTML = `
                <div class="placeholder-box" style="padding: 40px; text-align: center;">
                    <div style="margin-bottom: 12px; color: var(--text-muted);">
                        <svg style="width: 20px; height: 20px;"><use href="#icon-search"></use></svg>
                    </div>
                    <p style="font-weight: 500;">По вашему запросу ничего не найдено</p>
                    <p class="text-muted" style="font-size: 11.5px;">Попробуйте изменить поисковую фразу или сбросить фильтры</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = items.map(item => {
            const typeDisplay = this.getDisplayDocType(item);
            const statusClass = item.status === 'COMPLETED' ? 'success' : (item.status === 'FAILED' ? 'danger' : 'info');
            const confPct = item.overallConfidence ? Math.round(item.overallConfidence * 100) : 0;
            const sizeStr = this.formatFileSize(item.fileSize);
            const dateStr = this.formatDate(item.createdAt);

            const ext = (item.originalFilename || '').split('.').pop().toLowerCase();
            let formatClass = 'txt';
            if (ext === 'pdf') formatClass = 'pdf';
            else if (['docx', 'doc'].includes(ext)) formatClass = 'docx';
            else if (['xlsx', 'xls', 'csv'].includes(ext)) formatClass = 'xlsx';
            else if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) formatClass = 'img';

            // Бейдж уверенности
            let confBadgeHtml = '';
            if (item.overallConfidence !== null && item.overallConfidence !== undefined && item.overallConfidence > 0) {
                const confColorClass = confPct >= 75 ? 'healthy' : (confPct >= 40 ? 'warning' : 'error');
                confBadgeHtml = `<span class="status-badge ${confColorClass}">${confPct}% уверенность</span>`;
            }

            // Извлечённые поля
            let fieldsHtml = '';
            if (item.matchedFields && item.matchedFields.length > 0) {
                const fieldPills = item.matchedFields.map(f => {
                    const disp = this.escapeHtml(f.displayName || f.fieldName);
                    const val = this.safeHighlightHtml(f.fieldValue);
                    return `<span class="search-field-pill"><span class="search-field-pill-label">${disp}:</span> ${val}</span>`;
                }).join('');
                fieldsHtml = `<div class="search-matched-fields">${fieldPills}</div>`;
            }

            // Сниппеты текста
            let snippetsHtml = '';
            if (item.snippets && item.snippets.length > 0) {
                const snippetItems = item.snippets.map(s => {
                    return `<div class="search-snippet-item"><span style="color: var(--primary); margin-right: 6px;">▪</span>${this.safeHighlightHtml(s)}</div>`;
                }).join('');
                snippetsHtml = `<div class="search-result-snippets">${snippetItems}</div>`;
            }

            return `
                <div class="search-result-card" data-doc-id="${item.documentId}">
                    <div class="search-result-card-header">
                        <div class="search-result-card-header-left">
                            <span class="format-badge ${formatClass}">${ext.toUpperCase()}</span>
                            <div>
                                <div class="search-result-title">${this.safeHighlightHtml(item.originalFilename)}</div>
                                <div class="search-result-sub">
                                    <span>#${item.documentId}</span>
                                    <span>•</span>
                                    <span>${dateStr}</span>
                                    <span>•</span>
                                    <span>${sizeStr}</span>
                                </div>
                            </div>
                        </div>
                        <div class="search-result-badges">
                            <span class="category-badge">${this.escapeHtml(typeDisplay)}</span>
                            <span class="status-pill ${statusClass}">
                                <span class="dot"></span>
                                <span>${item.status}</span>
                            </span>
                            ${confBadgeHtml}
                            <button class="btn btn-sm btn-primary btn-open-inspector" data-doc-id="${item.documentId}">
                                <svg><use href="#icon-eye"></use></svg>
                                <span>Открыть в инспекторе</span>
                            </button>
                        </div>
                    </div>
                    ${fieldsHtml}
                    ${snippetsHtml}
                </div>
            `;
        }).join('');

        // Навешиваем клики на кнопки открытия карточки
        resultsContainer.querySelectorAll('.btn-open-inspector').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const docId = btn.dataset.docId;
                if (docId) this.openAnalysisModal(Number(docId));
            });
        });

        // Также клик по всей карточке открывает документ
        resultsContainer.querySelectorAll('.search-result-card').forEach(card => {
            card.addEventListener('click', () => {
                const docId = card.dataset.docId;
                if (docId) this.openAnalysisModal(Number(docId));
            });
        });
    },

    safeHighlightHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/&lt;mark&gt;/g, '<mark>')
            .replace(/&lt;\/mark&gt;/g, '</mark>');
    },

    getDocTypeBadgeClass(type) {
        switch ((type || '').toUpperCase()) {
            case 'PASSPORT':
            case 'PASSPORT_RF':
                return 'passport';
            case 'PTS':
                return 'pts';
            case 'RECEIPT':
                return 'receipt';
            case 'CONTRACT':
                return 'contract';
            case 'INVOICE':
                return 'invoice';
            default:
                return 'unknown';
        }
    },

    /**
     * === Инспектор документа и AI OCR Анализ ===
     */
    currentAnalysisDocId: null,

    /**
     * === Управление масштабом и слоями скана (Zoom & Pan & Layers) ===
    /**
     * === Управление масштабом, панорамированием и страницами скана ===
     */
    currentAnalysisData: null,
    currentPage: 1,
    totalPages: 1,

    viewerZoom: {
        scale: 1.0,
        naturalWidth: 0,
        naturalHeight: 0,
        showFields: true,
        showOcr: true
    },

    setupAnalysisModal() {
        const modal = document.getElementById('analysis-modal');
        const btnClose = document.getElementById('modal-btn-close');
        const btnAnalyze = document.getElementById('modal-btn-analyze');

        if (btnClose) {
            btnClose.addEventListener('click', () => this.closeAnalysisModal());
        }

        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeAnalysisModal();
            });
        }

        if (btnAnalyze) {
            btnAnalyze.addEventListener('click', () => this.runDocumentAnalysis());
        }

        const btnExportCsv = document.getElementById('modal-btn-export-csv');
        if (btnExportCsv) {
            btnExportCsv.addEventListener('click', () => {
                if (this.currentAnalysisDocId) {
                    this.downloadFile(ApiClient.getDocumentExportCsvUrl(this.currentAnalysisDocId), `document_${this.currentAnalysisDocId}_export.csv`);
                    this.showToast('Экспорт в CSV успешно начат', 'success');
                }
            });
        }

        const btnExportJson = document.getElementById('modal-btn-export-json');
        if (btnExportJson) {
            btnExportJson.addEventListener('click', () => {
                if (this.currentAnalysisDocId) {
                    this.downloadFile(ApiClient.getDocumentExportJsonUrl(this.currentAnalysisDocId), `document_${this.currentAnalysisDocId}_export.json`);
                    this.showToast('JSON-файл успешно сохранён', 'success');
                }
            });
        }

        // Переключение 4 вкладок в инспекторе (Поля, OCR, Валидация, Спросить у ИИ)
        const tabBtns = document.querySelectorAll('.inspector-tabs .tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const tab = btn.dataset.tab;
                const fieldsContent = document.getElementById('tab-fields-content');
                const ocrContent = document.getElementById('tab-ocr-content');
                const valContent = document.getElementById('tab-validation-content');
                const qaContent = document.getElementById('tab-qa-content');
                
                if (fieldsContent) fieldsContent.style.display = tab === 'fields' ? 'flex' : 'none';
                if (ocrContent) ocrContent.style.display = tab === 'ocr' ? 'flex' : 'none';
                if (valContent) valContent.style.display = tab === 'validation' ? 'flex' : 'none';
                if (qaContent) {
                    qaContent.style.display = tab === 'qa' ? 'flex' : 'none';
                    if (tab === 'qa') {
                        const input = document.getElementById('qa-input');
                        if (input) setTimeout(() => input.focus(), 100);
                    }
                }
            });
        });

        // Кнопки переключения страниц многостраничных документов / PDF
        const btnPrev = document.getElementById('btn-prev-page');
        const btnNext = document.getElementById('btn-next-page');
        if (btnPrev) {
            btnPrev.onclick = () => {
                if (this.currentPage > 1) {
                    this.switchPage(this.currentPage - 1);
                }
            };
        }
        if (btnNext) {
            btnNext.onclick = () => {
                if (this.currentPage < this.totalPages) {
                    this.switchPage(this.currentPage + 1);
                }
            };
        }

        // Кнопка копирования всего текста OCR
        const btnCopyOcr = document.getElementById('btn-copy-all-ocr');
        if (btnCopyOcr) {
            btnCopyOcr.onclick = () => {
                if (!this.currentAnalysisData || !this.currentAnalysisData.ocrBlocks || this.currentAnalysisData.ocrBlocks.length === 0) {
                    this.showToast('Нет распознанного текста для копирования', 'warning');
                    return;
                }
                const fullText = this.currentAnalysisData.ocrBlocks.map(b => b.text).join('\n');
                navigator.clipboard.writeText(fullText).then(() => {
                    this.showToast('Весь OCR-текст скопирован в буфер обмена', 'success');
                }).catch(err => {
                    console.error('Ошибка копирования OCR текста:', err);
                    prompt('Скопируйте OCR-текст вручную:', fullText);
                });
            };
        }

        // Поиск в реальном времени по блокам OCR текста
        const ocrSearch = document.getElementById('ocr-pane-search');
        if (ocrSearch) {
            ocrSearch.oninput = () => {
                const query = ocrSearch.value.trim().toLowerCase();
                const cards = document.querySelectorAll('#ocr-blocks-list .ocr-block-card');
                cards.forEach(card => {
                    const textEl = card.querySelector('.ocr-block-text');
                    const txt = (textEl ? textEl.textContent : '').toLowerCase();
                    if (!query || txt.includes(query)) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
            };
        }

        // Подключение слушателей для вопросно-ответной системы (Document Q&A)
        this.setupQaListeners();

        // Настройка элементов управления просмотрщика (масштаб, drag-and-pan, слои)
        this.setupViewerControls();
    },

    setupViewerControls() {
        const btnZoomIn = document.getElementById('btn-zoom-in');
        const btnZoomOut = document.getElementById('btn-zoom-out');
        const btnZoomReset = document.getElementById('btn-zoom-reset');
        const btnZoomFit = document.getElementById('btn-zoom-fit');
        const toggleFields = document.getElementById('toggle-fields-layer');
        const toggleOcr = document.getElementById('toggle-ocr-layer');
        const container = document.getElementById('viewer-container');

        if (btnZoomIn) {
            btnZoomIn.onclick = () => this.changeZoom(0.15);
        }
        if (btnZoomOut) {
            btnZoomOut.onclick = () => this.changeZoom(-0.15);
        }
        if (btnZoomReset) {
            btnZoomReset.onclick = () => {
                this.setZoom(1.0);
                if (container) {
                    container.scrollLeft = 0;
                    container.scrollTop = 0;
                }
            };
        }
        if (btnZoomFit) {
            btnZoomFit.onclick = () => this.fitViewer();
        }

        if (toggleFields) {
            toggleFields.onclick = () => {
                this.viewerZoom.showFields = !this.viewerZoom.showFields;
                toggleFields.classList.toggle('active', this.viewerZoom.showFields);
                const wrapper = document.getElementById('scan-wrapper');
                if (wrapper) wrapper.classList.toggle('hide-fields', !this.viewerZoom.showFields);
            };
        }

        if (toggleOcr) {
            toggleOcr.onclick = () => {
                this.viewerZoom.showOcr = !this.viewerZoom.showOcr;
                toggleOcr.classList.toggle('active', this.viewerZoom.showOcr);
                const wrapper = document.getElementById('scan-wrapper');
                if (wrapper) wrapper.classList.toggle('hide-ocr', !this.viewerZoom.showOcr);
            };
        }

        // Ctrl + Mouse Wheel zoom
        if (container) {
            container.onwheel = (e) => {
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    const delta = e.deltaY < 0 ? 0.15 : -0.15;
                    this.changeZoom(delta);
                }
            };

            // Drag-to-Pan (перетаскивание мышью без ограничений)
            let isPanning = false;
            let startX = 0;
            let startY = 0;
            let scrollStartLeft = 0;
            let scrollStartTop = 0;

            container.addEventListener('mousedown', (e) => {
                // Если кликнули по кнопкам или тегу поля — не запускаем drag
                if (e.target.closest('.btn-tool') || e.target.closest('.field-box-tag') || e.target.closest('.ocr-box') || e.target.closest('.field-box')) return;

                isPanning = true;
                startX = e.clientX;
                startY = e.clientY;
                scrollStartLeft = container.scrollLeft;
                scrollStartTop = container.scrollTop;
                container.classList.add('is-dragging');
            });

            window.addEventListener('mousemove', (e) => {
                if (!isPanning) return;
                e.preventDefault();
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                container.scrollLeft = scrollStartLeft - dx;
                container.scrollTop = scrollStartTop - dy;
            });

            const stopPanning = () => {
                if (isPanning) {
                    isPanning = false;
                    container.classList.remove('is-dragging');
                }
            };

            window.addEventListener('mouseup', stopPanning);
            container.addEventListener('mouseleave', stopPanning);
            container.classList.add('can-drag');
        }
    },

    changeZoom(delta) {
        let newScale = Math.round((this.viewerZoom.scale + delta) * 100) / 100;
        newScale = Math.min(Math.max(newScale, 0.1), 5.0); // Свободный зум от 10% до 500%
        this.setZoom(newScale);
    },

    setZoom(scale) {
        const container = document.getElementById('viewer-container');
        const prevScale = this.viewerZoom.scale || 1.0;
        this.viewerZoom.scale = scale;

        const badge = document.getElementById('zoom-level-badge');
        if (badge) {
            badge.textContent = `${Math.round(scale * 100)}%`;
        }

        const wrapper = document.getElementById('scan-wrapper');
        const img = document.getElementById('scan-img');
        if (!wrapper) return;

        // Определяем эталонную естественную ширину изображения
        let natW = this.viewerZoom.naturalWidth;
        let natH = this.viewerZoom.naturalHeight;
        if ((!natW || natW <= 0) && img && img.naturalWidth > 0) {
            natW = img.naturalWidth;
            natH = img.naturalHeight;
            this.viewerZoom.naturalWidth = natW;
            this.viewerZoom.naturalHeight = natH;
        }

        if ((!natW || natW <= 0) && this.currentAnalysisData && this.currentAnalysisData.quality) {
            natW = this.currentAnalysisData.quality.width || 0;
            natH = this.currentAnalysisData.quality.height || 0;
            if (natW > 0) {
                this.viewerZoom.naturalWidth = natW;
                this.viewerZoom.naturalHeight = natH;
            }
        }

        if (natW > 0) {
            const targetWidth = Math.round(natW * scale);
            wrapper.style.width = `${targetWidth}px`;
            wrapper.style.minWidth = `${targetWidth}px`;
            wrapper.style.maxWidth = `${targetWidth}px`;

            // Плавное центрирование точки обзора при зуме
            if (container && prevScale > 0 && prevScale !== scale && container.clientWidth > 0) {
                const ratio = scale / prevScale;
                const centerX = container.scrollLeft + container.clientWidth / 2;
                const centerY = container.scrollTop + container.clientHeight / 2;
                container.scrollLeft = Math.max(0, Math.round(centerX * ratio - container.clientWidth / 2));
                container.scrollTop = Math.max(0, Math.round(centerY * ratio - container.clientHeight / 2));
            }
        }
    },

    fitViewer() {
        const container = document.getElementById('viewer-container');
        if (!container) return;

        const img = document.getElementById('scan-img');
        let natW = this.viewerZoom.naturalWidth;
        if ((!natW || natW <= 0) && img && img.naturalWidth > 0) {
            natW = img.naturalWidth;
            this.viewerZoom.naturalWidth = natW;
            this.viewerZoom.naturalHeight = img.naturalHeight;
        }
        if ((!natW || natW <= 0) && this.currentAnalysisData && this.currentAnalysisData.quality) {
            natW = this.currentAnalysisData.quality.width || 0;
            if (natW > 0) {
                this.viewerZoom.naturalWidth = natW;
                this.viewerZoom.naturalHeight = this.currentAnalysisData.quality.height || 0;
            }
        }

        if (!natW || natW <= 0) return;

        // Вычитаем padding контейнера (24px с каждой стороны = 48px)
        const availWidth = container.clientWidth - 48;
        if (availWidth <= 0) return;

        const scale = availWidth / natW;
        const targetScale = Math.max(0.1, Math.min(5.0, Math.round(scale * 100) / 100));
        this.setZoom(targetScale);
        container.scrollLeft = 0;
        container.scrollTop = 0;
    },

    /**
     * Переключение страницы документа
     */
    async switchPage(page) {
        if (!this.currentAnalysisDocId) return;
        this.currentPage = page;

        const pageBadge = document.getElementById('page-nav-badge');
        if (pageBadge) pageBadge.textContent = `${this.currentPage} / ${this.totalPages}`;

        const img = document.getElementById('scan-img');
        if (img) {
            const previewUrl = ApiClient.getDocumentPreviewUrl(this.currentAnalysisDocId, this.currentPage);
            img.src = previewUrl;

            const onPageImgReady = () => {
                this.viewerZoom.naturalWidth = img.naturalWidth;
                this.viewerZoom.naturalHeight = img.naturalHeight;
                const infoEl = document.getElementById('modal-viewer-info');
                if (infoEl) infoEl.textContent = `${img.naturalWidth} × ${img.naturalHeight} px (Стр. ${this.currentPage})`;
                if (this.currentAnalysisData) {
                    this.renderPageBboxes(this.currentAnalysisData);
                }
                this.setZoom(this.viewerZoom.scale);
            };

            if (img.complete && img.naturalWidth > 0) {
                onPageImgReady();
            } else {
                img.onload = onPageImgReady;
            }
        }
    },

    async openAnalysisModal(docId) {
        this.currentAnalysisDocId = docId;
        this.currentPage = 1;
        this.totalPages = 1;
        this.currentAnalysisData = null;
        this.viewerZoom.naturalWidth = 0;
        this.viewerZoom.naturalHeight = 0;
        this.viewerZoom.scale = 1.0;

        const modal = document.getElementById('analysis-modal');
        const titleEl = document.getElementById('modal-doc-title');
        const statusEl = document.getElementById('modal-doc-status');
        const img = document.getElementById('scan-img');
        const overlay = document.getElementById('bbox-overlay-layer');
        const metricsBar = document.getElementById('modal-metrics-bar');
        const classBadge = document.getElementById('modal-classification-badge');
        const valBadge = document.getElementById('modal-validation-badge');
        const ocrList = document.getElementById('ocr-blocks-list');
        const ocrCount = document.getElementById('ocr-count-badge');
        const fieldsList = document.getElementById('fields-list');
        const fieldsCount = document.getElementById('fields-count-badge');
        const valList = document.getElementById('validation-list');
        const valCount = document.getElementById('validation-count-badge');
        const btnAnalyze = document.getElementById('modal-btn-analyze');
        const pageNav = document.getElementById('page-nav-controls');
        const pageBadge = document.getElementById('page-nav-badge');

        if (!modal) return;

        // Сброс вкладок на "Поля"
        const tabFieldsBtn = document.getElementById('tab-fields-btn');
        const tabOcrBtn = document.getElementById('tab-ocr-btn');
        const tabValBtn = document.getElementById('tab-validation-btn');
        const tabQaBtn = document.getElementById('tab-qa-btn');
        if (tabFieldsBtn) tabFieldsBtn.classList.add('active');
        if (tabOcrBtn) tabOcrBtn.classList.remove('active');
        if (tabValBtn) tabValBtn.classList.remove('active');
        if (tabQaBtn) tabQaBtn.classList.remove('active');

        const fieldsContent = document.getElementById('tab-fields-content');
        const ocrContent = document.getElementById('tab-ocr-content');
        const valContent = document.getElementById('tab-validation-content');
        const qaContent = document.getElementById('tab-qa-content');
        if (fieldsContent) fieldsContent.style.display = 'flex';
        if (ocrContent) ocrContent.style.display = 'none';
        if (valContent) valContent.style.display = 'none';
        if (qaContent) qaContent.style.display = 'none';

        // Сброс вопросно-ответной системы
        this.resetQaTab();

        // Показываем окно
        modal.style.display = 'flex';
        overlay.innerHTML = '';
        if (classBadge) classBadge.innerHTML = '';
        if (valBadge) valBadge.style.display = 'none';
        if (pageNav) pageNav.style.display = 'none';
        metricsBar.innerHTML = `<span class="text-muted">Загрузка информации о документе...</span>`;
        if (fieldsList) fieldsList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Загрузка полей...</p>`;
        if (fieldsCount) fieldsCount.textContent = '0';
        if (ocrList) ocrList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Загрузка данных...</p>`;
        if (ocrCount) ocrCount.textContent = '0';
        if (valList) valList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Загрузка правил валидации...</p>`;
        if (valCount) valCount.textContent = '0';

        if (btnAnalyze) {
            btnAnalyze.disabled = false;
            btnAnalyze.innerHTML = `<svg><use href="#icon-zap"></use></svg> <span>AI-анализ</span>`;
        }

        try {
            // Запрашиваем детали документа
            const doc = await ApiClient.getDocument(docId);
            titleEl.textContent = `${doc.originalFilename} (#${doc.id})`;
            const statusClass = doc.status === 'COMPLETED' ? 'success' : (doc.status === 'FAILED' ? 'danger' : 'info');
            statusEl.className = `status-pill ${statusClass}`;
            statusEl.innerHTML = `<span class="dot"></span><span>${doc.status}</span>`;

            // Обновляем бейдж формата в шапке инспектора
            const formatBadge = document.getElementById('modal-format-badge');
            if (formatBadge) {
                const ext = (doc.originalFilename || '').split('.').pop().toLowerCase();
                let formatClass = 'txt';
                if (ext === 'pdf') formatClass = 'pdf';
                else if (['docx', 'doc'].includes(ext)) formatClass = 'docx';
                else if (['xlsx', 'xls', 'csv'].includes(ext)) formatClass = 'xlsx';
                else if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) formatClass = 'img';
                formatBadge.className = `format-badge ${formatClass}`;
                formatBadge.textContent = ext.toUpperCase() || 'DOC';
            }

            if (doc.totalPages && doc.totalPages > 1) {
                this.totalPages = doc.totalPages;
                if (pageNav) pageNav.style.display = 'inline-flex';
                if (pageBadge) pageBadge.textContent = `${this.currentPage} / ${this.totalPages}`;
            }

            // Загружаем растровое превью страницы через /preview (поддерживает и PDF, и картинки!)
            const previewUrl = ApiClient.getDocumentPreviewUrl(docId, 1);
            img.onerror = () => {
                // Fallback на прямой файл, если серверное превью недоступно
                img.src = ApiClient.getDocumentFileUrl(docId);
            };
            img.src = previewUrl;

            const onImgReady = () => {
                this.viewerZoom.naturalWidth = img.naturalWidth;
                this.viewerZoom.naturalHeight = img.naturalHeight;
                const infoEl = document.getElementById('modal-viewer-info');
                if (infoEl) infoEl.textContent = `${img.naturalWidth} × ${img.naturalHeight} px`;
                requestAnimationFrame(() => this.fitViewer());
            };

            if (img.complete && img.naturalWidth > 0) {
                onImgReady();
            } else {
                img.onload = onImgReady;
            }

            // Проверяем, есть ли уже сохранённый результат анализа
            const existingAnalysis = await ApiClient.getDocumentAnalysis(docId);
            if (existingAnalysis && existingAnalysis.status === 'success') {
                this.renderAnalysisResult(existingAnalysis);
            } else {
                metricsBar.innerHTML = `
                    <span class="text-muted">Документ ещё не проанализирован нейросетью. Нажмите кнопку справа для запуска OCR, классификации и валидации.</span>
                `;
                if (fieldsList) {
                    fieldsList.innerHTML = `
                        <p class="text-muted text-center" style="margin-top: 40px;">
                            Нажмите "AI-анализ", чтобы извлечь реквизиты
                        </p>
                    `;
                }
                ocrList.innerHTML = `
                    <p class="text-muted text-center" style="margin-top: 40px;">
                        Нажмите "AI-анализ", чтобы распознать текст на документе
                    </p>
                `;
                if (valList) {
                    valList.innerHTML = `
                        <p class="text-muted text-center" style="margin-top: 40px;">
                            Правила валидации (ИНН, даты, суммы, VIN) будут проверены при анализе
                        </p>
                    `;
                }
            }

        } catch (error) {
            console.error('Ошибка открытия инспектора:', error);
            metricsBar.innerHTML = `<span style="color: var(--danger-text);">Ошибка: ${error.message}</span>`;
        }
    },

    closeAnalysisModal() {
        const modal = document.getElementById('analysis-modal');
        if (modal) modal.style.display = 'none';
        this.currentAnalysisDocId = null;
    },

    async runDocumentAnalysis() {
        if (!this.currentAnalysisDocId) return;

        const btnAnalyze = document.getElementById('modal-btn-analyze');
        const metricsBar = document.getElementById('modal-metrics-bar');
        const ocrList = document.getElementById('ocr-blocks-list');

        if (btnAnalyze) {
            btnAnalyze.disabled = true;
            btnAnalyze.innerHTML = `<span class="status-led checking"></span> <span>Идёт распознавание...</span>`;
        }

        metricsBar.innerHTML = `<span class="text-muted">Запущен конвейер: PyMuPDF -> OpenCV Deskew/CLAHE -> PaddleOCR...</span>`;
        ocrList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Нейросеть распознаёт символы и строит bounding boxes...</p>`;

        try {
            const result = await ApiClient.analyzeDocument(this.currentAnalysisDocId);
            console.log('Результат анализа получен:', result);

            this.renderAnalysisResult(result);
            this.loadDocuments();
            this.loadDashboardData();

            const statusEl = document.getElementById('modal-doc-status');
            if (statusEl) {
                statusEl.className = 'status-pill success';
                statusEl.innerHTML = '<span class="dot"></span><span>COMPLETED</span>';
            }

        } catch (error) {
            console.error('Ошибка запуска анализа:', error);
            metricsBar.innerHTML = `<span style="color: var(--danger-text);">Ошибка анализа: ${error.message}</span>`;
            ocrList.innerHTML = `<p class="text-center" style="color: var(--danger-text); margin-top: 40px;">${error.message}</p>`;
        } finally {
            if (btnAnalyze) {
                btnAnalyze.disabled = false;
                btnAnalyze.innerHTML = `<svg><use href="#icon-zap"></use></svg> <span>Перезапустить анализ</span>`;
            }
        }
    },

    renderAnalysisResult(analysis) {
        this.currentAnalysisData = analysis;

        const metricsBar = document.getElementById('modal-metrics-bar');
        const classBadge = document.getElementById('modal-classification-badge');
        const valBadge = document.getElementById('modal-validation-badge');
        const ocrList = document.getElementById('ocr-blocks-list');
        const ocrCount = document.getElementById('ocr-count-badge');
        const fieldsList = document.getElementById('fields-list');
        const fieldsCount = document.getElementById('fields-count-badge');
        const valList = document.getElementById('validation-list');
        const valCount = document.getElementById('validation-count-badge');
        const pageNav = document.getElementById('page-nav-controls');
        const pageBadge = document.getElementById('page-nav-badge');
        const img = document.getElementById('scan-img');

        // Многостраничность
        if (analysis.totalPages && analysis.totalPages > 1) {
            this.totalPages = analysis.totalPages;
            if (pageNav) pageNav.style.display = 'inline-flex';
            if (pageBadge) pageBadge.textContent = `${this.currentPage} / ${this.totalPages}`;
        }

        // 1. Отображение классифицированного типа документа (Этап 6)
        if (classBadge) {
            const detectedType = analysis.detectedType || 'UNKNOWN';
            const displayName = this.getDisplayDocType(analysis);
            const typeConf = analysis.typeConfidence ? Math.round(analysis.typeConfidence * 100) : 0;
            const explanation = analysis.explanation || '';

            classBadge.innerHTML = `
                <span class="category-badge" title="${this.escapeHtml(explanation)}">
                    ${this.escapeHtml(displayName)} (${typeConf}%)
                </span>
            `;
        }

        // 2. Отображение валидации (Этап 9: Проверка правил)
        const valData = analysis.validation;
        if (valData && valData.rules && valData.rules.length > 0) {
            const rawOverall = (valData.overallStatus || valData.overall_status || 'PASSED').toUpperCase();
            const isOverallValid = rawOverall === 'PASSED' || rawOverall === 'VALID' || rawOverall === 'OK';
            const overall = isOverallValid ? 'PASSED' : (rawOverall.includes('WARN') ? 'WARNING' : 'FAILED');
            const total = valData.totalRules || valData.total_rules || valData.rules.length;
            const passed = valData.passedRules || valData.passed_rules || 0;
            const warnings = valData.warningRules || valData.warning_rules || 0;
            const failed = valData.failedRules || valData.failed_rules || 0;

            if (valCount) valCount.textContent = `${total}`;

            if (valBadge) {
                valBadge.style.display = 'inline-flex';
                let cls = 'passed';
                let text = `Проверка: ${passed}/${total} ОК`;
                if (failed > 0) {
                    cls = 'failed';
                    text = `Ошибок: ${failed}`;
                } else if (warnings > 0) {
                    cls = 'warning';
                    text = `Предупреждений: ${warnings}`;
                }
                valBadge.className = `val-badge ${cls}`;
                valBadge.textContent = text;
                valBadge.onclick = () => {
                    const tabValBtn = document.getElementById('tab-validation-btn');
                    if (tabValBtn) tabValBtn.click();
                };
            }

            if (valList) {
                const summaryHtml = `
                    <div class="validation-summary-card">
                        <div>
                            <strong>Итог валидации:</strong>
                            <span class="val-status-pill val-status-${overall.toLowerCase()}">
                                ${overall === 'PASSED' ? 'ВСЕ ПРАВИЛА ПРОЙДЕНЫ' : (overall === 'WARNING' ? 'ЕСТЬ ПРЕДУПРЕЖДЕНИЯ' : 'НАЙДЕНЫ ОШИБКИ')}
                            </span>
                        </div>
                        <div style="font-size: 0.85em; display: flex; gap: 12px;">
                            <span style="color: var(--success); font-weight: 600;">✓ ${passed}</span>
                            <span style="color: var(--warning); font-weight: 600;">! ${warnings}</span>
                            <span style="color: var(--error); font-weight: 600;">✗ ${failed}</span>
                        </div>
                    </div>
                `;

                const rulesHtml = valData.rules.map(rule => {
                    const rawStatus = (rule.status || 'PASS').toUpperCase();
                    const rStatus = (rawStatus === 'PASS' || rawStatus === 'PASSED' || rawStatus === 'OK' || rawStatus === 'VALID') ? 'passed' : (rawStatus.includes('WARN') ? 'warning' : 'failed');
                    const rName = rule.ruleName || rule.rule_name || rule.ruleId || rule.rule_id;
                    const rId = rule.ruleId || rule.rule_id || '';
                    const rCat = rule.category || (rId.includes('inn') ? 'ИНН' : (rId.includes('date') ? 'ДАТЫ' : (rId.includes('math') ? 'МАТЕМАТИКА' : (rId.includes('vin') || rId.includes('pts') ? 'ТРАНСПОРТ' : 'ПРАВИЛО'))));
                    const rMsg = rule.message || '';
                    const rDetails = rule.details;
                    const rSugg = rule.suggestion;

                    return `
                        <div class="validation-rule-card rule-${rStatus}">
                            <div class="val-rule-header">
                                <span class="val-rule-title">
                                    ${this.escapeHtml(rName)}
                                </span>
                                <div style="display: flex; gap: 6px; align-items: center;">
                                    <span class="val-rule-cat">${this.escapeHtml(rCat)}</span>
                                    <span class="val-status-pill val-status-${rStatus}">${rStatus.toUpperCase()}</span>
                                </div>
                            </div>
                            <div class="val-rule-msg">${this.escapeHtml(rMsg)}</div>
                            ${rDetails ? `<div class="text-muted" style="font-size: 0.78em; font-family: monospace;">${this.escapeHtml(typeof rDetails === 'object' ? JSON.stringify(rDetails) : rDetails)}</div>` : ''}
                            ${rSugg ? `<div class="val-rule-suggestion">Рекомендация: ${this.escapeHtml(rSugg)}</div>` : ''}
                        </div>
                    `;
                }).join('');

                valList.innerHTML = summaryHtml + rulesHtml;
            }
        } else {
            if (valBadge) valBadge.style.display = 'none';
            if (valCount) valCount.textContent = '0';
            if (valList) {
                valList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Правила валидации для данного типа документа выполнены по умолчанию.</p>`;
            }
        }

        // 3. Отображение метрик качества и скорости
        const q = analysis.quality || {};
        const isBlurry = q.is_blurry;
        const blurScore = q.blur_score !== undefined ? q.blur_score : '—';
        const skewAngle = q.skew_angle !== undefined ? q.skew_angle : 0.0;
        const timeMs = analysis.processingTimeMs ? Math.round(analysis.processingTimeMs) : 0;
        const confPct = analysis.overallConfidence ? Math.round(analysis.overallConfidence * 100) : 0;

        metricsBar.innerHTML = `
            <span class="status-pill ${isBlurry ? 'warning' : 'success'}">
                <span class="dot"></span>
                <span>${isBlurry ? 'Размыто' : 'Чётко'} (${blurScore})</span>
            </span>
            <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">
                Наклон: ${skewAngle}° • ${timeMs} мс • Точность: ${confPct}% • Стр. ${analysis.totalPages || 1}
            </span>
        `;

        if (!this.viewerZoom.naturalWidth && q.width > 0) {
            this.viewerZoom.naturalWidth = q.width;
            this.viewerZoom.naturalHeight = q.height;
            this.fitViewer();
        }

        // 4. Отображение структурированных полей (Этап 7: Information Extraction)
        const fields = analysis.fields || [];
        if (fieldsCount) fieldsCount.textContent = `${fields.length}`;

        if (fieldsList) {
            if (fields.length === 0) {
                fieldsList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Структурированные поля для данного типа документа не обнаружены.</p>`;
            } else {
                fieldsList.innerHTML = fields.map((f, fIdx) => {
                    const conf = Math.round((f.confidence || 0) * 100);
                    const confClass = conf >= 90 ? 'conf-high' : (conf >= 70 ? 'conf-mid' : 'conf-low');
                    
                    const val = f.fieldValue !== undefined ? f.fieldValue : (f.value !== undefined ? f.value : '');
                    const label = f.displayName || f.fieldName || f.name || 'Поле';
                    const typeTitle = f.fieldTypeTitle || (typeof f.fieldType === 'object' ? f.fieldType.title : f.fieldType) || 'TEXT';

                    let parsedBbox = f.bbox;
                    if (typeof parsedBbox === 'string') {
                        try {
                            parsedBbox = JSON.parse(parsedBbox);
                        } catch (e) {
                            parsedBbox = null;
                        }
                    }
                    const hasBbox = parsedBbox && Array.isArray(parsedBbox) && parsedBbox.length === 4;
                    const bboxCoords = hasBbox ? `[${parsedBbox.join(', ')}]` : '';

                    // Специальный рендеринг для табличных структур (Этап 8: Таблицы)
                    if (f.fieldType === 'TABLE' || typeTitle === 'Таблица') {
                        let tableData = null;
                        try {
                            tableData = typeof val === 'object' ? val : JSON.parse(val);
                        } catch (e) {
                            tableData = null;
                        }

                        if (tableData && tableData.headers && tableData.rows) {
                            const headersHtml = tableData.headers.map(h => `<th>${this.escapeHtml(h)}</th>`).join('');
                            const rowsHtml = tableData.rows.map(row => {
                                const cellsHtml = row.map(cell => {
                                    const isNum = /^[\d\s]+(?:[\.,]\d{2})?(?:\s*(?:руб|р\.|\u20bd|шт|%))?$/.test(cell.trim());
                                    return `<td class="${isNum ? 'num-cell' : ''}">${this.escapeHtml(cell || '—')}</td>`;
                                }).join('');
                                return `<tr>${cellsHtml}</tr>`;
                            }).join('');

                            const summary = tableData.summary || {};
                            const totalStr = summary.formatted_total ? `Итого: <strong>${this.escapeHtml(summary.formatted_total)}</strong>` : '';

                            return `
                                <div class="field-table-card" data-field-index="${fIdx}">
                                    <div class="field-table-header">
                                        <div class="field-table-title">
                                            <span>${this.escapeHtml(label)}</span>
                                            <span class="field-type-pill">ТАБЛИЦА</span>
                                        </div>
                                        <div style="display: flex; gap: 6px; align-items: center;">
                                            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); App.copyTableAsCsv(${fIdx});">
                                                <svg><use href="#icon-copy"></use></svg>
                                                <span>CSV</span>
                                            </button>
                                            ${hasBbox ? `
                                                <button class="field-locate-btn" title="Показать на скане" onclick="event.stopPropagation(); App.locateFieldOnScan(${fIdx});">
                                                    <svg><use href="#icon-crosshair"></use></svg>
                                                </button>
                                            ` : ''}
                                            <span class="conf-pill ${confClass}">${conf}%</span>
                                        </div>
                                    </div>
                                    <div class="table-scroll-container">
                                        <table class="doc-data-table">
                                            <thead><tr>${headersHtml}</tr></thead>
                                            <tbody>${rowsHtml}</tbody>
                                        </table>
                                    </div>
                                    <div class="table-summary-bar">
                                        <span>Строк: ${tableData.rows.length} ${hasBbox ? `• ${bboxCoords}` : ''}</span>
                                        <span>${totalStr}</span>
                                    </div>
                                </div>
                            `;
                        }
                    }

                    // Индикатор валидации поля
                    let valIndicator = '';
                    if (valData && valData.rules) {
                        const fieldKey = (f.fieldName || f.name || '').toLowerCase();
                        if (fieldKey.includes('inn') || fieldKey.includes('инн')) {
                            const innRule = valData.rules.find(r => (r.ruleId || '').includes('inn'));
                            if (innRule) {
                                valIndicator = innRule.status === 'PASSED' ? '<span class="status-pill success" style="padding: 1px 5px; font-size: 10px;">ИНН ✓</span>' : '<span class="status-pill danger" style="padding: 1px 5px; font-size: 10px;">ИНН ✗</span>';
                            }
                        } else if (fieldKey.includes('vin') || fieldKey.includes('вин')) {
                            const vinRule = valData.rules.find(r => (r.ruleId || '').includes('vin'));
                            if (vinRule) {
                                valIndicator = vinRule.status === 'PASSED' ? '<span class="status-pill success" style="padding: 1px 5px; font-size: 10px;">VIN ✓</span>' : '<span class="status-pill warning" style="padding: 1px 5px; font-size: 10px;">VIN !</span>';
                            }
                        }
                    }

                    return `
                        <div class="field-item-card" data-field-index="${fIdx}">
                            <div class="field-top-row">
                                <span class="field-key-name">${this.escapeHtml(label)}</span>
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <span class="field-type-pill">${this.escapeHtml(typeTitle)}</span>
                                    <span class="conf-pill ${confClass}">${conf}%</span>
                                </div>
                            </div>
                            <div class="field-input-row">
                                <input type="text" class="field-val-input" value="${this.escapeHtml(val)}" readonly />
                                ${hasBbox ? `
                                    <button class="field-locate-btn" title="Показать на скане" onclick="event.stopPropagation(); App.locateFieldOnScan(${fIdx});">
                                        <svg><use href="#icon-crosshair"></use></svg>
                                    </button>
                                ` : ''}
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 10.5px; color: var(--text-muted);">
                                <span>${hasBbox ? bboxCoords : ''} ${valIndicator}</span>
                                <span>Стр. ${f.pageNumber || 1}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }

        // 5. Отображение блоков сырого OCR текста
        const blocks = analysis.ocrBlocks || [];
        if (ocrCount) ocrCount.textContent = `${blocks.length}`;

        if (blocks.length === 0) {
            ocrList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">Текст на документе не обнаружен.</p>`;
        } else {
            ocrList.innerHTML = blocks.map((block, idx) => {
                const conf = Math.round(block.confidence * 100);
                const confClass = conf >= 90 ? 'conf-high' : (conf >= 70 ? 'conf-mid' : 'conf-low');
                const bboxStr = Array.isArray(block.bbox) ? block.bbox.join(', ') : block.bbox;
                return `
                    <div class="ocr-block-card" data-index="${idx}">
                        <div class="ocr-block-header">
                            <span>#${idx + 1} • Стр. ${block.page || 1}</span>
                            <span class="conf-pill ${confClass}">${conf}%</span>
                        </div>
                        <div class="ocr-block-text">${this.escapeHtml(block.text)}</div>
                        <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">
                            [${bboxStr}]
                        </div>
                    </div>
                `;
            }).join('');
        }

        // 6. Отрисовка Bounding Boxes для активной страницы
        this.renderPageBboxes(analysis);

        // 7. Навешиваем слушатели синхронной подсветки
        ocrList.querySelectorAll('.ocr-block-card').forEach(card => {
            const idx = card.dataset.index;
            card.addEventListener('mouseenter', () => this.highlightBlock(idx));
            card.addEventListener('mouseleave', () => this.unhighlightBlock(idx));
        });

        if (fieldsList) {
            fieldsList.querySelectorAll('.field-card, .field-table-card, .field-item-card').forEach(card => {
                const fIdx = card.dataset.fieldIndex;
                card.addEventListener('mouseenter', () => this.highlightField(fIdx));
                card.addEventListener('mouseleave', () => this.unhighlightField(fIdx));
            });
        }
    },

    /**
     * Отрисовка Bounding Boxes для конкретной текущей страницы
     */
    renderPageBboxes(analysis) {
        const overlay = document.getElementById('bbox-overlay-layer');
        const img = document.getElementById('scan-img');
        if (!overlay) return;
        overlay.innerHTML = '';

        const q = analysis.quality || {};
        const docWidth = (q.width && q.width > 0) ? q.width : (this.viewerZoom.naturalWidth || img.naturalWidth || 915);
        const docHeight = (q.height && q.height > 0) ? q.height : (this.viewerZoom.naturalHeight || img.naturalHeight || 1280);
        const curPage = this.currentPage || 1;

        // OCR блоки текущей страницы
        const blocks = analysis.ocrBlocks || [];
        blocks.forEach((block, idx) => {
            const blockPage = block.page || 1;
            if (blockPage !== curPage) return;

            const [x1, y1, x2, y2] = block.bbox;
            const leftPct = (x1 / docWidth) * 100;
            const topPct = (y1 / docHeight) * 100;
            const widthPct = ((x2 - x1) / docWidth) * 100;
            const heightPct = ((y2 - y1) / docHeight) * 100;

            const box = document.createElement('div');
            box.className = 'ocr-box';
            box.dataset.index = idx;
            box.title = `"${block.text}" (${Math.round(block.confidence * 100)}%)`;
            box.style.left = `${leftPct}%`;
            box.style.top = `${topPct}%`;
            box.style.width = `${Math.max(0.5, widthPct)}%`;
            box.style.height = `${Math.max(0.5, heightPct)}%`;

            box.addEventListener('mouseenter', () => this.highlightBlock(idx));
            box.addEventListener('mouseleave', () => this.unhighlightBlock(idx));

            overlay.appendChild(box);
        });

        // Поля текущей страницы
        const fields = analysis.fields || [];
        fields.forEach((f, fIdx) => {
            const fieldPage = f.pageNumber || 1;
            if (fieldPage !== curPage) return;

            let parsedBbox = f.bbox;
            if (typeof parsedBbox === 'string') {
                try {
                    parsedBbox = JSON.parse(parsedBbox);
                } catch (e) {
                    parsedBbox = null;
                }
            }

            if (parsedBbox && Array.isArray(parsedBbox) && parsedBbox.length === 4) {
                const [x1, y1, x2, y2] = parsedBbox;
                const leftPct = (x1 / docWidth) * 100;
                const topPct = (y1 / docHeight) * 100;
                const widthPct = ((x2 - x1) / docWidth) * 100;
                const heightPct = ((y2 - y1) / docHeight) * 100;

                const val = f.fieldValue !== undefined ? f.fieldValue : (f.value !== undefined ? f.value : '');
                const label = f.displayName || f.fieldName || f.name || 'Поле';

                const fBox = document.createElement('div');
                fBox.className = 'ocr-box field-box';
                fBox.dataset.fieldIndex = fIdx;
                fBox.title = `[Поле] ${label}: ${val}`;
                fBox.style.left = `${leftPct}%`;
                fBox.style.top = `${topPct}%`;
                fBox.style.width = `${Math.max(0.5, widthPct)}%`;
                fBox.style.height = `${Math.max(0.5, heightPct)}%`;

                const tag = document.createElement('span');
                tag.className = 'field-box-tag';
                tag.textContent = label;
                fBox.appendChild(tag);

                fBox.addEventListener('mouseenter', () => this.highlightField(fIdx));
                fBox.addEventListener('mouseleave', () => this.unhighlightField(fIdx));

                overlay.appendChild(fBox);
            }
        });
    },

    copyTableAsCsv(fieldIndex) {
        if (!this.currentAnalysisData || !this.currentAnalysisData.fields) return;
        const field = this.currentAnalysisData.fields[fieldIndex];
        if (!field) return;

        let tableData = null;
        const val = field.fieldValue !== undefined ? field.fieldValue : field.value;
        try {
            tableData = typeof val === 'object' ? val : JSON.parse(val);
        } catch (e) {
            return;
        }

        if (!tableData || !tableData.headers || !tableData.rows) return;

        const csvLines = [];
        csvLines.push(tableData.headers.map(h => `"${(h || '').replace(/"/g, '""')}"`).join(';'));
        for (const row of tableData.rows) {
            csvLines.push(row.map(c => `"${(c || '').replace(/"/g, '""')}"`).join(';'));
        }
        const csvText = csvLines.join('\n');

        navigator.clipboard.writeText(csvText).then(() => {
            this.showToast('Таблица скопирована в буфер обмена (CSV/Excel)', 'success');
        }).catch(err => {
            console.error('Ошибка копирования:', err);
            prompt('Скопируйте CSV вручную:', csvText);
        });
    },

    locateFieldOnScan(fieldIndex) {
        if (!this.currentAnalysisData || !this.currentAnalysisData.fields) return;
        const field = this.currentAnalysisData.fields[fieldIndex];
        if (!field) return;

        let parsedBbox = field.bbox;
        if (typeof parsedBbox === 'string') {
            try { parsedBbox = JSON.parse(parsedBbox); } catch (e) { parsedBbox = null; }
        }
        if (!parsedBbox || !Array.isArray(parsedBbox) || parsedBbox.length !== 4) {
            this.showToast('У данного поля нет координат на скане', 'info');
            return;
        }

        const targetPage = field.pageNumber || 1;
        if (targetPage !== this.currentPage && targetPage <= this.totalPages) {
            this.switchPage(targetPage);
        }

        const overlay = document.getElementById('bbox-overlay-layer');
        const img = document.getElementById('scan-img');
        const container = document.getElementById('viewer-container');
        if (!overlay || !img) return;

        // Удаляем предыдущие пульсирующие подсветки
        overlay.querySelectorAll('.bbox-pulse-highlight').forEach(el => el.remove());

        const q = (this.currentAnalysisData && this.currentAnalysisData.quality) || {};
        const docWidth = (q.width && q.width > 0) ? q.width : (this.viewerZoom.naturalWidth || img.naturalWidth || 1000);
        const docHeight = (q.height && q.height > 0) ? q.height : (this.viewerZoom.naturalHeight || img.naturalHeight || 1000);

        const [x1, y1, x2, y2] = parsedBbox;
        const leftPct = (x1 / docWidth) * 100;
        const topPct = (y1 / docHeight) * 100;
        const widthPct = ((x2 - x1) / docWidth) * 100;
        const heightPct = ((y2 - y1) / docHeight) * 100;

        const pulseBox = document.createElement('div');
        pulseBox.className = 'ocr-box field-box bbox-pulse-highlight';
        pulseBox.style.left = `${leftPct}%`;
        pulseBox.style.top = `${topPct}%`;
        pulseBox.style.width = `${Math.max(1.0, widthPct)}%`;
        pulseBox.style.height = `${Math.max(1.0, heightPct)}%`;

        const label = field.displayName || field.fieldName || field.name || 'Поле';
        const tag = document.createElement('span');
        tag.className = 'field-box-tag';
        tag.style.background = '#2563EB';
        tag.style.color = '#FFFFFF';
        tag.textContent = label;
        pulseBox.appendChild(tag);

        overlay.appendChild(pulseBox);

        // Плавный скролл просмотрщика на координату поля
        if (container) {
            const currentImgWidth = img.clientWidth || img.naturalWidth;
            const currentImgHeight = img.clientHeight || img.naturalHeight;
            const targetX = (x1 / docWidth) * currentImgWidth;
            const targetY = (y1 / docHeight) * currentImgHeight;

            container.scrollTo({
                left: Math.max(0, targetX - container.clientWidth / 2),
                top: Math.max(0, targetY - container.clientHeight / 2),
                behavior: 'smooth'
            });
        }

        this.showToast(`Поле «${label}» подсвечено на скане`, 'info');
    },

    highlightBlock(index) {
        const box = document.querySelector(`.ocr-box[data-index="${index}"]`);
        const card = document.querySelector(`.ocr-block-card[data-index="${index}"]`);

        if (box) box.classList.add('highlighted');
        if (card) {
            card.classList.add('highlighted');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    unhighlightBlock(index) {
        const box = document.querySelector(`.ocr-box[data-index="${index}"]`);
        const card = document.querySelector(`.ocr-block-card[data-index="${index}"]`);

        if (box) box.classList.remove('highlighted');
        if (card) card.classList.remove('highlighted');
    },

    highlightField(fieldIndex) {
        const box = document.querySelector(`.ocr-box.field-box[data-field-index="${fieldIndex}"]`);
        const card = document.querySelector(`.field-card[data-field-index="${fieldIndex}"], .field-table-card[data-field-index="${fieldIndex}"], .field-item-card[data-field-index="${fieldIndex}"]`);

        if (box) box.classList.add('highlighted');
        if (card) {
            card.classList.add('highlighted');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    unhighlightField(fieldIndex) {
        const box = document.querySelector(`.ocr-box.field-box[data-field-index="${fieldIndex}"]`);
        const card = document.querySelector(`.field-card[data-field-index="${fieldIndex}"], .field-table-card[data-field-index="${fieldIndex}"], .field-item-card[data-field-index="${fieldIndex}"]`);

        if (box) box.classList.remove('highlighted');
        if (card) card.classList.remove('highlighted');
    },

    getDocumentTypeIcon(type) {
        return '';
    },

    getDocumentTypeDisplayName(type) {
        switch ((type || '').toUpperCase()) {
            case 'PASSPORT':
            case 'PASSPORT_RF':
                return 'Паспорт РФ';
            case 'PTS':
                return 'Паспорт ТС (ПТС)';
            case 'STS':
                return 'Свидетельство о регистрации ТС (СТС)';
            case 'DRIVER_LICENSE':
                return 'Водительское удостоверение';
            case 'SNILS':
                return 'СНИЛС';
            case 'INN':
                return 'Свидетельство ИНН';
            case 'RECEIPT':
                return 'Квитанция / Счёт ЖКУ';
            case 'CASH_RECEIPT':
                return 'Кассовый чек';
            case 'BANK_STATEMENT':
                return 'Банковская выписка';
            case 'TECH_PASSPORT':
                return 'Техпаспорт оборудования';
            case 'MEDICAL_REPORT':
                return 'Медицинские анализы / Заключение';
            case 'LEGAL_HR':
                return 'Судебный / Кадровый документ';
            case 'CONTRACT':
                return 'Договор';
            case 'INVOICE':
                return 'Счёт на оплату';
            case 'ACT':
                return 'Акт выполненных работ';
            case 'TAX_2NDFL':
                return 'Справка 2-НДФЛ';
            case 'CERTIFICATE':
                return 'Свидетельство / Справка';
            default:
                return 'Не определен';
        }
    },

    getDisplayDocType(doc) {
        if (!doc) return 'Не определён';
        const name = typeof doc === 'string' ? doc : (doc.documentTypeDisplayName || doc.displayName || doc.detectedTypeDisplayName);
        if (name && !name.includes('?')) return name;
        const rawType = typeof doc === 'string' ? doc : (doc.documentType || doc.type || doc.detectedType);
        return this.getDocumentTypeDisplayName(rawType);
    },

    /**
     * === Интерактивная вопросно-ответная система (Document Q&A with Visual Grounding) ===
     */
    setupQaListeners() {
        const qaInput = document.getElementById('qa-input');
        const btnAsk = document.getElementById('btn-qa-ask');
        const chips = document.querySelectorAll('.qa-chip');

        if (qaInput) {
            qaInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.submitDocumentQuestion();
                }
            });
        }

        if (btnAsk) {
            btnAsk.addEventListener('click', () => {
                this.submitDocumentQuestion();
            });
        }

        chips.forEach(chip => {
            chip.addEventListener('click', () => {
                const q = chip.dataset.question || chip.textContent;
                if (qaInput) {
                    qaInput.value = q;
                }
                this.submitDocumentQuestion();
            });
        });
    },

    resetQaTab() {
        const qaInput = document.getElementById('qa-input');
        if (qaInput) qaInput.value = '';
        const loader = document.getElementById('qa-status-loading');
        if (loader) loader.style.display = 'none';

        const answersList = document.getElementById('qa-answers-list');
        if (answersList) {
            answersList.innerHTML = `
                <div class="qa-empty-state" style="text-align: center; color: var(--text-muted); padding: 32px 10px;">
                    <div style="margin-bottom: 8px;">
                        <svg style="width: 18px; height: 18px; color: var(--text-muted);"><use href="#icon-message-square"></use></svg>
                    </div>
                    <h4 style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Естественный диалог с документом</h4>
                    <p style="font-size: 11.5px; color: var(--text-muted);">Задайте любой вопрос на русском языке. AI найдёт точный ответ, процитирует источник и подсветит координаты на скане.</p>
                </div>
            `;
        }

        // Очищаем подсветку Q&A со скана
        const overlay = document.getElementById('bbox-overlay-layer');
        if (overlay) {
            overlay.querySelectorAll('.bbox-pulse-highlight').forEach(el => el.remove());
        }
    },

    async submitDocumentQuestion() {
        const qaInput = document.getElementById('qa-input');
        if (!qaInput || !this.currentAnalysisDocId) return;

        const question = qaInput.value.trim();
        if (!question) return;

        const loader = document.getElementById('qa-status-loading');
        const btnAsk = document.getElementById('btn-qa-ask');
        const answersList = document.getElementById('qa-answers-list');

        // Убираем empty-state, если он есть
        const emptyState = answersList.querySelector('.qa-empty-state');
        if (emptyState) emptyState.remove();

        if (loader) loader.style.display = 'flex';
        if (btnAsk) btnAsk.disabled = true;

        try {
            const resp = await ApiClient.askQuestion(this.currentAnalysisDocId, question);
            console.log('Q&A ответ получен:', resp);

            const isSuccess = resp.status === 'success';
            const isPartial = resp.status === 'partial';
            const cardClass = isSuccess ? 'success-answer' : (isPartial ? 'partial-answer' : 'notfound-answer');

            const confPct = Math.round((resp.confidence || 0) * 100);
            const confClass = confPct >= 75 ? 'conf-high' : (confPct >= 40 ? 'conf-mid' : 'conf-low');

            const card = document.createElement('div');
            card.className = `qa-card ${cardClass}`;

            const bboxAttr = resp.bbox ? JSON.stringify(resp.bbox) : '';
            const pageNum = resp.page || 1;

            card.innerHTML = `
                <div class="qa-q-row">
                    <span class="qa-q-text">${this.escapeHtml(resp.question || question)}</span>
                    <span class="conf-pill ${confClass}">${confPct}%</span>
                </div>
                <div class="qa-ans-box">
                    <div class="qa-ans-label">Ответ:</div>
                    <div class="qa-ans-value">${this.escapeHtml(resp.answer)}</div>
                </div>
                ${resp.snippet ? `
                    <div class="qa-snippet-box">
                        «${this.escapeHtml(resp.snippet)}»
                    </div>
                ` : ''}
                <div class="qa-footer-row">
                    <span class="text-muted" style="font-size: 0.78em;">
                        ${resp.message ? this.escapeHtml(resp.message) : (isSuccess ? 'Точное совпадение' : 'Эвристический поиск')}
                        ${pageNum > 1 ? `• Стр. ${pageNum}` : ''}
                    </span>
                    ${resp.bbox ? `
                        <button class="btn-locate-bbox" data-page="${pageNum}">
                            <svg style="width: 12px; height: 12px; vertical-align: -1px; margin-right: 3px;"><use href="#icon-crosshair"></use></svg>
                            <span>Показать на скане</span>
                        </button>
                    ` : ''}
                </div>
            `;

            const locateBtn = card.querySelector('.btn-locate-bbox');
            if (locateBtn) {
                locateBtn.addEventListener('click', () => {
                    this.highlightQaBbox(resp.bbox, pageNum);
                });
            }

            answersList.prepend(card);

            // Если есть координаты, автоматически центрируем и подсвечиваем область
            if (resp.bbox) {
                this.highlightQaBbox(resp.bbox, pageNum);
            }

            qaInput.value = '';

        } catch (error) {
            console.error('Ошибка Q&A:', error);
            const errCard = document.createElement('div');
            errCard.className = 'qa-card notfound-answer';
            errCard.innerHTML = `
                <div class="qa-q-row">
                    <span class="qa-q-text">${this.escapeHtml(question)}</span>
                    <span class="conf-pill conf-low">0%</span>
                </div>
                <div style="color: var(--danger-text); font-size: 0.85em;">
                    Не удалось получить ответ: ${this.escapeHtml(error.message)}
                </div>
            `;
            answersList.prepend(errCard);
        } finally {
            if (loader) loader.style.display = 'none';
            if (btnAsk) btnAsk.disabled = false;
        }
    },

    highlightQaBbox(bbox, targetPage) {
        if (!bbox || !Array.isArray(bbox) || bbox.length !== 4) return;

        // Если ответ на другой странице — переключаем страницу
        if (targetPage && targetPage !== this.currentPage && targetPage <= this.totalPages) {
            this.switchPage(targetPage);
        }

        const overlay = document.getElementById('bbox-overlay-layer');
        const img = document.getElementById('scan-img');
        const container = document.getElementById('viewer-container');
        if (!overlay || !img) return;

        // Удаляем предыдущие пульсирующие подсветки
        overlay.querySelectorAll('.bbox-pulse-highlight').forEach(el => el.remove());

        const q = (this.currentAnalysisData && this.currentAnalysisData.quality) || {};
        const docWidth = (q.width && q.width > 0) ? q.width : (this.viewerZoom.naturalWidth || img.naturalWidth || 1000);
        const docHeight = (q.height && q.height > 0) ? q.height : (this.viewerZoom.naturalHeight || img.naturalHeight || 1000);

        const [x1, y1, x2, y2] = bbox;
        const leftPct = (x1 / docWidth) * 100;
        const topPct = (y1 / docHeight) * 100;
        const widthPct = ((x2 - x1) / docWidth) * 100;
        const heightPct = ((y2 - y1) / docHeight) * 100;

        const pulseBox = document.createElement('div');
        pulseBox.className = 'ocr-box field-box bbox-pulse-highlight';
        pulseBox.style.left = `${leftPct}%`;
        pulseBox.style.top = `${topPct}%`;
        pulseBox.style.width = `${Math.max(1.0, widthPct)}%`;
        pulseBox.style.height = `${Math.max(1.0, heightPct)}%`;

        const tag = document.createElement('span');
        tag.className = 'field-box-tag';
        tag.style.background = '#2563EB';
        tag.style.color = '#FFFFFF';
        tag.style.fontWeight = 'bold';
        tag.textContent = 'НАЙДЕННЫЙ ОТВЕТ';
        pulseBox.appendChild(tag);

        overlay.appendChild(pulseBox);

        // Плавный скролл просмотрщика точно на найденную область
        if (container) {
            const currentImgWidth = img.clientWidth || img.naturalWidth;
            const currentImgHeight = img.clientHeight || img.naturalHeight;
            const targetX = (x1 / docWidth) * currentImgWidth;
            const targetY = (y1 / docHeight) * currentImgHeight;

            container.scrollTo({
                left: Math.max(0, targetX - container.clientWidth / 2),
                top: Math.max(0, targetY - container.clientHeight / 2),
                behavior: 'smooth'
            });
        }
    }
};

window.App = App;

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
