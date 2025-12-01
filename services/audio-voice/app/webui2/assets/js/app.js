/**
 * Audio Voice Service - WebUI Application
 * Gerencia toda a interação com a API REST
 */

/**
 * ========================================================
 * FIX INT-05: Suppress Chrome Extension Runtime Errors
 * ========================================================
 * 
 * Reference: https://stackoverflow.com/questions/54126343
 * Issue: CRITICAL_ISSUE_INT05_RUNTIME_ERROR.md
 * 
 * CONTEXT:
 * Chrome extensions (VPN, AdBlock, Translators, etc) intercept page events
 * and cause "Unchecked runtime.lastError: The message port closed before a response was received"
 * 
 * This is NOT a bug in our application code - it's caused by third-party extensions
 * that don't properly handle async responses in chrome.runtime.sendMessage().
 * 
 * IMPACT WITHOUT FIX:
 * - Console polluted with irrelevant errors
 * - Difficult to debug real application errors
 * - QA wastes time investigating false positives
 * 
 * SOLUTION:
 * Monkey patch console.error to filter known extension error patterns.
 */
(function suppressExtensionErrors() {
  // Known error patterns from Chrome extensions
  const EXTENSION_ERROR_PATTERNS = [
    'message port closed',
    'Extension context invalidated',
    'runtime.lastError',
    'chrome.runtime',
    'browser.runtime',
    'Could not establish connection',
    'Receiving end does not exist'
  ];

  // Save original console.error
  const originalConsoleError = console.error.bind(console);

  // Replace console.error with filter
  console.error = function(...args) {
    const errorString = args.join(' ').toLowerCase();
    
    // Check if it's an extension error
    const isExtensionError = EXTENSION_ERROR_PATTERNS.some(pattern => 
      errorString.includes(pattern.toLowerCase())
    );
    
    if (isExtensionError) {
      // Log to debug only (for developers who want to see)
      console.debug('[SUPPRESSED EXTENSION ERROR]', ...args);
      return;
    }
    
    // Real errors pass through normally
    originalConsoleError(...args);
  };

  console.log('✅ Extension error suppression activated (INT-05 fix)');
})();

/**
 * API Base URL Configuration
 * 
 * Uses hostname-based detection (more robust than port detection):
 * - Local development: '' (same origin - localhost:8005)
 * - Production: 'https://clone.loadstask.com'
 * 
 * Previous approach used port detection (8080 vs 8005) which was:
 * - ❌ Magic number (8080 hardcoded)
 * - ❌ Environment-specific (breaks on different ports)
 * - ❌ Infrastructure logic in frontend (violation of SoC)
 * 
 * Current approach:
 * - ✅ Hostname-based (works on any port)
 * - ✅ Environment-agnostic
 * - ✅ Separation of concerns
 */
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? '' // Same origin (e.g., http://localhost:8005)
  : 'https://clone.loadstask.com';

console.log(`🌐 API Base URL: ${API_BASE || window.location.origin}`);

