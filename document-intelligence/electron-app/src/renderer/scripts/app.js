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

    init() {
        console.log('Document Intelligence UI запущен');
        console.log('Платформа:', window.api ? window.api.platform : 'browser');

        this.setupNavigation();
        this.setupHealthCheck();
        this.setupFileUpload();
        this.setupDocumentsPage();
        this.setupAnalysisModal();
        this.setupSettings();

        // Проверяем доступность сервисов и загружаем статистику
        this.checkHealth();
        this.loadDashboardData();
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
            quickUploadBtn.addEventListener('click', () => this.navigateTo('upload'));
        }
    },

    navigateTo(pageName) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

        const navItem = document.querySelector(`.nav-item[data-page="${pageName}"]`);
        const page = document.getElementById(`page-${pageName}`);

        if (navItem) navItem.classList.add('active');
        if (page) page.classList.add('active');

        // При переходе на вкладку документов — обновляем список
        if (pageName === 'documents') {
            this.loadDocuments();
        } else if (pageName === 'dashboard') {
            this.loadDashboardData();
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

    async checkHealth() {
        const btn = document.getElementById('btn-check-health');
        const resultBox = document.getElementById('health-result');

        this.updateStatusBadge('status-java', 'checking', 'Проверка...');
        this.updateStatusBadge('status-ai', 'checking', 'Проверка...');
        this.updateStatusBadge('status-db', 'checking', 'Проверка...');

        if (btn) btn.disabled = true;

        try {
            const health = await ApiClient.checkHealth();

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
            if (health.database && health.database.startsWith('connected')) {
                this.updateStatusBadge('status-db', 'healthy', 'Подключена ✓');
            } else {
                this.updateStatusBadge('status-db', 'error', 'Недоступна ✗');
            }

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
     * Настройка страницы загрузки документов (Drag-and-Drop + File Input).
     */
    setupFileUpload() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const btnBrowse = document.getElementById('btn-browse-file');
        const btnUpload = document.getElementById('btn-start-upload');
        const btnCancel = document.getElementById('btn-cancel-file');

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
                this.handleFileSelected(e.target.files[0]);
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
                this.handleFileSelected(dt.files[0]);
            }
        });

        // Отмена выбранного файла
        btnCancel.addEventListener('click', () => {
            this.clearSelectedFile();
        });

        // Кнопка отправки на сервер
        btnUpload.addEventListener('click', () => {
            this.uploadSelectedFile();
        });
    },

    handleFileSelected(file) {
        this.selectedFile = file;

        const card = document.getElementById('selected-file-card');
        const nameEl = document.getElementById('selected-file-name');
        const sizeEl = document.getElementById('selected-file-size');
        const statusEl = document.getElementById('upload-status');

        if (nameEl) nameEl.textContent = file.name;
        if (sizeEl) sizeEl.textContent = this.formatFileSize(file.size);
        if (card) card.style.display = 'flex';
        if (statusEl) statusEl.style.display = 'none';
    },

    clearSelectedFile() {
        this.selectedFile = null;
        const fileInput = document.getElementById('file-input');
        if (fileInput) fileInput.value = '';

        const card = document.getElementById('selected-file-card');
        if (card) card.style.display = 'none';

        const statusEl = document.getElementById('upload-status');
        if (statusEl) statusEl.style.display = 'none';
    },

    async uploadSelectedFile() {
        if (!this.selectedFile) return;

        const btnUpload = document.getElementById('btn-start-upload');
        const statusEl = document.getElementById('upload-status');

        if (btnUpload) {
            btnUpload.disabled = true;
            btnUpload.textContent = '⏳ Отправка...';
        }

        try {
            const result = await ApiClient.uploadDocument(this.selectedFile);

            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.className = 'alert-box success';
                statusEl.innerHTML = `✅ Документ успешно загружен! <br><strong>ID:</strong> #${result.id} | <strong>Имя:</strong> ${result.originalFilename} | <strong>Статус:</strong> ${result.status}`;
            }

            // Очищаем выбранный файл через небольшую паузу
            setTimeout(() => {
                this.clearSelectedFile();
                this.loadDashboardData();
            }, 2500);

        } catch (error) {
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.className = 'alert-box error';
                statusEl.innerHTML = `❌ Ошибка при загрузке файла: <br>${error.message}`;
            }
        } finally {
            if (btnUpload) {
                btnUpload.disabled = false;
                btnUpload.textContent = '🚀 Отправить на сервер';
            }
        }
    },

    /**
     * Настройка вкладки "Документы" и загрузка реестра.
     */
    setupDocumentsPage() {
        const btnRefresh = document.getElementById('btn-refresh-docs');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => this.loadDocuments());
        }

        const tbody = document.getElementById('documents-table-body');
        if (tbody) {
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
                } else if (action === 'delete') {
                    this.confirmDeleteDocument(id);
                }
            });
        }
    },

    async loadDocuments() {
        const tbody = document.getElementById('documents-table-body');
        if (!tbody) return;

        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Загрузка данных...</td></tr>`;

        try {
            const data = await ApiClient.getDocuments(0, 50);
            const documents = data.content || [];

            if (documents.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Загруженных документов пока нет. Перейдите во вкладку "Загрузка", чтобы добавить первый документ.</td></tr>`;
                return;
            }

            tbody.innerHTML = documents.map(doc => `
                <tr>
                    <td>#${doc.id}</td>
                    <td><strong>${this.escapeHtml(doc.originalFilename)}</strong></td>
                    <td>${this.escapeHtml(doc.documentTypeDisplayName || doc.documentType)}</td>
                    <td>${this.formatFileSize(doc.fileSize)}</td>
                    <td><span class="badge ${this.getStatusBadgeClass(doc.status)}">${doc.status}</span></td>
                    <td>${doc.overallConfidence ? Math.round(doc.overallConfidence * 100) + '%' : '—'}</td>
                    <td>${this.formatDate(doc.createdAt)}</td>
                    <td>
                        <button class="btn btn-primary btn-sm" data-action="analyze" data-id="${doc.id}">⚡ Анализ</button>
                        <button class="btn btn-secondary btn-sm" data-action="view" data-id="${doc.id}">👁️ Скан</button>
                        <button class="btn btn-danger btn-sm" data-action="delete" data-id="${doc.id}">🗑️</button>
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: var(--error);">Ошибка загрузки реестра: ${error.message}</td></tr>`;
        }
    },

    viewDocumentFile(id) {
        const fileUrl = ApiClient.getDocumentFileUrl(id);
        window.open(fileUrl, '_blank');
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
     * Загрузка данных для Dashboard.
     */
    async loadDashboardData() {
        const countEl = document.getElementById('dashboard-total-count');
        const recentContainer = document.getElementById('dashboard-recent-list');

        try {
            const recentDocs = await ApiClient.getRecentDocuments(5);
            const totalCount = recentDocs.length; // в полностраничном API будет totalElements

            if (countEl) {
                // Запрашиваем полный список для точного количества
                const fullList = await ApiClient.getDocuments(0, 1);
                countEl.textContent = fullList.totalElements !== undefined ? fullList.totalElements : recentDocs.length;
            }

            if (recentContainer) {
                if (recentDocs.length === 0) {
                    recentContainer.innerHTML = `<p class="text-muted">Загруженных документов пока нет.</p>`;
                } else {
                    recentContainer.innerHTML = recentDocs.map(doc => `
                        <div class="recent-doc-item">
                            <div class="recent-doc-info">
                                <span>📄</span>
                                <div>
                                    <strong>${this.escapeHtml(doc.originalFilename)}</strong>
                                    <div class="text-muted" style="font-size: 0.8em;">#${doc.id} • ${doc.documentTypeDisplayName || doc.documentType} • ${this.formatDate(doc.createdAt)}</div>
                                </div>
                            </div>
                            <span class="badge ${this.getStatusBadgeClass(doc.status)}">${doc.status}</span>
                        </div>
                    `).join('');
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

        // Переключение 3 вкладок в инспекторе (Поля, OCR, Валидация)
        const tabBtns = document.querySelectorAll('.inspector-tabs .tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const tab = btn.dataset.tab;
                const fieldsContent = document.getElementById('tab-fields-content');
                const ocrContent = document.getElementById('tab-ocr-content');
                const valContent = document.getElementById('tab-validation-content');
                
                if (fieldsContent) fieldsContent.style.display = tab === 'fields' ? 'flex' : 'none';
                if (ocrContent) ocrContent.style.display = tab === 'ocr' ? 'flex' : 'none';
                if (valContent) valContent.style.display = tab === 'validation' ? 'flex' : 'none';
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
            btnZoomReset.onclick = () => this.setZoom(1.0);
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
                if (e.target.closest('.btn-tool') || e.target.closest('.field-box-tag')) return;

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
        this.viewerZoom.scale = scale;
        const wrapper = document.getElementById('scan-wrapper');
        const badge = document.getElementById('zoom-level-badge');
        if (badge) {
            badge.textContent = `${Math.round(scale * 100)}%`;
        }
        if (wrapper && this.viewerZoom.naturalWidth > 0) {
            wrapper.style.width = `${Math.round(this.viewerZoom.naturalWidth * scale)}px`;
        }
    },

    fitViewer() {
        const container = document.getElementById('viewer-container');
        if (!container || this.viewerZoom.naturalWidth <= 0) return;

        const availWidth = container.clientWidth - 48;
        if (availWidth <= 0) return;
        const scale = availWidth / this.viewerZoom.naturalWidth;
        this.setZoom(Math.max(0.1, Math.min(5.0, Math.round(scale * 100) / 100)));
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
        if (tabFieldsBtn) tabFieldsBtn.classList.add('active');
        if (tabOcrBtn) tabOcrBtn.classList.remove('active');
        if (tabValBtn) tabValBtn.classList.remove('active');

        const fieldsContent = document.getElementById('tab-fields-content');
        const ocrContent = document.getElementById('tab-ocr-content');
        const valContent = document.getElementById('tab-validation-content');
        if (fieldsContent) fieldsContent.style.display = 'flex';
        if (ocrContent) ocrContent.style.display = 'none';
        if (valContent) valContent.style.display = 'none';

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
            btnAnalyze.innerHTML = `⚡ Запустить AI-анализ`;
        }

        try {
            // Запрашиваем детали документа
            const doc = await ApiClient.getDocument(docId);
            titleEl.textContent = `${doc.originalFilename} (#${doc.id})`;
            statusEl.className = `badge ${this.getStatusBadgeClass(doc.status)}`;
            statusEl.textContent = doc.status;

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
                this.fitViewer();
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
                            Нажмите "⚡ Запустить AI-анализ", чтобы извлечь реквизиты
                        </p>
                    `;
                }
                ocrList.innerHTML = `
                    <p class="text-muted text-center" style="margin-top: 40px;">
                        Нажмите "⚡ Запустить AI-анализ", чтобы распознать текст на документе
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
            metricsBar.innerHTML = `<span style="color: var(--error);">Ошибка: ${error.message}</span>`;
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
            btnAnalyze.innerHTML = `⏳ Идёт распознавание (OCR)...`;
        }

        metricsBar.innerHTML = `<span class="text-muted">⚡ Запущен конвейер: PyMuPDF -> OpenCV Deskew/CLAHE -> PaddleOCR...</span>`;
        ocrList.innerHTML = `<p class="text-muted text-center" style="margin-top: 40px;">⏳ Нейросеть распознаёт символы и строит bounding boxes...</p>`;

        try {
            const result = await ApiClient.analyzeDocument(this.currentAnalysisDocId);
            console.log('Результат анализа получен:', result);

            this.renderAnalysisResult(result);
            this.loadDocuments();
            this.loadDashboardData();

            const statusEl = document.getElementById('modal-doc-status');
            if (statusEl) {
                statusEl.className = `badge ${this.getStatusBadgeClass('COMPLETED')}`;
                statusEl.textContent = 'COMPLETED';
            }

        } catch (error) {
            console.error('Ошибка запуска анализа:', error);
            metricsBar.innerHTML = `<span style="color: var(--error);">Ошибка анализа: ${error.message}</span>`;
            ocrList.innerHTML = `<p class="text-center" style="color: var(--error); margin-top: 40px;">${error.message}</p>`;
        } finally {
            if (btnAnalyze) {
                btnAnalyze.disabled = false;
                btnAnalyze.innerHTML = `⚡ Перезапустить анализ`;
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
            const displayName = analysis.detectedTypeDisplayName || this.getDocumentTypeDisplayName(detectedType);
            const typeConf = analysis.typeConfidence ? Math.round(analysis.typeConfidence * 100) : 0;
            const explanation = analysis.explanation || '';
            const typeClass = detectedType.toLowerCase();

            classBadge.innerHTML = `
                <span class="doc-type-badge ${typeClass}" title="${this.escapeHtml(explanation)}">
                    ${this.getDocumentTypeIcon(detectedType)} ${displayName} (${typeConf}%)
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
                let icon = '✓';
                let cls = 'passed';
                let text = `Проверка: ${passed}/${total} ОК`;
                if (failed > 0) {
                    icon = '❌';
                    cls = 'failed';
                    text = `Ошибок: ${failed}`;
                } else if (warnings > 0) {
                    icon = '⚠️';
                    cls = 'warning';
                    text = `Предупреждений: ${warnings}`;
                }
                valBadge.className = `val-badge ${cls}`;
                valBadge.innerHTML = `${icon} ${text}`;
                valBadge.onclick = () => {
                    const tabValBtn = document.getElementById('tab-validation-btn');
                    if (tabValBtn) tabValBtn.click();
                };
            }

            if (valList) {
                const summaryHtml = `
                    <div class="validation-summary-card">
                        <div>
                            <strong>Итог валидации (Этап 9):</strong>
                            <span class="val-status-pill val-status-${overall.toLowerCase()}">
                                ${overall === 'PASSED' ? '✓ ВСЕ ПРАВИЛА ПРОЙДЕНЫ' : (overall === 'WARNING' ? '⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ' : '❌ НАЙДЕНЫ ОШИБКИ')}
                            </span>
                        </div>
                        <div style="font-size: 0.85em; display: flex; gap: 12px;">
                            <span style="color: var(--success); font-weight: 600;">✓ ${passed}</span>
                            <span style="color: var(--warning); font-weight: 600;">⚠️ ${warnings}</span>
                            <span style="color: var(--error); font-weight: 600;">❌ ${failed}</span>
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
                                    ${rStatus === 'passed' ? '✓' : (rStatus === 'warning' ? '⚠️' : '❌')}
                                    ${this.escapeHtml(rName)}
                                </span>
                                <div style="display: flex; gap: 6px; align-items: center;">
                                    <span class="val-rule-cat">${this.escapeHtml(rCat)}</span>
                                    <span class="val-status-pill val-status-${rStatus}">${rStatus.toUpperCase()}</span>
                                </div>
                            </div>
                            <div class="val-rule-msg">${this.escapeHtml(rMsg)}</div>
                            ${rDetails ? `<div class="text-muted" style="font-size: 0.78em; font-family: monospace;">${this.escapeHtml(typeof rDetails === 'object' ? JSON.stringify(rDetails) : rDetails)}</div>` : ''}
                            ${rSugg ? `<div class="val-rule-suggestion">💡 Рекомендация: ${this.escapeHtml(rSugg)}</div>` : ''}
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
            <span class="metric-pill ${isBlurry ? 'warning' : 'success'}">
                ${isBlurry ? '⚠️ Размыто' : '✓ Чётко'} (Резкость: ${blurScore})
            </span>
            <span class="metric-pill">
                📐 Наклон: ${skewAngle}°
            </span>
            <span class="metric-pill">
                ⏱️ Время: ${timeMs} мс
            </span>
            <span class="metric-pill success">
                🎯 Точность: ${confPct}%
            </span>
            <span class="metric-pill">
                📄 Страниц: ${analysis.totalPages || 1}
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
                                            📊 ${this.escapeHtml(label)}
                                            <span class="field-type-pill">ТАБЛИЦА</span>
                                        </div>
                                        <div style="display: flex; gap: 8px; align-items: center;">
                                            <button class="btn-export-table" onclick="event.stopPropagation(); App.copyTableAsCsv(${fIdx});">
                                                📋 Скопировать CSV
                                            </button>
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
                                        <span>Строк: ${tableData.rows.length} ${hasBbox ? `• 📍 ${bboxCoords}` : ''}</span>
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
                                valIndicator = innRule.status === 'PASSED' ? '<span class="field-val-icon" title="ИНН проверен по контрольным суммам ФНС" style="color: var(--success);">✓</span>' : '<span class="field-val-icon" title="Ошибка контрольной суммы ИНН" style="color: var(--error);">⚠️</span>';
                            }
                        } else if (fieldKey.includes('vin') || fieldKey.includes('вин')) {
                            const vinRule = valData.rules.find(r => (r.ruleId || '').includes('vin'));
                            if (vinRule) {
                                valIndicator = vinRule.status === 'PASSED' ? '<span class="field-val-icon" title="VIN проверен по ISO 3779" style="color: var(--success);">✓</span>' : '<span class="field-val-icon" title="Предупреждение VIN" style="color: var(--warning);">⚠️</span>';
                            }
                        }
                    }

                    return `
                        <div class="field-card" data-field-index="${fIdx}">
                            <div class="field-card-header">
                                <span class="field-card-label">${this.escapeHtml(label)}</span>
                                <span class="field-type-pill">${this.escapeHtml(typeTitle)}</span>
                            </div>
                            <div class="field-card-value">${this.escapeHtml(val || '—')} ${valIndicator}</div>
                            <div class="field-card-meta">
                                <span class="conf-pill ${confClass}">Точность: ${conf}%</span>
                                <span>${hasBbox ? `📍 ${bboxCoords}` : 'Стр. ' + (f.pageNumber || 1)}</span>
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
                        <div class="ocr-block-text">${this.escapeHtml(block.text)}</div>
                        <div class="ocr-block-meta">
                            <span class="conf-pill ${confClass}">${conf}%</span>
                            <span>[${bboxStr}] • Стр. ${block.page || 1}</span>
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
            fieldsList.querySelectorAll('.field-card, .field-table-card').forEach(card => {
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
            alert('✓ Таблица скопирована в буфер обмена в формате CSV/Excel (с разделителем ;)!');
        }).catch(err => {
            console.error('Ошибка копирования:', err);
            // Fallback: prompt
            prompt('Скопируйте CSV вручную:', csvText);
        });
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
        const card = document.querySelector(`.field-card[data-field-index="${fieldIndex}"], .field-table-card[data-field-index="${fieldIndex}"]`);

        if (box) box.classList.add('highlighted');
        if (card) {
            card.classList.add('highlighted');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    unhighlightField(fieldIndex) {
        const box = document.querySelector(`.ocr-box.field-box[data-field-index="${fieldIndex}"]`);
        const card = document.querySelector(`.field-card[data-field-index="${fieldIndex}"], .field-table-card[data-field-index="${fieldIndex}"]`);

        if (box) box.classList.remove('highlighted');
        if (card) card.classList.remove('highlighted');
    },

    getDocumentTypeIcon(type) {
        switch ((type || '').toUpperCase()) {
            case 'PASSPORT':
            case 'PASSPORT_RF':
                return '🛂';
            case 'CONTRACT':
                return '📋';
            case 'INVOICE':
                return '🧾';
            case 'ACT':
                return '📑';
            case 'TAX_2NDFL':
                return '💰';
            case 'CERTIFICATE':
                return '📜';
            case 'APPLICATION':
                return '✉️';
            case 'PTS':
                return '🚗';
            case 'RECEIPT':
                return '💡';
            default:
                return '📄';
        }
    },

    getDocumentTypeDisplayName(type) {
        switch ((type || '').toUpperCase()) {
            case 'PASSPORT':
            case 'PASSPORT_RF':
                return 'Паспорт РФ';
            case 'PTS':
                return 'Паспорт ТС (ПТС)';
            case 'RECEIPT':
                return 'Квитанция / Счёт ЖКУ';
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
    }
};

window.App = App;

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