const app = {
    // ==================== ESTADO GLOBAL ====================
    state: {
        currentSection: 'dashboard',
        languages: [],
        presets: [],
        voices: [],
        rvcModels: [],
        qualityProfiles: { xtts_profiles: [], f5tts_profiles: [] },
        cloningJobs: {}, // Job IDs de clonagens em andamento
        jobsAutoRefreshInterval: null,
        currentJobMonitorInterval: null, // Intervalo de monitoramento do job buscado
    },

    // ==================== INICIALIZAÇÃO ====================
    init() {
        console.log('🚀 Inicializando Audio Voice Service WebUI...');
        
        // Event listeners
        this.setupEventListeners();
        
        // Carregar dados iniciais
        this.loadInitialData();
        
        // Navegar para dashboard
        this.navigate('dashboard');
        
        console.log('✅ WebUI inicializada com sucesso!');
    },

    setupEventListeners() {
        // Form: Create Job
        document.getElementById('form-create-job')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createJob();
        });

        // Form: Clone Voice
        document.getElementById('form-clone-voice')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.cloneVoice();
        });

        // Form: Upload RVC Model
        document.getElementById('form-upload-rvc')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadRvcModel();
        });

        // Form: Create Quality Profile
        document.getElementById('form-create-quality-profile')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createQualityProfile();
        });

        // Form: Edit Quality Profile
        document.getElementById('form-edit-quality-profile')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateQualityProfile();
        });

        // Text counter
        document.getElementById('job-text')?.addEventListener('input', (e) => {
            document.getElementById('text-counter').textContent = e.target.value.length;
        });

        // Mode change handler
        document.getElementById('job-mode')?.addEventListener('change', (e) => {
            this.toggleVoiceMode(e.target.value);
        });

        // TTS Engine change handler
        document.getElementById('job-tts-engine')?.addEventListener('change', (e) => {
            this.loadQualityProfilesForEngine(e.target.value);
            this.updateRefTextVisibility(); // BUG-02 fix
        });
        
        // Mode change also affects ref_text visibility
        const originalModeHandler = document.getElementById('job-mode')?.onchange;
        document.getElementById('job-mode')?.addEventListener('change', (e) => {
            this.updateRefTextVisibility(); // BUG-02 fix
        });

        // Enable RVC toggle
        document.getElementById('job-enable-rvc')?.addEventListener('change', (e) => {
            document.getElementById('rvc-params').style.display = e.target.checked ? 'block' : 'none';
        });

        // RVC sliders
        this.setupRangeSliders();

        // Jobs auto-refresh
        document.getElementById('jobs-auto-refresh')?.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.state.jobsAutoRefreshInterval = setInterval(() => this.loadJobs(), 10000);
            } else {
                clearInterval(this.state.jobsAutoRefreshInterval);
                this.state.jobsAutoRefreshInterval = null;
            }
        });

        // RVC sort change
        document.getElementById('rvc-sort-by')?.addEventListener('change', () => {
            this.loadRvcModels();
        });
    },

    setupRangeSliders() {
        const sliders = [
            { id: 'job-rvc-pitch', display: 'rvc-pitch-val' },
            { id: 'job-rvc-index-rate', display: 'rvc-index-rate-val' },
            { id: 'job-rvc-filter-radius', display: 'rvc-filter-radius-val' },
            { id: 'job-rvc-rms-mix-rate', display: 'rvc-rms-mix-rate-val' },
            { id: 'job-rvc-protect', display: 'rvc-protect-val' },
        ];

        sliders.forEach(({ id, display }) => {
            const slider = document.getElementById(id);
            const displayEl = document.getElementById(display);
            if (slider && displayEl) {
                slider.addEventListener('input', (e) => {
                    displayEl.textContent = e.target.value;
                });
            }
        });
    },

    async loadInitialData() {
        console.log('📥 Carregando dados iniciais...');
        
        try {
            await Promise.all([
                this.loadLanguages(),
                this.loadPresets(),
            ]);
        } catch (error) {
            console.error('❌ Erro ao carregar dados iniciais:', error);
        }
    },

    // ==================== NAVEGAÇÃO ====================
    navigate(section) {
        console.log(`🧭 Navegando para: ${section}`);
        
        // Esconder todas as seções
        document.querySelectorAll('.content-section').forEach(el => {
            el.style.display = 'none';
        });

        // Mostrar seção solicitada
        const sectionEl = document.getElementById(`section-${section}`);
        if (sectionEl) {
            sectionEl.style.display = 'block';
            this.state.currentSection = section;

            // Carregar dados específicos da seção
            this.loadSectionData(section);

            // Atualizar navbar (active state)
            document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
                link.classList.remove('active');
            });
        } else {
            console.warn(`⚠️ Seção não encontrada: ${section}`);
        }
    },

    loadSectionData(section) {
        switch (section) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'create-job':
                this.loadVoices();
                this.loadRvcModels();
                this.loadQualityProfiles();
                // QA FIX: Inicializar visibilidade do campo ref_text
                setTimeout(() => this.updateRefTextVisibility(), 100);
                break;
            case 'jobs':
                this.loadJobs();
                break;
            case 'voices':
                this.loadVoices();
                break;
            case 'rvc-models':
                this.loadRvcModels();
                this.loadRvcStats();
                break;
            case 'quality-profiles':
                this.loadQualityProfiles();
                break;
            case 'admin':
                this.loadAdminSection();
                break;
            case 'feature-flags':
                this.loadFeatureFlags();
                break;
        }
    },

    // ==================== API HELPERS ====================
    async fetchJson(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                },
            });

            if (!response.ok) {
                let errorMsg = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) {
                        if (Array.isArray(errorData.detail)) {
                            errorMsg = errorData.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                        } else {
                            errorMsg = errorData.detail;
                        }
                    }
                } catch (e) {
                    errorMsg = await response.text() || errorMsg;
                }
                throw new Error(errorMsg);
            }

            // Handle 204 No Content (DELETE operations)
            if (response.status === 204 || response.headers.get('content-length') === '0') {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('❌ Fetch error:', error);
            throw error;
        }
    },

    async fetchText(url, options = {}) {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }
        return await response.text();
    },

    // ==================== TOAST SYSTEM ====================
    showToast(title, message, type = 'info') {
        const toastEl = document.getElementById('toast');
        const toastTitle = document.getElementById('toast-title');
        const toastBody = document.getElementById('toast-body');

        toastTitle.textContent = title;
        toastBody.textContent = message;

        // Reset classes
        toastEl.className = 'toast';
        
        // Add type class
        const typeClasses = {
            success: 'bg-success text-white',
            error: 'bg-danger text-white',
            warning: 'bg-warning',
            info: 'bg-info text-white'
        };
        toastEl.classList.add(...(typeClasses[type] || typeClasses.info).split(' '));

        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    },

    // ==================== DASHBOARD ====================
    async loadDashboard() {
        console.log('📊 Carregando dashboard...');
        
        await Promise.all([
            this.loadApiStatus(),
            this.loadAdminStats(),
            this.loadRvcStats(),
            this.loadRecentJobs(),
            this.loadRecentVoices(),
        ]);
    },

    async loadApiStatus() {
        const container = document.getElementById('dashboard-api-status');
        try {
            const data = await this.fetchJson(`${API_BASE}/`);
            container.innerHTML = `
                <div class="text-success mb-2">
                    <i class="bi bi-check-circle-fill fs-1"></i>
                </div>
                <h5>API Online</h5>
                <div class="json-display">${JSON.stringify(data, null, 2)}</div>
            `;
        } catch (error) {
            container.innerHTML = `
                <div class="text-danger">
                    <i class="bi bi-x-circle-fill fs-1"></i>
                    <h5>API Offline</h5>
                    <p class="text-muted">${error.message}</p>
                </div>
            `;
        }
    },

    async loadAdminStats() {
        const container = document.getElementById('dashboard-stats');
        try {
            const data = await this.fetchJson(`${API_BASE}/admin/stats`);
            container.innerHTML = this.renderStatsHtml(data);
        } catch (error) {
            container.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    },

    async loadRvcStats() {
        const container = document.getElementById('dashboard-rvc-stats');
        try {
            const data = await this.fetchJson(`${API_BASE}/rvc-models/stats`);
            container.innerHTML = this.renderStatsHtml(data);
        } catch (error) {
            container.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    },

    async loadRecentJobs() {
        const container = document.getElementById('dashboard-recent-jobs');
        try {
            const data = await this.fetchJson(`${API_BASE}/jobs?limit=5`);
            if (data.jobs && data.jobs.length > 0) {
                container.innerHTML = `
                    <div class="list-group">
                        ${data.jobs.map(job => `
                            <div class="list-group-item">
                                <div class="d-flex justify-content-between">
                                    <span class="text-monospace">${job.id.substring(0, 8)}...</span>
                                    <span class="badge status-badge status-${job.status}">${job.status}</span>
                                </div>
                                <small class="text-muted">${job.tts_engine || 'xtts'} • ${new Date(job.created_at).toLocaleString('pt-BR')}</small>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else {
                container.innerHTML = this.renderEmptyState('Nenhum job encontrado');
            }
        } catch (error) {
            container.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    },

    async loadRecentVoices() {
        const container = document.getElementById('dashboard-recent-voices');
        try {
            const data = await this.fetchJson(`${API_BASE}/voices?limit=5`);
            if (data.voices && data.voices.length > 0) {
                container.innerHTML = `
                    <div class="list-group">
                        ${data.voices.map(voice => `
                            <div class="list-group-item">
                                <div><strong>${voice.name}</strong></div>
                                <small class="text-muted">${voice.language} • ${voice.engine || 'xtts'} • ${new Date(voice.created_at).toLocaleString('pt-BR')}</small>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else {
                container.innerHTML = this.renderEmptyState('Nenhuma voz encontrada');
            }
        } catch (error) {
            container.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    },

    renderStatsHtml(data) {
        return `
            <dl class="row mb-0">
                ${Object.entries(data).map(([key, value]) => `
                    <dt class="col-sm-6">${this.formatKey(key)}</dt>
                    <dd class="col-sm-6">${this.formatValue(value)}</dd>
                `).join('')}
            </dl>
        `;
    },

    // ==================== JOBS ====================
    async loadJobs() {
        const container = document.getElementById('jobs-table-container');
        const limit = document.getElementById('jobs-limit')?.value || 20;
        
        try {
            container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Carregando...</p></div>';
            
            const data = await this.fetchJson(`${API_BASE}/jobs?limit=${limit}`);
            
            if (data.jobs && data.jobs.length > 0) {
                container.innerHTML = `
                    <p class="text-muted">Total: ${data.total} jobs</p>
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Job ID</th>
                                    <th>Status</th>
                                    <th>Engine</th>
                                    <th>Mode</th>
                                    <th>Criado em</th>
                                    <th>Ações</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.jobs.map(job => this.renderJobRow(job)).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            } else {
                container.innerHTML = this.renderEmptyState('Nenhum job encontrado', 'Crie um novo job na seção "Dublar Texto"');
            }
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
            this.showToast('Erro', `Falha ao carregar jobs: ${error.message}`, 'error');
        }
    },

    renderJobRow(job) {
        const statusClass = `status-${job.status}`;
        const canDownload = job.status === 'completed';
        
        return `
            <tr>
                <td class="text-monospace" style="font-size: 0.85rem;">${job.id}</td>
                <td><span class="badge status-badge ${statusClass}">${job.status}</span></td>
                <td>${job.tts_engine || 'xtts'}</td>
                <td>${job.mode}</td>
                <td>${new Date(job.created_at).toLocaleString('pt-BR')}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="app.showJobDetails('${job.id}')">
                            <i class="bi bi-info-circle"></i>
                        </button>
                        ${canDownload ? `
                            <button class="btn btn-outline-success" onclick="app.showJobFormats('${job.id}')">
                                <i class="bi bi-file-earmark-music"></i>
                            </button>
                            <a href="${API_BASE}/jobs/${job.id}/download?format=wav" 
                               class="btn btn-outline-info" target="_blank">
                                <i class="bi bi-download"></i> WAV
                            </a>
                        ` : ''}
                        <button class="btn btn-outline-danger" onclick="app.deleteJob('${job.id}')">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    },

    async showJobDetails(jobId) {
        const modal = new bootstrap.Modal(document.getElementById('modal-job-details'));
        const body = document.getElementById('modal-job-details-body');
        
        body.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
        modal.show();
        
        try {
            const job = await this.fetchJson(`${API_BASE}/jobs/${jobId}`);
            
            // Botões de ação disponíveis conforme status do job
            let actionButtons = '';
            if (job.status === 'completed') {
                actionButtons = `
                    <div class="d-flex gap-2 mb-3">
                        <button class="btn btn-success" onclick="app.showJobFormats('${jobId}')">
                            <i class="bi bi-download"></i> Baixar Áudio
                        </button>
                        <button class="btn btn-outline-danger" onclick="app.deleteJob('${jobId}'); bootstrap.Modal.getInstance(document.getElementById('modal-job-details')).hide();">
                            <i class="bi bi-trash"></i> Deletar Job
                        </button>
                    </div>
                `;
            } else if (job.status === 'failed') {
                actionButtons = `
                    <div class="alert alert-danger mb-3">
                        <i class="bi bi-exclamation-triangle"></i> 
                        <strong>Job falhou:</strong> ${job.error_message || 'Erro desconhecido'}
                    </div>
                    <button class="btn btn-outline-danger mb-3" onclick="app.deleteJob('${jobId}'); bootstrap.Modal.getInstance(document.getElementById('modal-job-details')).hide();">
                        <i class="bi bi-trash"></i> Deletar Job
                    </button>
                `;
            } else if (job.status === 'processing' || job.status === 'pending') {
                actionButtons = `
                    <div class="alert alert-info mb-3">
                        <i class="bi bi-hourglass-split"></i> 
                        <strong>Status:</strong> ${job.status}
                        ${job.progress ? ` - Progresso: ${(job.progress * 100).toFixed(1)}%` : ''}
                    </div>
                `;
            }
            
            body.innerHTML = `
                ${actionButtons}
                <h6>Detalhes do Job:</h6>
                <div class="json-display">${JSON.stringify(job, null, 2)}</div>
            `;
        } catch (error) {
            body.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async showJobFormats(jobId) {
        try {
            const formats = await this.fetchJson(`${API_BASE}/jobs/${jobId}/formats`);
            
            let html = '<h6>Formatos disponíveis:</h6><div class="list-group">';
            
            /**
             * INT-04 FIX: Replace direct links with JavaScript buttons for error handling
             */
            if (Array.isArray(formats)) {
                formats.forEach(format => {
                    html += `
                        <button onclick="app.downloadJobFile('${jobId}', '${format}')" 
                           class="list-group-item list-group-item-action btn-download-format">
                            <i class="bi bi-file-earmark-music"></i> ${format.toUpperCase()}
                            <i class="bi bi-download float-end"></i>
                        </button>
                    `;
                });
            } else {
                // Se retornar objeto
                Object.keys(formats).forEach(key => {
                    html += `
                        <button onclick="app.downloadJobFile('${jobId}', '${key}')" 
                           class="list-group-item list-group-item-action btn-download-format">
                            <i class="bi bi-file-earmark-music"></i> ${key.toUpperCase()}
                            <i class="bi bi-download float-end"></i>
                        </button>
                    `;
                });
            }
            
            html += '</div>';
            
            this.showModal('Formatos de Download', html);
        } catch (error) {
            this.showToast('Erro', `Falha ao carregar formatos: ${error.message}`, 'error');
        }
    },

    /**
     * INT-04 FIX: Download job file with proper error handling
     * Replaces direct window.open() with fetch + blob download
     * 
     * @param {string} jobId - Job identifier
     * @param {string} format - File format (e.g., 'wav', 'mp3')
     */
    async downloadJobFile(jobId, format) {
        try {
            const response = await fetch(`${API_BASE}/jobs/${jobId}/download?format=${format}`);
            
            if (!response.ok) {
                // Handle HTTP errors with user-friendly messages
                if (response.status === 404) {
                    throw new Error('Job ou arquivo não encontrado');
                } else if (response.status === 500) {
                    throw new Error('Erro no servidor. Tente novamente.');
                } else {
                    const errorText = await response.text();
                    throw new Error(errorText || `Erro HTTP ${response.status}`);
                }
            }
            
            // Download via blob to ensure error handling
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `job_${jobId}.${format}`;
            document.body.appendChild(a); // Required for Firefox
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showToast('Sucesso', `Download de ${format.toUpperCase()} iniciado`, 'success');
        } catch (error) {
            this.showToast('Erro', `Falha no download: ${error.message}`, 'error');
        }
    },

    async searchJobById() {
        const jobId = document.getElementById('search-job-id').value.trim();
        if (!jobId) {
            this.showToast('Atenção', 'Digite um Job ID', 'warning');
            return;
        }
        
        await this.searchAndMonitorJob(jobId);
    },

    /**
     * Busca um job e monitora até completar/falhar
     */
    async searchAndMonitorJob(jobId) {
        // Limpar intervalo anterior se existir
        if (this.state.currentJobMonitorInterval) {
            clearInterval(this.state.currentJobMonitorInterval);
            this.state.currentJobMonitorInterval = null;
        }

        const renderJob = async () => {
            try {
                const job = await this.fetchJson(`${API_BASE}/jobs/${jobId}`);
                
                // Renderizar apenas este job na tabela
                const container = document.getElementById('jobs-container');
                container.innerHTML = `
                    <div class="table-responsive">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="mb-0">Resultado da Busca</h5>
                            <button class="btn btn-sm btn-outline-secondary" onclick="app.loadJobs()">
                                <i class="bi bi-arrow-clockwise"></i> Mostrar Todos
                            </button>
                        </div>
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Job ID</th>
                                    <th>Status</th>
                                    <th>Engine</th>
                                    <th>Mode</th>
                                    <th>Data</th>
                                    <th>Ações</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${this.renderJobRow(job)}
                            </tbody>
                        </table>
                    </div>
                `;
                
                // Se job está em processamento, continuar monitorando
                if (job.status === 'processing' || job.status === 'pending') {
                    if (!this.state.currentJobMonitorInterval) {
                        this.state.currentJobMonitorInterval = setInterval(() => renderJob(), 3000);
                    }
                } else {
                    // Job completou ou falhou, parar monitoramento
                    if (this.state.currentJobMonitorInterval) {
                        clearInterval(this.state.currentJobMonitorInterval);
                        this.state.currentJobMonitorInterval = null;
                    }
                    
                    if (job.status === 'completed') {
                        this.showToast('Sucesso', `Job ${jobId} completado!`, 'success');
                    } else if (job.status === 'failed') {
                        this.showToast('Erro', `Job ${jobId} falhou`, 'error');
                    }
                }
                
                return job;
            } catch (error) {
                // Job não encontrado, parar monitoramento
                if (this.state.currentJobMonitorInterval) {
                    clearInterval(this.state.currentJobMonitorInterval);
                    this.state.currentJobMonitorInterval = null;
                }
                this.showToast('Erro', `Job não encontrado: ${error.message}`, 'error');
                throw error;
            }
        };

        // Renderizar imediatamente
        await renderJob();
    },

    async deleteJob(jobId) {
        if (!confirm(`Tem certeza que deseja excluir o job ${jobId}?`)) return;
        
        try {
            await this.fetchJson(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' });
            this.showToast('Sucesso', 'Job excluído com sucesso', 'success');
            this.loadJobs();
        } catch (error) {
            this.showToast('Erro', `Falha ao excluir job: ${error.message}`, 'error');
        }
    },

    // ==================== CREATE JOB ====================
    async createJob() {
        const btn = document.getElementById('btn-create-job');
        btn.disabled = true;
        btn.classList.add('btn-loading');
        
        try {
            // Validação de idioma de origem
            const sourceLanguage = document.getElementById('job-source-language').value;
            if (!sourceLanguage) {
                throw new Error('Selecione o idioma de origem');
            }
            
            const formData = new URLSearchParams();
            
            // Required fields
            formData.append('text', document.getElementById('job-text').value);
            formData.append('source_language', sourceLanguage);
            formData.append('mode', document.getElementById('job-mode').value);
            
            // Voice preset or voice ID
            const mode = document.getElementById('job-mode').value;
            if (mode === 'dubbing') {
                formData.append('voice_preset', document.getElementById('job-voice-preset').value);
            } else if (mode === 'dubbing_with_clone') {
                const voiceId = document.getElementById('job-voice-id').value;
                if (!voiceId) {
                    throw new Error('Selecione uma voz clonada');
                }
                formData.append('voice_id', voiceId);
            }
            
            // Optional fields
            const targetLang = document.getElementById('job-target-language').value;
            // Apenas envia target_language se for diferente de vazio (null/undefined = usar source_language)
            if (targetLang) formData.append('target_language', targetLang);
            
            formData.append('tts_engine', document.getElementById('job-tts-engine').value);
            
            const qualityProfileId = document.getElementById('job-quality-profile').value;
            if (qualityProfileId) formData.append('quality_profile_id', qualityProfileId);
            
            const refText = document.getElementById('job-ref-text').value;
            if (refText) formData.append('ref_text', refText);
            
            // RVC params
            const enableRvc = document.getElementById('job-enable-rvc').checked;
            formData.append('enable_rvc', enableRvc);
            
            if (enableRvc) {
                const rvcModelId = document.getElementById('job-rvc-model-id').value;
                const rvcModelSelect = document.getElementById('job-rvc-model-id');
                
                /**
                 * INT-03 FIX: Enhanced RVC validation with visual feedback
                 */
                if (!rvcModelId) {
                    // Add visual feedback (red border)
                    rvcModelSelect.classList.add('is-invalid');
                    
                    // Show error message
                    throw new Error('Selecione um modelo RVC quando RVC estiver ativado');
                }
                
                // Remove invalid state if exists (user fixed it)
                rvcModelSelect.classList.remove('is-invalid');
                
                formData.append('rvc_model_id', rvcModelId);
                formData.append('rvc_pitch', document.getElementById('job-rvc-pitch').value);
                formData.append('rvc_index_rate', document.getElementById('job-rvc-index-rate').value);
                formData.append('rvc_filter_radius', document.getElementById('job-rvc-filter-radius').value);
                formData.append('rvc_rms_mix_rate', document.getElementById('job-rvc-rms-mix-rate').value);
                formData.append('rvc_protect', document.getElementById('job-rvc-protect').value);
                formData.append('rvc_f0_method', document.getElementById('job-rvc-f0-method').value);
            }
            
            const job = await this.fetchJson(`${API_BASE}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData.toString()
            });
            
            this.showToast('Sucesso', `Job criado com sucesso! ID: ${job.id}`, 'success');
            
            // Reset form
            document.getElementById('form-create-job').reset();
            document.getElementById('text-counter').textContent = '0';
            
            // Recarregar idiomas após reset
            this.loadLanguages();
            
            // Navigate to jobs
            this.navigate('jobs');
            
            // Preencher barra de busca com Job ID
            const searchInput = document.getElementById('search-job-id');
            if (searchInput) {
                searchInput.value = job.id;
            }
            
            // Buscar e monitorar o job criado
            await this.searchAndMonitorJob(job.id);
            
        } catch (error) {
            this.showToast('Erro', `Falha ao criar job: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
        }
    },

    toggleVoiceMode(mode) {
        const presetContainer = document.getElementById('container-voice-preset');
        const voiceIdContainer = document.getElementById('container-voice-id');
        
        if (mode === 'dubbing') {
            presetContainer.style.display = 'block';
            voiceIdContainer.style.display = 'none';
        } else if (mode === 'dubbing_with_clone') {
            presetContainer.style.display = 'none';
            voiceIdContainer.style.display = 'block';
        }
    },
    
    /**
     * BUG-02 FIX: Atualiza visibilidade e label do campo ref_text baseado em engine e mode
     */
    updateRefTextVisibility() {
        const engine = document.getElementById('job-tts-engine')?.value || 'xtts';
        const mode = document.getElementById('job-mode')?.value || 'dubbing';
        const refTextContainer = document.getElementById('job-ref-text')?.parentElement;
        const refTextLabel = refTextContainer?.querySelector('label');
        
        if (!refTextLabel) return;
        
        // F5-TTS + dubbing_with_clone: ref_text é importante
        if (engine === 'f5tts' && mode === 'dubbing_with_clone') {
            refTextLabel.innerHTML = `
                <i class="bi bi-file-text"></i> Texto de Referência (F5-TTS) 
                <span class="badge bg-warning text-dark">Recomendado</span>
                <small class="text-muted">(transcrição do áudio de referência)</small>
            `;
            refTextContainer.style.display = 'block';
        } 
        // F5-TTS + dubbing: ref_text não faz sentido
        else if (engine === 'f5tts' && mode === 'dubbing') {
            refTextLabel.innerHTML = `
                <i class="bi bi-file-text"></i> Texto de Referência
                <small class="text-muted">(não aplicável para modo dubbing)</small>
            `;
            refTextContainer.style.display = 'none';
        }
        // XTTS: ref_text opcional
        else {
            refTextLabel.innerHTML = `
                <i class="bi bi-file-text"></i> Texto de Referência
                <small class="text-muted">(opcional, auto-transcrito se vazio)</small>
            `;
            refTextContainer.style.display = 'block';
        }
    },

    // ==================== LANGUAGES & PRESETS ====================
    async loadLanguages() {
        const selects = [
            { id: 'job-source-language', label: 'idiomas de origem' },
            { id: 'job-target-language', label: 'idiomas de destino' },
            { id: 'clone-language', label: 'idiomas' }
        ];
        
        try {
            const response = await this.fetchJson(`${API_BASE}/languages`);
            // QA FIX: API retorna {languages: [...], total: N, examples: {...}}
            const languages = Array.isArray(response) ? response : (response.languages || []);
            
            console.log('🔍 DEBUG loadLanguages:', {
                responseType: typeof response,
                isArray: Array.isArray(response),
                languagesType: typeof languages,
                languagesIsArray: Array.isArray(languages),
                languagesLength: languages?.length,
                firstItems: languages?.slice?.(0, 3)
            });
            
            this.state.languages = languages;
            
            // Populate source language select
            const sourceSelect = document.getElementById('job-source-language');
            if (sourceSelect) {
                console.log('🔍 BEFORE populate - source select options:', sourceSelect.options.length, Array.from(sourceSelect.options).map(o => o.textContent));
                console.log('🔍 Populating source select with', languages.length, 'languages');
                this.populateLanguageSelect(sourceSelect, languages, { includeSameAsSource: false });
                console.log('✅ AFTER populate - source select options:', sourceSelect.options.length, Array.from(sourceSelect.options).map(o => o.textContent).slice(0, 5));
            }
            
            // Populate target language select
            const targetSelect = document.getElementById('job-target-language');
            if (targetSelect) {
                this.populateLanguageSelect(targetSelect, languages, { includeSameAsSource: true });
            }
            
            // Populate clone language select
            const cloneSelect = document.getElementById('clone-language');
            if (cloneSelect) {
                this.populateLanguageSelect(cloneSelect, languages, { includeSameAsSource: false });
            }
            
            console.log('✅ Idiomas carregados:', languages);
        } catch (error) {
            console.error('❌ Erro ao carregar idiomas:', error);
            
            // BUG-04 FIX: Atualizar selects com mensagem de erro e botão retry
            selects.forEach(({ id, label }) => {
                const select = document.getElementById(id);
                if (select) {
                    select.innerHTML = `<option value="" style="color: red;">❌ Erro ao carregar ${label} - Clique para tentar novamente</option>`;
                    select.style.cursor = 'pointer';
                    
                    const retryHandler = () => {
                        select.innerHTML = '<option value="">⏳ Carregando...</option>';
                        select.style.cursor = 'default';
                        select.removeEventListener('click', retryHandler);
                        this.loadLanguages();
                    };
                    
                    select.addEventListener('click', retryHandler, { once: true });
                }
            });
            
            this.showToast('Erro', 'Falha ao carregar idiomas. Clique no dropdown para tentar novamente.', 'error');
        }
    },

    /**
     * Popula select de idiomas com opções individuais
     */
    populateLanguageSelect(selectElement, languages, options = {}) {
        const { includeSameAsSource = false } = options;
        
        console.log('🔍 populateLanguageSelect called:', {
            selectId: selectElement?.id,
            languagesType: typeof languages,
            isArray: Array.isArray(languages),
            length: languages?.length,
            firstItem: languages?.[0]
        });
        
        // Mapeamento de códigos de idioma para nomes amigáveis
        const languageNames = {
            'en': 'English',
            'en-US': 'English (United States)',
            'en-GB': 'English (United Kingdom)',
            'en-AU': 'English (Australia)',
            'pt': 'Portuguese (Portugal)',
            'pt-BR': 'Portuguese (Brazil)',
            'es': 'Spanish (Spain)',
            'es-ES': 'Spanish (Spain)',
            'es-MX': 'Spanish (Mexico)',
            'es-AR': 'Spanish (Argentina)',
            'fr': 'French (France)',
            'fr-FR': 'French (France)',
            'fr-CA': 'French (Canada)',
            'de': 'German (Germany)',
            'de-DE': 'German (Germany)',
            'it': 'Italian (Italy)',
            'it-IT': 'Italian (Italy)',
            'ja': 'Japanese',
            'zh': 'Chinese',
            'zh-CN': 'Chinese (Simplified)',
            'ko': 'Korean',
            'ru': 'Russian',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'nl': 'Dutch',
            'pl': 'Polish',
            'tr': 'Turkish',
            'hu': 'Hungarian'
        };
        
        // Limpa todas as options existentes
        selectElement.innerHTML = '';
        
        // Adiciona option placeholder
        const placeholder = document.createElement('option');
        placeholder.value = '';
        
        if (includeSameAsSource) {
            placeholder.textContent = 'Mesmo que idioma de origem (padrão)';
        } else {
            placeholder.textContent = selectElement.id.includes('clone') 
                ? 'Selecione o idioma da voz' 
                : 'Selecione o idioma de origem';
        }
        
        selectElement.appendChild(placeholder);
        
        // Adiciona cada idioma como option separada
        if (Array.isArray(languages)) {
            console.log(`✅ Languages is array with ${languages.length} items, creating options...`);
            languages.forEach((langCode, index) => {
                try {
                    const option = document.createElement('option');
                    option.value = langCode;
                    // Usa nome amigável se disponível, senão usa o código
                    option.textContent = languageNames[langCode] || langCode;
                    selectElement.appendChild(option);
                    
                    if (index < 3) {
                        console.log(`  [${index}] Created option:`, { value: langCode, text: option.textContent });
                    }
                } catch (err) {
                    console.error(`❌ Error creating option for ${langCode}:`, err);
                }
            });
            console.log(`✅ Finished adding options, total: ${selectElement.options.length}`);
        } else if (typeof languages === 'object' && languages !== null) {
            console.log('📝 Languages is object, using Object.entries...');
            Object.entries(languages).forEach(([code, name]) => {
                const option = document.createElement('option');
                option.value = code;
                option.textContent = name || languageNames[code] || code;
                selectElement.appendChild(option);
            });
        } else {
            console.error('❌ Languages is neither array nor object!', typeof languages, languages);
        }
    },

    async loadPresets() {
        try {
            const response = await this.fetchJson(`${API_BASE}/presets`);
            // QA FIX: API retorna {presets: {...}}
            const presets = response.presets || response;
            this.state.presets = presets;
            
            const select = document.getElementById('job-voice-preset');
            if (select) {
                let html = '';
                
                if (Array.isArray(presets)) {
                    html = presets.map(preset => `<option value="${preset}">${preset}</option>`).join('');
                } else {
                    html = Object.keys(presets).map(key => `<option value="${key}">${presets[key].description || key}</option>`).join('');
                }
                
                select.innerHTML = html;
            }
            
            console.log('✅ Presets carregados:', presets);
        } catch (error) {
            console.error('❌ Erro ao carregar presets:', error);
            
            // BUG-04 FIX: Feedback com retry
            const select = document.getElementById('job-voice-preset');
            if (select) {
                select.innerHTML = '<option value="" style="color: red;">❌ Erro ao carregar presets - Clique para tentar novamente</option>';
                select.style.cursor = 'pointer';
                
                const retryHandler = () => {
                    select.innerHTML = '<option value="">⏳ Carregando...</option>';
                    select.style.cursor = 'default';
                    select.removeEventListener('click', retryHandler);
                    this.loadPresets();
                };
                
                select.addEventListener('click', retryHandler, { once: true });
            }
            
            this.showToast('Erro', 'Falha ao carregar presets de voz. Clique no dropdown para tentar novamente.', 'error');
        }
    },

    // ==================== VOICES ====================
    async loadVoices() {
        const container = document.getElementById('voices-list-container');
        const selectJob = document.getElementById('job-voice-id');
        
        try {
            if (container) {
                container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Carregando...</p></div>';
            }
            
            const data = await this.fetchJson(`${API_BASE}/voices?limit=100`);
            this.state.voices = data.voices || [];
            
            // Populate select (job form)
            if (selectJob) {
                selectJob.innerHTML = this.state.voices.length > 0
                    ? this.state.voices.map(v => `<option value="${v.id}">${v.name} (${v.language})</option>`).join('')
                    : '<option value="">Nenhuma voz disponível</option>';
            }
            
            // Render list
            if (container) {
                if (this.state.voices.length > 0) {
                    container.innerHTML = `
                        <p class="text-muted">Total: ${data.total} vozes</p>
                        <div class="row">
                            ${this.state.voices.map(voice => this.renderVoiceCard(voice)).join('')}
                        </div>
                    `;
                } else {
                    container.innerHTML = this.renderEmptyState('Nenhuma voz clonada', 'Clone uma nova voz usando o formulário acima');
                }
            }
        } catch (error) {
            if (container) {
                container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
            }
        }
    },

    renderVoiceCard(voice) {
        return `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="voice-card">
                    <div class="voice-card-header">
                        <h5 class="voice-card-title">${voice.name}</h5>
                        <span class="badge bg-primary">${voice.engine || 'xtts'}</span>
                    </div>
                    <div class="voice-card-meta">
                        <div><i class="bi bi-translate"></i> ${voice.language}</div>
                        <div><i class="bi bi-calendar"></i> ${new Date(voice.created_at).toLocaleDateString('pt-BR')}</div>
                        ${voice.duration ? `<div><i class="bi bi-clock"></i> ${voice.duration.toFixed(1)}s</div>` : ''}
                        ${voice.usage_count ? `<div><i class="bi bi-graph-up"></i> Usado ${voice.usage_count}x</div>` : ''}
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="app.showVoiceDetails('${voice.id}')">
                            <i class="bi bi-info-circle"></i> Detalhes
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="app.deleteVoice('${voice.id}')">
                            <i class="bi bi-trash"></i> Excluir
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    async showVoiceDetails(voiceId) {
        const modal = new bootstrap.Modal(document.getElementById('modal-voice-details'));
        const body = document.getElementById('modal-voice-details-body');
        
        body.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
        modal.show();
        
        try {
            const voice = await this.fetchJson(`${API_BASE}/voices/${voiceId}`);
            body.innerHTML = `<div class="json-display">${JSON.stringify(voice, null, 2)}</div>`;
        } catch (error) {
            body.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async deleteVoice(voiceId) {
        if (!confirm('Tem certeza que deseja excluir esta voz?')) return;
        
        try {
            await this.fetchJson(`${API_BASE}/voices/${voiceId}`, { method: 'DELETE' });
            this.showToast('Sucesso', 'Voz excluída com sucesso', 'success');
            this.loadVoices();
        } catch (error) {
            this.showToast('Erro', `Falha ao excluir voz: ${error.message}`, 'error');
        }
    },

    // ==================== CLONE VOICE ====================
    async cloneVoice() {
        const btn = document.getElementById('btn-clone-voice');
        btn.disabled = true;
        btn.classList.add('btn-loading');
        
        try {
            const formData = new FormData();
            
            const file = document.getElementById('clone-audio-file').files[0];
            if (!file) {
                throw new Error('Selecione um arquivo de áudio');
            }
            
            // BUG-05 FIX: Validar extensão
            const allowedExtensions = ['.wav', '.mp3', '.flac', '.m4a', '.ogg'];
            const fileName = file.name.toLowerCase();
            const isValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
            
            if (!isValidExtension) {
                throw new Error(`Formato inválido. Use: ${allowedExtensions.join(', ')}`);
            }
            
            // BUG-05 FIX: Validar tamanho (50MB)
            const maxSize = 50 * 1024 * 1024;
            if (file.size > maxSize) {
                const fileSizeMB = (file.size / 1024 / 1024).toFixed(2);
                throw new Error(`Arquivo muito grande (${fileSizeMB}MB). Máximo permitido: 50MB`);
            }
            
            formData.append('file', file);
            formData.append('name', document.getElementById('clone-voice-name').value);
            formData.append('language', document.getElementById('clone-language').value);
            formData.append('tts_engine', document.getElementById('clone-tts-engine').value);
            
            const description = document.getElementById('clone-description').value;
            if (description) formData.append('description', description);
            
            const refText = document.getElementById('clone-ref-text').value;
            if (refText) formData.append('ref_text', refText);
            
            const response = await fetch(`${API_BASE}/voices/clone`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            const jobId = result.job_id;
            
            this.showToast('Sucesso', `Clonagem iniciada! Job ID: ${jobId}`, 'success');
            
            // Reset form
            document.getElementById('form-clone-voice').reset();
            
            // Add to cloning jobs tracking
            this.trackCloningJob(jobId);
            
        } catch (error) {
            this.showToast('Erro', `Falha ao iniciar clonagem: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
        }
    },

    trackCloningJob(jobId) {
        this.state.cloningJobs[jobId] = { status: 'processing', startTime: Date.now() };
        this.renderCloningJobs();
        this.pollCloningJob(jobId);
    },

    renderCloningJobs() {
        const card = document.getElementById('cloning-jobs-card');
        const list = document.getElementById('cloning-jobs-list');
        
        const jobs = Object.entries(this.state.cloningJobs);
        
        if (jobs.length === 0) {
            card.style.display = 'none';
            return;
        }
        
        card.style.display = 'block';
        list.innerHTML = jobs.map(([jobId, data]) => `
            <div class="cloning-job-card ${data.status}" id="cloning-job-${jobId}">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Job: ${jobId.substring(0, 12)}...</strong>
                        <br><small class="text-muted">Status: ${data.status}</small>
                    </div>
                    <button class="btn btn-sm btn-outline-primary" onclick="app.showJobDetails('${jobId}')">
                        <i class="bi bi-arrow-clockwise"></i> Atualizar
                    </button>
                </div>
            </div>
        `).join('');
    },

    async pollCloningJob(jobId) {
        const maxAttempts = 60; // 5 minutos (5s * 60)
        let attempts = 0;
        
        const interval = setInterval(async () => {
            attempts++;
            
            try {
                const job = await this.fetchJson(`${API_BASE}/jobs/${jobId}`);
                
                if (job.status === 'completed') {
                    clearInterval(interval);
                    this.state.cloningJobs[jobId].status = 'completed';
                    this.renderCloningJobs();
                    this.showToast('Sucesso', 'Clonagem concluída!', 'success');
                    this.loadVoices(); // Reload voices list
                    
                    // Remove from tracking after 10s
                    setTimeout(() => {
                        delete this.state.cloningJobs[jobId];
                        this.renderCloningJobs();
                    }, 10000);
                    
                } else if (job.status === 'failed') {
                    clearInterval(interval);
                    this.state.cloningJobs[jobId].status = 'failed';
                    this.renderCloningJobs();
                    this.showToast('Erro', `Clonagem falhou: ${job.error_message || 'Erro desconhecido'}`, 'error');
                    
                } else if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    delete this.state.cloningJobs[jobId];
                    this.renderCloningJobs();
                    this.showToast('Timeout', 'Tempo limite de polling atingido', 'warning');
                }
            } catch (error) {
                console.error('Erro no polling:', error);
            }
        }, 5000);
    },

    // ==================== RVC MODELS ====================
    async loadRvcModels() {
        const container = document.getElementById('rvc-models-list-container');
        const selectJob = document.getElementById('job-rvc-model-id');
        const sortBy = document.getElementById('rvc-sort-by')?.value || 'created_at';
        
        try {
            if (container) {
                container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Carregando...</p></div>';
            }
            
            const data = await this.fetchJson(`${API_BASE}/rvc-models?sort_by=${sortBy}`);
            this.state.rvcModels = data.models || [];
            
            // Populate select (job form)
            if (selectJob) {
                selectJob.innerHTML = '<option value="">Selecione um modelo</option>' +
                    this.state.rvcModels.map(m => `<option value="${m.id}">${m.name} (${m.file_size_mb.toFixed(1)} MB)</option>`).join('');
            }
            
            // Render list
            if (container) {
                if (this.state.rvcModels.length > 0) {
                    container.innerHTML = `
                        <p class="text-muted">Total: ${data.total} modelos</p>
                        <div class="row">
                            ${this.state.rvcModels.map(model => this.renderRvcModelCard(model)).join('')}
                        </div>
                    `;
                } else {
                    container.innerHTML = this.renderEmptyState('Nenhum modelo RVC', 'Faça upload de um novo modelo usando o formulário acima');
                }
            }
        } catch (error) {
            if (container) {
                container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
            }
        }
    },

    renderRvcModelCard(model) {
        return `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="model-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h5>${model.name}</h5>
                            <p class="text-muted mb-1">${model.description || 'Sem descrição'}</p>
                        </div>
                    </div>
                    <div class="mt-2">
                        <small class="d-block"><i class="bi bi-hdd"></i> ${model.file_size_mb.toFixed(2)} MB</small>
                        <small class="d-block"><i class="bi bi-calendar"></i> ${new Date(model.created_at).toLocaleDateString('pt-BR')}</small>
                        ${model.index_file ? '<small class="d-block"><i class="bi bi-check-circle text-success"></i> Com índice</small>' : ''}
                    </div>
                    <div class="mt-3">
                        <button class="btn btn-sm btn-outline-primary" onclick="app.showRvcModelDetails('${model.id}')">
                            <i class="bi bi-info-circle"></i> Detalhes
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="app.deleteRvcModel('${model.id}')">
                            <i class="bi bi-trash"></i> Excluir
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    async showRvcModelDetails(modelId) {
        const modal = new bootstrap.Modal(document.getElementById('modal-rvc-details'));
        const body = document.getElementById('modal-rvc-details-body');
        
        body.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
        modal.show();
        
        try {
            const model = await this.fetchJson(`${API_BASE}/rvc-models/${modelId}`);
            body.innerHTML = `<div class="json-display">${JSON.stringify(model, null, 2)}</div>`;
        } catch (error) {
            body.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async deleteRvcModel(modelId) {
        if (!confirm('Tem certeza que deseja excluir este modelo?')) return;
        
        try {
            await this.fetchJson(`${API_BASE}/rvc-models/${modelId}`, { method: 'DELETE' });
            this.showToast('Sucesso', 'Modelo excluído com sucesso', 'success');
            this.loadRvcModels();
            this.loadRvcStats();
        } catch (error) {
            this.showToast('Erro', `Falha ao excluir modelo: ${error.message}`, 'error');
        }
    },

    async uploadRvcModel() {
        const btn = document.getElementById('btn-upload-rvc');
        btn.disabled = true;
        btn.classList.add('btn-loading');
        
        try {
            const formData = new FormData();
            
            const name = document.getElementById('rvc-model-name').value;
            const pthFile = document.getElementById('rvc-pth-file').files[0];
            
            if (!name || !pthFile) {
                throw new Error('Nome e arquivo .pth são obrigatórios');
            }
            
            formData.append('name', name);
            formData.append('pth_file', pthFile);
            
            const description = document.getElementById('rvc-model-description').value;
            if (description) formData.append('description', description);
            
            const indexFile = document.getElementById('rvc-index-file').files[0];
            if (indexFile) formData.append('index_file', indexFile);
            
            const response = await fetch(`${API_BASE}/rvc-models`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            
            const model = await response.json();
            
            this.showToast('Sucesso', `Modelo "${model.name}" enviado com sucesso!`, 'success');
            
            // Reset form
            document.getElementById('form-upload-rvc').reset();
            
            // Reload
            this.loadRvcModels();
            this.loadRvcStats();
            
        } catch (error) {
            this.showToast('Erro', `Falha ao enviar modelo: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
        }
    },

    async loadRvcStats() {
        const container = document.getElementById('rvc-stats-container');
        if (!container) return;
        
        try {
            const stats = await this.fetchJson(`${API_BASE}/rvc-models/stats`);
            container.innerHTML = this.renderStatsHtml(stats);
        } catch (error) {
            container.innerHTML = `<p class="text-danger">Erro: ${error.message}</p>`;
        }
    },

    // ==================== QUALITY PROFILES ====================
    async loadQualityProfiles() {
        const xttsContainer = document.getElementById('xtts-profiles-container');
        const f5ttsContainer = document.getElementById('f5tts-profiles-container');
        
        try {
            if (xttsContainer) xttsContainer.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
            if (f5ttsContainer) f5ttsContainer.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
            
            const data = await this.fetchJson(`${API_BASE}/quality-profiles`);
            this.state.qualityProfiles = data;
            
            if (xttsContainer) {
                xttsContainer.innerHTML = data.xtts_profiles?.length > 0
                    ? data.xtts_profiles.map(p => this.renderProfileItem(p, 'xtts')).join('')
                    : this.renderEmptyState('Nenhum perfil XTTS');
            }
            
            if (f5ttsContainer) {
                f5ttsContainer.innerHTML = data.f5tts_profiles?.length > 0
                    ? data.f5tts_profiles.map(p => this.renderProfileItem(p, 'f5tts')).join('')
                    : this.renderEmptyState('Nenhum perfil F5-TTS');
            }
            
            // Also update job form select
            this.loadQualityProfilesForEngine(document.getElementById('job-tts-engine')?.value || 'xtts');
            
        } catch (error) {
            if (xttsContainer) xttsContainer.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
            if (f5ttsContainer) f5ttsContainer.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    loadQualityProfilesForEngine(engine) {
        const select = document.getElementById('job-quality-profile');
        if (!select) return;
        
        // BUG-01 FIX: Filtrar perfis apenas do engine selecionado
        const profiles = engine === 'xtts' 
            ? this.state.qualityProfiles.xtts_profiles 
            : this.state.qualityProfiles.f5tts_profiles;
        
        let html = `<option value="">Usar padrão do ${engine.toUpperCase()}</option>`;
        if (profiles && profiles.length > 0) {
            html += profiles.map(p => `<option value="${p.id}">${p.name}${p.is_default ? ' (padrão)' : ''}</option>`).join('');
        }
        
        select.innerHTML = html;
    },

    renderProfileItem(profile, engine) {
        const defaultClass = profile.is_default ? 'default-profile' : '';
        
        return `
            <div class="profile-item ${defaultClass}">
                ${profile.is_default ? '<div class="default-badge">PADRÃO</div>' : ''}
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h5>${profile.name}</h5>
                        <p class="text-muted mb-2">${profile.description || 'Sem descrição'}</p>
                        <small class="text-muted">ID: ${profile.id}</small>
                    </div>
                    <div class="btn-group">
                        ${!profile.is_default ? `
                            <button class="btn btn-sm btn-outline-success" 
                                onclick="app.setDefaultProfile('${engine}', '${profile.id}')">
                                <i class="bi bi-star"></i> Definir padrão
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-outline-info" 
                            onclick="app.duplicateQualityProfile('${engine}', '${profile.id}', '${profile.name}')" 
                            title="Duplicar este perfil">
                            <i class="bi bi-files"></i> Duplicar
                        </button>
                        <button class="btn btn-sm btn-outline-primary" 
                            onclick="app.editQualityProfile('${engine}', '${profile.id}')">
                            <i class="bi bi-pencil"></i>
                        </button>
                        ${!profile.is_default ? `
                            <button class="btn btn-sm btn-outline-danger" 
                                onclick="app.deleteQualityProfile('${engine}', '${profile.id}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Toggle engine-specific parameters in Quality Profile form
     */
    toggleQualityProfileEngine(engine) {
        const xttsParams = document.getElementById('qp-xtts-params');
        const f5ttsParams = document.getElementById('qp-f5tts-params');
        
        if (engine === 'xtts') {
            xttsParams.style.display = 'block';
            f5ttsParams.style.display = 'none';
        } else if (engine === 'f5tts') {
            xttsParams.style.display = 'none';
            f5ttsParams.style.display = 'block';
        }
    },

    /**
     * Coleta parâmetros XTTS do formulário
     */
    getXttsParameters() {
        return {
            temperature: parseFloat(document.getElementById('qp-xtts-temperature').value),
            speed: parseFloat(document.getElementById('qp-xtts-speed').value),
            repetition_penalty: parseFloat(document.getElementById('qp-xtts-repetition-penalty').value),
            top_p: parseFloat(document.getElementById('qp-xtts-top-p').value),
            top_k: parseInt(document.getElementById('qp-xtts-top-k').value),
            length_penalty: parseFloat(document.getElementById('qp-xtts-length-penalty').value),
            enable_text_splitting: document.getElementById('qp-xtts-enable-text-splitting').checked
        };
    },

    /**
     * Coleta parâmetros F5-TTS do formulário
     */
    getF5ttsParameters() {
        return {
            nfe_step: parseInt(document.getElementById('qp-f5tts-nfe-step').value),
            cfg_scale: parseFloat(document.getElementById('qp-f5tts-cfg-scale').value),
            speed: parseFloat(document.getElementById('qp-f5tts-speed').value),
            sway_sampling_coef: parseFloat(document.getElementById('qp-f5tts-sway-sampling-coef').value),
            denoise_audio: document.getElementById('qp-f5tts-denoise-audio').checked,
            noise_reduction_strength: parseFloat(document.getElementById('qp-f5tts-noise-reduction-strength').value),
            enhance_prosody: document.getElementById('qp-f5tts-enhance-prosody').checked,
            prosody_strength: parseFloat(document.getElementById('qp-f5tts-prosody-strength').value),
            apply_normalization: document.getElementById('qp-f5tts-apply-normalization').checked,
            target_loudness: parseFloat(document.getElementById('qp-f5tts-target-loudness').value),
            apply_declipping: document.getElementById('qp-f5tts-apply-declipping').checked,
            apply_deessing: document.getElementById('qp-f5tts-apply-deessing').checked,
            deessing_frequency: parseInt(document.getElementById('qp-f5tts-deessing-frequency').value),
            add_breathing: document.getElementById('qp-f5tts-add-breathing').checked,
            breathing_strength: parseFloat(document.getElementById('qp-f5tts-breathing-strength').value),
            pause_optimization: document.getElementById('qp-f5tts-pause-optimization').checked
        };
    },

    async createQualityProfile() {
        const btn = document.querySelector('#form-create-quality-profile button[type="submit"]');
        btn.disabled = true;
        btn.classList.add('btn-loading');
        
        try {
            const name = document.getElementById('qp-name').value.trim();
            const engine = document.getElementById('qp-engine').value;
            const description = document.getElementById('qp-description').value.trim();
            const isDefault = document.getElementById('qp-is-default').checked;
            
            if (!name) {
                throw new Error('Nome do perfil é obrigatório');
            }
            
            // Coletar parâmetros baseado no engine
            let parameters;
            if (engine === 'xtts') {
                parameters = this.getXttsParameters();
            } else if (engine === 'f5tts') {
                parameters = this.getF5ttsParameters();
            }
            
            const payload = {
                name,
                engine,
                description: description || undefined,
                is_default: isDefault,
                parameters
            };
            
            const response = await this.fetchJson(`${API_BASE}/quality-profiles`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            this.showToast('Sucesso', `Perfil "${name}" criado com sucesso!`, 'success');
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('modal-create-profile')).hide();
            
            // Reset form
            document.getElementById('form-create-quality-profile').reset();
            this.toggleQualityProfileEngine('xtts'); // Volta para padrão
            
            // Reload
            this.loadQualityProfiles();
            
        } catch (error) {
            console.error('Erro ao criar perfil:', error);
            
            // Tratar erros 422 de validação
            if (error.detail && Array.isArray(error.detail)) {
                const errors = error.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                this.showToast('Erro de Validação', errors, 'error');
            } else {
                this.showToast('Erro', `Falha ao criar perfil: ${error.message}`, 'error');
            }
        } finally {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
        }
    },

    /**
     * BUG-03 FIX: Refatorado para usar formulário estruturado
     */
    async editQualityProfile(engine, profileId) {
        const modal = new bootstrap.Modal(document.getElementById('modal-edit-profile'));
        
        try {
            const profile = await this.fetchJson(`${API_BASE}/quality-profiles/${engine}/${profileId}`);
            
            // Campos comuns
            document.getElementById('edit-qp-engine').value = engine;
            document.getElementById('edit-qp-id').value = profileId;
            document.getElementById('edit-qp-name').value = profile.name;
            document.getElementById('edit-qp-engine-display').value = engine.toUpperCase();
            document.getElementById('edit-qp-description').value = profile.description || '';
            document.getElementById('edit-qp-is-default').checked = profile.is_default;
            
            // Toggle visibility dos params
            const xttsParams = document.getElementById('edit-qp-xtts-params');
            const f5ttsParams = document.getElementById('edit-qp-f5tts-params');
            
            if (engine === 'xtts') {
                xttsParams.style.display = 'block';
                f5ttsParams.style.display = 'none';
                
                // Preencher campos XTTS
                document.getElementById('edit-qp-xtts-temperature').value = profile.temperature || 0.75;
                document.getElementById('edit-qp-xtts-speed').value = profile.speed || 1.0;
                document.getElementById('edit-qp-xtts-repetition-penalty').value = profile.repetition_penalty || 1.5;
                document.getElementById('edit-qp-xtts-top-p').value = profile.top_p || 0.9;
                document.getElementById('edit-qp-xtts-top-k').value = profile.top_k || 60;
                document.getElementById('edit-qp-xtts-length-penalty').value = profile.length_penalty || 1.2;
                document.getElementById('edit-qp-xtts-enable-text-splitting').checked = profile.enable_text_splitting || false;
            } else if (engine === 'f5tts') {
                xttsParams.style.display = 'none';
                f5ttsParams.style.display = 'block';
                
                // Preencher campos F5-TTS
                document.getElementById('edit-qp-f5tts-nfe-step').value = profile.nfe_step || 32;
                document.getElementById('edit-qp-f5tts-cfg-scale').value = profile.cfg_scale || 2.0;
                document.getElementById('edit-qp-f5tts-speed').value = profile.speed || 1.0;
                document.getElementById('edit-qp-f5tts-sway-sampling-coef').value = profile.sway_sampling_coef || -1.0;
                document.getElementById('edit-qp-f5tts-denoise-audio').checked = profile.denoise_audio !== false;
                document.getElementById('edit-qp-f5tts-noise-reduction-strength').value = profile.noise_reduction_strength || 0.7;
                document.getElementById('edit-qp-f5tts-enhance-prosody').checked = profile.enhance_prosody !== false;
                document.getElementById('edit-qp-f5tts-prosody-strength').value = profile.prosody_strength || 0.8;
                document.getElementById('edit-qp-f5tts-apply-normalization').checked = profile.apply_normalization !== false;
                document.getElementById('edit-qp-f5tts-target-loudness').value = profile.target_loudness || -20;
                document.getElementById('edit-qp-f5tts-apply-declipping').checked = profile.apply_declipping !== false;
                document.getElementById('edit-qp-f5tts-apply-deessing').checked = profile.apply_deessing !== false;
                document.getElementById('edit-qp-f5tts-deessing-frequency').value = profile.deessing_frequency || 6000;
                document.getElementById('edit-qp-f5tts-add-breathing').checked = profile.add_breathing !== false;
                document.getElementById('edit-qp-f5tts-breathing-strength').value = profile.breathing_strength || 0.3;
                document.getElementById('edit-qp-f5tts-pause-optimization').checked = profile.pause_optimization !== false;
            }
            
            modal.show();
            
        } catch (error) {
            this.showToast('Erro', `Falha ao carregar perfil: ${error.message}`, 'error');
        }
    },

    /**
     * BUG-03 FIX: Agora usa getXttsParameters() / getF5ttsParameters()
     */
    async updateQualityProfile() {
        const btn = document.querySelector('#form-edit-quality-profile button[type="submit"]');
        btn.disabled = true;
        btn.classList.add('btn-loading');
        
        try {
            const engine = document.getElementById('edit-qp-engine').value;
            const profileId = document.getElementById('edit-qp-id').value;
            const name = document.getElementById('edit-qp-name').value.trim();
            const description = document.getElementById('edit-qp-description').value.trim();
            const isDefault = document.getElementById('edit-qp-is-default').checked;
            
            // Coletar parâmetros via funções estruturadas
            let parameters;
            if (engine === 'xtts') {
                parameters = this.getEditXttsParameters();
            } else if (engine === 'f5tts') {
                parameters = this.getEditF5ttsParameters();
            }
            
            const payload = {
                name: name || undefined,
                description: description || undefined,
                is_default: isDefault,
                parameters
            };
            
            await this.fetchJson(`${API_BASE}/quality-profiles/${engine}/${profileId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            this.showToast('Sucesso', `Perfil "${name || profileId}" atualizado com sucesso!`, 'success');
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('modal-edit-profile')).hide();
            
            // Reload
            this.loadQualityProfiles();
            
        } catch (error) {
            console.error('Erro ao atualizar perfil:', error);
            
            // Tratar erros 422 de validação
            if (error.detail && Array.isArray(error.detail)) {
                const errors = error.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                this.showToast('Erro de Validação', errors, 'error');
            } else {
                this.showToast('Erro', `Falha ao atualizar perfil: ${error.message}`, 'error');
            }
        } finally {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
        }
    },
    
    /**
     * BUG-03 FIX: Funções auxiliares para coletar parâmetros do formulário de edição
     */
    getEditXttsParameters() {
        return {
            temperature: parseFloat(document.getElementById('edit-qp-xtts-temperature').value),
            speed: parseFloat(document.getElementById('edit-qp-xtts-speed').value),
            repetition_penalty: parseFloat(document.getElementById('edit-qp-xtts-repetition-penalty').value),
            top_p: parseFloat(document.getElementById('edit-qp-xtts-top-p').value),
            top_k: parseInt(document.getElementById('edit-qp-xtts-top-k').value),
            length_penalty: parseFloat(document.getElementById('edit-qp-xtts-length-penalty').value),
            enable_text_splitting: document.getElementById('edit-qp-xtts-enable-text-splitting').checked
        };
    },
    
    getEditF5ttsParameters() {
        return {
            nfe_step: parseInt(document.getElementById('edit-qp-f5tts-nfe-step').value),
            cfg_scale: parseFloat(document.getElementById('edit-qp-f5tts-cfg-scale').value),
            speed: parseFloat(document.getElementById('edit-qp-f5tts-speed').value),
            sway_sampling_coef: parseFloat(document.getElementById('edit-qp-f5tts-sway-sampling-coef').value),
            denoise_audio: document.getElementById('edit-qp-f5tts-denoise-audio').checked,
            noise_reduction_strength: parseFloat(document.getElementById('edit-qp-f5tts-noise-reduction-strength').value),
            enhance_prosody: document.getElementById('edit-qp-f5tts-enhance-prosody').checked,
            prosody_strength: parseFloat(document.getElementById('edit-qp-f5tts-prosody-strength').value),
            apply_normalization: document.getElementById('edit-qp-f5tts-apply-normalization').checked,
            target_loudness: parseFloat(document.getElementById('edit-qp-f5tts-target-loudness').value),
            apply_declipping: document.getElementById('edit-qp-f5tts-apply-declipping').checked,
            apply_deessing: document.getElementById('edit-qp-f5tts-apply-deessing').checked,
            deessing_frequency: parseInt(document.getElementById('edit-qp-f5tts-deessing-frequency').value),
            add_breathing: document.getElementById('edit-qp-f5tts-add-breathing').checked,
            breathing_strength: parseFloat(document.getElementById('edit-qp-f5tts-breathing-strength').value),
            pause_optimization: document.getElementById('edit-qp-f5tts-pause-optimization').checked
        };
    },

    async deleteQualityProfile(engine, profileId) {
        if (!confirm('Tem certeza que deseja excluir este perfil?')) return;
        
        try {
            await this.fetchJson(`${API_BASE}/quality-profiles/${engine}/${profileId}`, { method: 'DELETE' });
            this.showToast('Sucesso', 'Perfil excluído com sucesso', 'success');
            this.loadQualityProfiles();
        } catch (error) {
            this.showToast('Erro', `Falha ao excluir perfil: ${error.message}`, 'error');
        }
    },

    /**
     * INT-02 FIX: Duplicate Quality Profile
     * Endpoint: POST /quality-profiles/{engine}/{profile_id}/duplicate
     */
    async duplicateQualityProfile(engine, profileId, originalName) {
        // Prompt for new name (optional)
        const newName = prompt(`Duplicar perfil "${originalName}"\n\nNovo nome (deixe vazio para auto-gerar):`, `${originalName} - Cópia`);
        
        // User cancelled
        if (newName === null) return;
        
        try {
            // Build URL with optional new_name query param
            const url = newName.trim() 
                ? `${API_BASE}/quality-profiles/${engine}/${profileId}/duplicate?new_name=${encodeURIComponent(newName.trim())}`
                : `${API_BASE}/quality-profiles/${engine}/${profileId}/duplicate`;
            
            const duplicated = await this.fetchJson(url, {
                method: 'POST'
            });
            
            this.showToast('Sucesso', `Perfil "${duplicated.name}" criado com sucesso`, 'success');
            await this.loadQualityProfiles(); // Reload list to show new profile
        } catch (error) {
            this.showToast('Erro', `Falha ao duplicar: ${error.message}`, 'error');
        }
    },

    /**
     * Duplicar perfil a partir do modal de edição
     */
    async duplicateProfileFromEdit() {
        const engine = document.getElementById('edit-qp-engine').value;
        const profileId = document.getElementById('edit-qp-id').value;
        const currentName = document.getElementById('edit-qp-name').value;
        
        // Fechar modal de edição
        const editModal = bootstrap.Modal.getInstance(document.getElementById('modal-edit-profile'));
        if (editModal) {
            editModal.hide();
        }
        
        // Chamar função de duplicação
        await this.duplicateQualityProfile(engine, profileId, currentName);
    },

    async setDefaultProfile(engine, profileId) {
        try {
            await this.fetchJson(`${API_BASE}/quality-profiles/${engine}/${profileId}/set-default`, { method: 'POST' });
            this.showToast('Sucesso', 'Perfil definido como padrão', 'success');
            this.loadQualityProfiles();
        } catch (error) {
            this.showToast('Erro', `Falha ao definir padrão: ${error.message}`, 'error');
        }
    },

    // ==================== ADMIN ====================
    async loadAdminSection() {
        await Promise.all([
            this.loadHealthBasic(),
            this.loadHealthDeep(),
            this.loadAdminStatsDetail(),
        ]);
    },

    async loadHealthBasic() {
        const container = document.getElementById('admin-health-basic');
        if (!container) return;
        
        try {
            const data = await this.fetchJson(`${API_BASE}/`);
            container.innerHTML = `
                <div class="text-success text-center mb-2">
                    <i class="bi bi-check-circle-fill fs-1"></i>
                </div>
                <div class="json-display">${JSON.stringify(data, null, 2)}</div>
            `;
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async loadHealthDeep() {
        const container = document.getElementById('admin-health-deep');
        if (!container) return;
        
        try {
            const data = await this.fetchJson(`${API_BASE}/health`);
            container.innerHTML = `<div class="json-display">${JSON.stringify(data, null, 2)}</div>`;
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async loadAdminStatsDetail() {
        const container = document.getElementById('admin-stats');
        if (!container) return;
        
        try {
            const data = await this.fetchJson(`${API_BASE}/admin/stats`);
            container.innerHTML = this.renderStatsHtml(data);
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async performCleanup() {
        const deep = document.getElementById('cleanup-deep').checked;
        
        if (!confirm(`Executar limpeza${deep ? ' profunda' : ''}?`)) return;
        
        try {
            const result = await this.fetchJson(`${API_BASE}/admin/cleanup?deep=${deep}`, { method: 'POST' });
            this.showToast('Sucesso', 'Limpeza executada com sucesso', 'success');
            
            // Show result
            this.showModal('Resultado da Limpeza', `<div class="json-display">${JSON.stringify(result, null, 2)}</div>`);
            
            // Reload stats
            this.loadAdminStatsDetail();
            
        } catch (error) {
            this.showToast('Erro', `Falha na limpeza: ${error.message}`, 'error');
        }
    },

    // ==================== FEATURE FLAGS ====================
    async loadFeatureFlags() {
        const container = document.getElementById('feature-flags-list');
        
        try {
            container.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Carregando...</p></div>';
            
            const flags = await this.fetchJson(`${API_BASE}/feature-flags`);
            
            if (Object.keys(flags).length > 0) {
                container.innerHTML = `
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Feature</th>
                                    <th>Status</th>
                                    <th>Valor</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${Object.entries(flags).map(([key, value]) => `
                                    <tr>
                                        <td><code>${key}</code></td>
                                        <td>
                                            ${typeof value === 'boolean' 
                                                ? `<span class="badge ${value ? 'bg-success' : 'bg-secondary'}">${value ? 'ATIVO' : 'INATIVO'}</span>`
                                                : '-'
                                            }
                                        </td>
                                        <td><code>${JSON.stringify(value)}</code></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            } else {
                container.innerHTML = this.renderEmptyState('Nenhuma feature flag configurada');
            }
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    async checkFeatureFlag() {
        const flagName = document.getElementById('flag-name').value.trim();
        const userId = document.getElementById('flag-user-id').value.trim();
        const resultContainer = document.getElementById('flag-result');
        
        if (!flagName) {
            this.showToast('Atenção', 'Digite o nome da feature', 'warning');
            return;
        }
        
        try {
            const url = userId 
                ? `${API_BASE}/feature-flags/${flagName}?user_id=${userId}`
                : `${API_BASE}/feature-flags/${flagName}`;
            
            const result = await this.fetchJson(url);
            
            resultContainer.innerHTML = `
                <div class="alert alert-info">
                    <h6>Resultado:</h6>
                    <div class="json-display">${JSON.stringify(result, null, 2)}</div>
                </div>
            `;
        } catch (error) {
            resultContainer.innerHTML = `<div class="alert alert-danger">Erro: ${error.message}</div>`;
        }
    },

    // ==================== UTILITIES ====================
    renderEmptyState(title, subtitle = '') {
        return `
            <div class="empty-state">
                <i class="bi bi-inbox"></i>
                <h5>${title}</h5>
                ${subtitle ? `<p class="text-muted">${subtitle}</p>` : ''}
            </div>
        `;
    },

    showModal(title, content) {
        // Use job details modal for generic purposes
        const modal = new bootstrap.Modal(document.getElementById('modal-job-details'));
        document.querySelector('#modal-job-details .modal-title').textContent = title;
        document.getElementById('modal-job-details-body').innerHTML = content;
        modal.show();
    },

    formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    },

    formatValue(value) {
        if (typeof value === 'boolean') {
            return `<span class="badge ${value ? 'bg-success' : 'bg-secondary'}">${value ? 'Sim' : 'Não'}</span>`;
        }
        if (typeof value === 'number') {
            return value.toLocaleString('pt-BR');
        }
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        return value;
    },
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});

/**
 * ========================================================
 * FIX INT-05: Global Error Handlers for Extension Errors
 * ========================================================
 * 
 * Capture unhandled errors and filter out Chrome extension errors
 * before they reach the console.
 */

// Handler for synchronous errors
window.addEventListener('error', (event) => {
  const errorMsg = (event.message || '').toLowerCase();
  
  const isExtensionError = [
    'message port closed',
    'extension context',
    'runtime.lasterror',
    'chrome.runtime'
  ].some(pattern => errorMsg.includes(pattern));
  
  if (isExtensionError) {
    console.debug('[GLOBAL ERROR HANDLER] Extension error suppressed:', event.message);
    event.preventDefault(); // Prevent default browser logging
    return true;
  }
});

// Handler for unhandled Promise rejections
window.addEventListener('unhandledrejection', (event) => {
  const reason = (event.reason?.message || event.reason || '').toString().toLowerCase();
  
  const isExtensionError = [
    'message port closed',
    'extension context'
  ].some(pattern => reason.includes(pattern));
  
  if (isExtensionError) {
    console.debug('[PROMISE REJECTION] Extension error suppressed:', event.reason);
    event.preventDefault();
  }
});

console.log('✅ Global error handlers installed (INT-05 fix)');
