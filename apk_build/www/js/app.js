/* ==========================================================================
   PulseGet Pro — 2026 Core Frontend Controller
   ========================================================================== */

class PulseGetApp {
  constructor() {
    this.tasks = {};
    this.currentCategory = 'all';
    this.searchQuery = '';
    this.settings = {};
    this.peakSpeed = 0;
    this.totalDownloadedSession = 0;
    this.currentAnalyzedData = null;
    this.isMediaDownload = false;
    this.ws = null;
    this.speedChart = null;
    this.chartDataPoints = Array(25).fill(0);
    this.chartLabels = Array(25).fill('');
    this.analysisDebounceTimer = null;

    this.init();
  }

  async init() {
    this.initElements();
    this.initChart();
    this.bindEvents();
    this.connectWebSocket();
    this.loadInitialSettings();
  }

  initElements() {
    // Top Bar
    this.globalSpeedEl = document.getElementById('globalSpeed');
    this.activeTasksCountEl = document.getElementById('activeTasksCount');
    this.btnOpenNewModal = document.getElementById('btnOpenNewModal');
    this.btnClearCompleted = document.getElementById('btnClearCompleted');
    this.btnOpenSettings = document.getElementById('btnOpenSettings');

    // Quick Grab Strip
    this.quickUrlInput = document.getElementById('quickUrlInput');
    this.btnQuickPasteClipboard = document.getElementById('btnQuickPasteClipboard');
    this.btnQuickStart = document.getElementById('btnQuickStart');

    // Sidebar & Badges
    this.badgeAll = document.getElementById('badgeAll');
    this.badgeDownloading = document.getElementById('badgeDownloading');
    this.badgeCompleted = document.getElementById('badgeCompleted');
    this.badgeVideo = document.getElementById('badgeVideo');
    this.badgeAudio = document.getElementById('badgeAudio');
    this.badgeDocument = document.getElementById('badgeDocument');
    this.badgeArchive = document.getElementById('badgeArchive');
    this.sidebarThreads = document.getElementById('sidebarThreads');

    // Main Dashboard & Chart Stats
    this.statPeakSpeed = document.getElementById('statPeakSpeed');
    this.statTotalDownloaded = document.getElementById('statTotalDownloaded');
    this.statActiveThreads = document.getElementById('statActiveThreads');
    this.searchInput = document.getElementById('searchInput');
    this.taskListEl = document.getElementById('taskList');
    this.emptyStateEl = document.getElementById('emptyState');
    this.btnEmptyAdd = document.getElementById('btnEmptyAdd');
    this.btnResumeAll = document.getElementById('btnResumeAll');
    this.btnPauseAll = document.getElementById('btnPauseAll');

    // Modals
    this.newDownloadModal = document.getElementById('newDownloadModal');
    this.btnCloseNewModal = document.getElementById('btnCloseNewModal');
    this.btnCancelAdd = document.getElementById('btnCancelAdd');
    this.inputUrl = document.getElementById('inputUrl');
    this.btnPasteClipboard = document.getElementById('btnPasteClipboard');
    this.analysisLoader = document.getElementById('analysisLoader');
    this.probeResult = document.getElementById('probeResult');
    this.probeFilename = document.getElementById('probeFilename');
    this.probeSize = document.getElementById('probeSize');
    this.probeRanges = document.getElementById('probeRanges');
    this.probeCategory = document.getElementById('probeCategory');
    this.probeTypeIcon = document.getElementById('probeTypeIcon');

    this.mediaPreview = document.getElementById('mediaPreview');
    this.mediaThumb = document.getElementById('mediaThumb');
    this.mediaTitle = document.getElementById('mediaTitle');
    this.mediaUploader = document.getElementById('mediaUploader');
    this.mediaDuration = document.getElementById('mediaDuration');
    this.selectFormat = document.getElementById('selectFormat');

    this.rangeThreads = document.getElementById('rangeThreads');
    this.threadsBadge = document.getElementById('threadsBadge');
    this.inputSavePath = document.getElementById('inputSavePath');
    this.btnConfirmDownload = document.getElementById('btnConfirmDownload');

    // Player Modal
    this.playerModal = document.getElementById('playerModal');
    this.playerTitle = document.getElementById('playerTitle');
    this.btnClosePlayer = document.getElementById('btnClosePlayer');
    this.inAppVideo = document.getElementById('inAppVideo');
    this.inAppAudio = document.getElementById('inAppAudio');

    // Settings Modal
    this.settingsModal = document.getElementById('settingsModal');
    this.btnCloseSettings = document.getElementById('btnCloseSettings');
    this.btnCancelSettings = document.getElementById('btnCancelSettings');
    this.btnSaveSettings = document.getElementById('btnSaveSettings');
    this.settingSaveDir = document.getElementById('settingSaveDir');
    this.settingDefaultThreads = document.getElementById('settingDefaultThreads');
    this.settingTheme = document.getElementById('settingTheme');
    this.settingSoundEffects = document.getElementById('settingSoundEffects');

    // Audio
    this.completionSound = document.getElementById('completionSound');

    // Mobile
    this.btnMobAdd = document.getElementById('btnMobAdd');
    this.btnMobSettings = document.getElementById('btnMobSettings');
  }

  initChart() {
    const ctx = document.getElementById('speedChart').getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 140);
    gradient.addColorStop(0, 'rgba(0, 242, 254, 0.45)');
    gradient.addColorStop(1, 'rgba(0, 242, 254, 0.0)');

    this.speedChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.chartLabels,
        datasets: [{
          data: this.chartDataPoints,
          borderColor: '#00f2fe',
          borderWidth: 2.5,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHitRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            callbacks: {
              label: (ctx) => `${ctx.parsed.y.toFixed(2)} MB/s`
            }
          }
        },
        scales: {
          x: { display: false },
          y: {
            beginAtZero: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.05)',
              drawBorder: false
            },
            ticks: {
              color: '#64748b',
              font: { family: "'JetBrains Mono', monospace", size: 10 },
              callback: (val) => `${val} MB/s`
            }
          }
        },
        animation: {
          duration: 300
        }
      }
    });
  }

  bindEvents() {
    // Navigation category switches (.nav-btn and .nav-item)
    document.querySelectorAll('.nav-btn, .nav-item').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn, .nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.currentCategory = btn.dataset.category || 'all';
        this.renderTaskList();
      });
    });

    // Mobile nav (.mob-nav-btn and .mob-item)
    document.querySelectorAll('.mob-nav-btn, .mob-item').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mob-nav-btn, .mob-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.currentCategory = btn.dataset.category || 'all';
        this.renderTaskList();
      });
    });

    // Modals open/close
    const openNewModal = () => {
      this.newDownloadModal.classList.add('active');
      this.inputUrl.focus();
      this.checkClipboardForUrl();
    };

    // Quick Grab Strip
    if (this.btnQuickPasteClipboard) {
      this.btnQuickPasteClipboard.addEventListener('click', async () => {
        try {
          const text = await navigator.clipboard.readText();
          if (text && text.trim().startsWith('http')) {
            this.quickUrlInput.value = text.trim();
          }
        } catch (err) {
          console.warn('Clipboard read error', err);
        }
      });
    }

    if (this.btnQuickStart) {
      const launchFromQuick = () => {
        const val = this.quickUrlInput ? this.quickUrlInput.value.trim() : '';
        if (!val) {
          openNewModal();
          return;
        }
        this.inputUrl.value = val;
        openNewModal();
        this.triggerAnalyzeUrl(val);
      };

      this.btnQuickStart.addEventListener('click', launchFromQuick);
      if (this.quickUrlInput) {
        this.quickUrlInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            launchFromQuick();
          }
        });
      }
    }

    // Search input
    this.searchInput.addEventListener('input', (e) => {
      this.searchQuery = e.target.value.toLowerCase().trim();
      this.renderTaskList();
    });
    this.btnOpenNewModal.addEventListener('click', openNewModal);
    this.btnEmptyAdd.addEventListener('click', openNewModal);
    if (this.btnMobAdd) this.btnMobAdd.addEventListener('click', openNewModal);

    const closeNewModal = () => {
      this.newDownloadModal.classList.remove('active');
      this.resetNewModal();
    };
    this.btnCloseNewModal.addEventListener('click', closeNewModal);
    this.btnCancelAdd.addEventListener('click', closeNewModal);

    // Settings Modal
    const openSettings = () => {
      this.settingsModal.classList.add('active');
    };
    this.btnOpenSettings.addEventListener('click', openSettings);
    if (this.btnMobSettings) this.btnMobSettings.addEventListener('click', openSettings);

    const closeSettings = () => {
      this.settingsModal.classList.remove('active');
    };
    this.btnCloseSettings.addEventListener('click', closeSettings);
    this.btnCancelSettings.addEventListener('click', closeSettings);

    // Save Settings
    this.btnSaveSettings.addEventListener('click', () => this.savePreferences());

    // Player Modal Close
    this.btnClosePlayer.addEventListener('click', () => {
      this.playerModal.classList.remove('active');
      this.inAppVideo.pause();
      this.inAppAudio.pause();
      this.inAppVideo.src = '';
      this.inAppAudio.src = '';
    });

    // Clear completed
    this.btnClearCompleted.addEventListener('click', async () => {
      await fetch('/api/download/clear-completed', { method: 'POST' });
    });

    // Resume / Pause All
    this.btnResumeAll.addEventListener('click', () => {
      Object.values(this.tasks).forEach(t => {
        if (t.status === 'paused') fetch(`/api/download/resume/${t.id}`, { method: 'POST' });
      });
    });
    this.btnPauseAll.addEventListener('click', () => {
      Object.values(this.tasks).forEach(t => {
        if (t.status === 'downloading') fetch(`/api/download/pause/${t.id}`, { method: 'POST' });
      });
    });

    // URL input typing debounced analyzer
    this.inputUrl.addEventListener('input', () => {
      clearTimeout(this.analysisDebounceTimer);
      this.analysisDebounceTimer = setTimeout(() => {
        this.triggerAnalyzeUrl(this.inputUrl.value.trim());
      }, 400);
    });

    // Paste clipboard button
    this.btnPasteClipboard.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text && text.startsWith('http')) {
          this.inputUrl.value = text.trim();
          this.triggerAnalyzeUrl(this.inputUrl.value);
        }
      } catch (err) {
        console.warn('Clipboard read error', err);
      }
    });

    // Threads range slider
    this.rangeThreads.addEventListener('input', (e) => {
      this.threadsBadge.innerText = `${e.target.value} Segments`;
    });

    // Confirm Download
    this.btnConfirmDownload.addEventListener('click', () => this.startRequestedDownload());
  }

  async checkClipboardForUrl() {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.startsWith('http') && !this.inputUrl.value) {
          this.inputUrl.value = text.trim();
          this.triggerAnalyzeUrl(text.trim());
        }
      }
    } catch (_) {}
  }

  async loadInitialSettings() {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        this.settings = await res.json();
        this.applySettingsToUI();
      }
    } catch (err) {
      console.error('Failed loading settings', err);
    }
  }

  applySettingsToUI() {
    if (this.settings.save_directory) {
      this.inputSavePath.value = this.settings.save_directory;
      this.settingSaveDir.value = this.settings.save_directory;
    }
    if (this.settings.default_threads) {
      this.rangeThreads.value = this.settings.default_threads;
      this.threadsBadge.innerText = `${this.settings.default_threads} Segments`;
      this.sidebarThreads.innerText = `${this.settings.default_threads} Segments`;
      this.settingDefaultThreads.value = String(this.settings.default_threads);
    }
    if (this.settings.theme) {
      document.body.className = this.settings.theme;
      this.settingTheme.value = this.settings.theme;
    }
    if (this.settings.sound_effects !== undefined) {
      this.settingSoundEffects.checked = this.settings.sound_effects;
    }
  }

  async savePreferences() {
    const payload = {
      save_directory: this.settingSaveDir.value.trim(),
      default_threads: parseInt(this.settingDefaultThreads.value, 10),
      theme: this.settingTheme.value,
      sound_effects: this.settingSoundEffects.checked
    };
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        this.settings = data.settings;
        this.applySettingsToUI();
        this.settingsModal.classList.remove('active');
      }
    } catch (err) {
      alert('Error saving preferences: ' + err.message);
    }
  }

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsUrl = `${protocol}//${host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleSocketMessage(data);
      } catch (e) {
        console.error('WS Parse Error', e);
      }
    };

    this.ws.onclose = () => {
      // Automatic reconnection
      setTimeout(() => this.connectWebSocket(), 2000);
    };

    this.ws.onerror = (err) => {
      console.warn('WS error:', err);
    };
  }

  handleSocketMessage(msg) {
    if (msg.type === 'init_state') {
      this.tasks = {};
      msg.tasks.forEach(t => { this.tasks[t.id] = t; });
      if (msg.settings) {
        this.settings = msg.settings;
        this.applySettingsToUI();
      }
      this.renderTaskList();
      this.updateStatsCounters();
    } else if (msg.type === 'task_update') {
      const prev = this.tasks[msg.task.id];
      // Check completion chime
      if (prev && prev.status !== 'completed' && msg.task.status === 'completed') {
        if (this.settings.sound_effects) {
          this.completionSound.play().catch(() => {});
        }
      }

      this.tasks[msg.task.id] = msg.task;
      this.updateTaskCard(msg.task);
      this.updateGlobalBandwidth(msg.global_speed_bps, msg.global_speed_formatted, msg.active_downloads);
      this.updateStatsCounters();
    } else if (msg.type === 'task_removed') {
      delete this.tasks[msg.task_id];
      const card = document.getElementById(`task-card-${msg.task_id}`);
      if (card) card.remove();
      this.renderTaskList();
      this.updateStatsCounters();
    } else if (msg.type === 'tasks_cleared') {
      msg.task_ids.forEach(tid => delete this.tasks[tid]);
      this.renderTaskList();
      this.updateStatsCounters();
    }
  }

  updateGlobalBandwidth(speedBps, formattedSpeed, activeDownloads) {
    this.globalSpeedEl.innerText = formattedSpeed || '0.0 KB/s';
    this.activeTasksCountEl.innerText = `${activeDownloads || 0} Active`;

    // Speed in MB/s for chart
    const speedMB = (speedBps || 0) / (1024 * 1024);
    if (speedMB > this.peakSpeed) {
      this.peakSpeed = speedMB;
      this.statPeakSpeed.innerText = `${this.peakSpeed.toFixed(2)} MB/s`;
    }

    // Push into chart data
    this.chartDataPoints.push(speedMB);
    this.chartDataPoints.shift();
    if (this.speedChart) {
      this.speedChart.update('none');
    }

    // Active threads count
    let totalThreads = 0;
    Object.values(this.tasks).forEach(t => {
      if (t.status === 'downloading') {
        totalThreads += (t.threads || 16);
      }
    });
    this.statActiveThreads.innerText = `${totalThreads} Threads`;
  }

  updateStatsCounters() {
    const list = Object.values(this.tasks);
    const countAll = list.length;
    const countDownloading = list.filter(t => t.status === 'downloading' || t.status === 'merging').length;
    const countCompleted = list.filter(t => t.status === 'completed').length;
    const countVideo = list.filter(t => t.category === 'video').length;
    const countAudio = list.filter(t => t.category === 'audio').length;
    const countDoc = list.filter(t => t.category === 'document').length;
    const countArchive = list.filter(t => t.category === 'archive').length;

    this.badgeAll.innerText = countAll;
    this.badgeDownloading.innerText = countDownloading;
    this.badgeCompleted.innerText = countCompleted;
    this.badgeVideo.innerText = countVideo;
    this.badgeAudio.innerText = countAudio;
    this.badgeDocument.innerText = countDoc;
    this.badgeArchive.innerText = countArchive;

    // Total session download
    let totalBytes = 0;
    list.forEach(t => { totalBytes += (t.downloaded_bytes || 0); });
    this.statTotalDownloaded.innerText = this.formatBytes(totalBytes);
  }

  async triggerAnalyzeUrl(url) {
    if (!url || !url.startsWith('http')) return;

    this.analysisLoader.classList.remove('hidden');
    this.probeResult.classList.add('hidden');
    this.mediaPreview.classList.add('hidden');

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      this.analysisLoader.classList.add('hidden');

      if (data.is_media && data.data && data.data.success) {
        this.displayMediaAnalysis(data.data);
      } else if (data.data) {
        this.displayProbeAnalysis(data.data);
      }
    } catch (err) {
      this.analysisLoader.classList.add('hidden');
      console.warn('Analyze failed', err);
    }
  }

  displayProbeAnalysis(probe) {
    this.isMediaDownload = false;
    this.currentAnalyzedData = probe;

    this.probeResult.classList.remove('hidden');
    this.probeFilename.innerText = probe.filename || 'Direct File';
    this.probeSize.innerText = probe.total_formatted || 'Unknown Size';

    if (probe.supports_ranges) {
      this.probeRanges.innerHTML = '<i class="fa-solid fa-check"></i> Multi-Thread Ready (Fast)';
      this.probeRanges.className = 'tag-pill tag-emerald';
    } else {
      this.probeRanges.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Single Stream';
      this.probeRanges.className = 'tag-pill tag-cyan';
    }

    this.probeCategory.innerText = (probe.category || 'other').toUpperCase();
    
    // Icon
    const iconClass = this.getCategoryIcon(probe.category);
    this.probeTypeIcon.innerHTML = `<i class="${iconClass}"></i>`;
  }

  displayMediaAnalysis(media) {
    this.isMediaDownload = true;
    this.currentAnalyzedData = media;

    this.mediaPreview.classList.remove('hidden');
    this.mediaTitle.innerText = media.title || 'Video Stream';
    this.mediaUploader.innerText = media.uploader || 'Universal Media';
    this.mediaThumb.src = media.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=300';
    
    if (media.duration) {
      const m = Math.floor(media.duration / 60);
      const s = media.duration % 60;
      this.mediaDuration.innerText = `${m}:${s < 10 ? '0' : ''}${s}`;
    } else {
      this.mediaDuration.innerText = '--:--';
    }

    // Populate format dropdown
    this.selectFormat.innerHTML = '';
    (media.formats || []).forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.id;
      opt.innerText = f.label;
      this.selectFormat.appendChild(opt);
    });
  }

  resetNewModal() {
    this.inputUrl.value = '';
    this.analysisLoader.classList.add('hidden');
    this.probeResult.classList.add('hidden');
    this.mediaPreview.classList.add('hidden');
    this.currentAnalyzedData = null;
    this.isMediaDownload = false;
  }

  async startRequestedDownload() {
    const url = this.inputUrl.value.trim();
    if (!url) {
      alert('Please enter a valid download link.');
      return;
    }

    const payload = {
      url: url,
      threads: parseInt(this.rangeThreads.value, 10),
      save_path: this.inputSavePath.value || undefined
    };

    if (this.isMediaDownload && this.currentAnalyzedData) {
      payload.is_media = true;
      payload.filename = this.currentAnalyzedData.title;
      payload.format_id = this.selectFormat.value;
      payload.category = this.selectFormat.value.includes('audio') ? 'audio' : 'video';
    } else if (this.currentAnalyzedData) {
      payload.filename = this.currentAnalyzedData.filename;
      payload.category = this.currentAnalyzedData.category;
    }

    try {
      const res = await fetch('/api/download/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        this.newDownloadModal.classList.remove('active');
        this.resetNewModal();
      } else {
        const err = await res.json();
        alert('Download error: ' + (err.detail || 'Could not start'));
      }
    } catch (e) {
      alert('Failed connecting to engine: ' + e.message);
    }
  }

  renderTaskList() {
    let tasks = Object.values(this.tasks);

    // Filter by Category
    if (this.currentCategory === 'downloading') {
      tasks = tasks.filter(t => t.status === 'downloading' || t.status === 'merging' || t.status === 'queued');
    } else if (this.currentCategory === 'completed') {
      tasks = tasks.filter(t => t.status === 'completed');
    } else if (this.currentCategory !== 'all') {
      tasks = tasks.filter(t => t.category === this.currentCategory);
    }

    // Filter by Search Query
    if (this.searchQuery) {
      tasks = tasks.filter(t => 
        (t.filename && t.filename.toLowerCase().includes(this.searchQuery)) ||
        (t.url && t.url.toLowerCase().includes(this.searchQuery))
      );
    }

    // Sort: newest created first
    tasks.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));

    if (tasks.length === 0) {
      this.emptyStateEl.style.display = 'flex';
      // Remove card elements
      document.querySelectorAll('.download-card').forEach(c => c.remove());
      return;
    }

    this.emptyStateEl.style.display = 'none';

    // Build or update cards
    const existingCards = new Set();
    tasks.forEach(task => {
      existingCards.add(task.id);
      let card = document.getElementById(`task-card-${task.id}`);
      if (!card) {
        card = this.createTaskCardElement(task);
        this.taskListEl.appendChild(card);
      }
      this.updateTaskCard(task);
    });

    // Remove old cards
    document.querySelectorAll('.download-card').forEach(c => {
      const id = c.id.replace('task-card-', '');
      if (!existingCards.has(id)) {
        c.remove();
      }
    });
  }

  createTaskCardElement(task) {
    const card = document.createElement('div');
    card.id = `task-card-${task.id}`;
    card.className = `download-card status-${task.status}`;

    const iconClass = this.getCategoryIcon(task.category);
    const typeModifier = `file-type-${task.category || 'other'}`;

    card.innerHTML = `
      <div class="card-top">
        <div class="file-info-group">
          <div class="file-type-icon ${typeModifier}">
            <i class="${iconClass}"></i>
          </div>
          <div class="file-details">
            <span class="file-title" title="${task.filename}">${task.filename}</span>
            <div class="file-meta-row">
              <span class="meta-pill" id="card-size-${task.id}">${task.downloaded_formatted} / ${task.total_formatted}</span>
              <span class="meta-pill text-cyan" id="card-speed-${task.id}">${task.speed || '0 KB/s'}</span>
              <span class="meta-pill" id="card-eta-${task.id}">ETA: ${task.eta || '--:--'}</span>
              <span class="meta-pill" id="card-threads-${task.id}">${task.threads || 16} Chunks</span>
            </div>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-icon btn-action-toggle" id="btn-toggle-${task.id}" title="Pause/Resume">
            <i class="fa-solid fa-pause"></i>
          </button>
          <button class="btn-icon" id="btn-folder-${task.id}" title="Show in Folder">
            <i class="fa-solid fa-folder-open"></i>
          </button>
          <button class="btn-icon btn-preview hidden" id="btn-preview-${task.id}" title="Preview / Play">
            <i class="fa-solid fa-circle-play"></i>
          </button>
          <button class="btn-icon btn-icon-danger" id="btn-cancel-${task.id}" title="Cancel & Delete">
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      </div>

      <div class="progress-section">
        <div class="progress-track">
          <div class="progress-fill" id="card-progress-bar-${task.id}" style="width: ${task.progress}%"></div>
        </div>
        <div class="progress-stats-row">
          <span id="card-status-text-${task.id}">${this.formatStatus(task.status)}</span>
          <span id="card-percent-text-${task.id}">${task.progress.toFixed(1)}%</span>
        </div>
      </div>

      <!-- Segment Chunks Visualizer -->
      <div class="chunks-section" id="chunks-section-${task.id}">
        <div class="chunks-visualizer-toggle" id="chunks-toggle-${task.id}">
          <span><i class="fa-solid fa-network-wired"></i> Live Segment Stream Activity</span>
          <span id="chunks-active-count-${task.id}">16 Threads Streaming</span>
        </div>
        <div class="chunks-grid" id="chunks-grid-${task.id}"></div>
      </div>
    `;

    // Bind card actions
    const btnToggle = card.querySelector(`#btn-toggle-${task.id}`);
    btnToggle.addEventListener('click', () => {
      const cur = this.tasks[task.id];
      if (!cur) return;
      if (cur.status === 'downloading') {
        fetch(`/api/download/pause/${task.id}`, { method: 'POST' });
      } else {
        fetch(`/api/download/resume/${task.id}`, { method: 'POST' });
      }
    });

    const btnFolder = card.querySelector(`#btn-folder-${task.id}`);
    btnFolder.addEventListener('click', () => {
      fetch(`/api/download/open-folder/${task.id}`, { method: 'POST' });
    });

    const btnCancel = card.querySelector(`#btn-cancel-${task.id}`);
    btnCancel.addEventListener('click', () => {
      if (confirm('Cancel and delete this download?')) {
        fetch(`/api/download/cancel/${task.id}`, { method: 'POST' });
      }
    });

    const btnPreview = card.querySelector(`#btn-preview-${task.id}`);
    btnPreview.addEventListener('click', () => {
      this.openMediaPlayer(this.tasks[task.id]);
    });

    return card;
  }

  updateTaskCard(task) {
    const card = document.getElementById(`task-card-${task.id}`);
    if (!card) return;

    card.className = `download-card status-${task.status}`;

    // Update Meta
    const sizeEl = document.getElementById(`card-size-${task.id}`);
    if (sizeEl) sizeEl.innerText = `${task.downloaded_formatted} / ${task.total_formatted}`;

    const speedEl = document.getElementById(`card-speed-${task.id}`);
    if (speedEl) speedEl.innerText = task.speed || '0 KB/s';

    const etaEl = document.getElementById(`card-eta-${task.id}`);
    if (etaEl) etaEl.innerText = `ETA: ${task.eta || '--:--'}`;

    const pBar = document.getElementById(`card-progress-bar-${task.id}`);
    if (pBar) {
      pBar.style.width = `${task.progress}%`;
      if (task.status === 'completed') pBar.classList.add('completed');
    }

    const pText = document.getElementById(`card-percent-text-${task.id}`);
    if (pText) pText.innerText = `${task.progress.toFixed(1)}%`;

    const statusText = document.getElementById(`card-status-text-${task.id}`);
    if (statusText) statusText.innerText = this.formatStatus(task.status, task.error_message);

    // Toggle button icon
    const btnToggle = document.getElementById(`btn-toggle-${task.id}`);
    if (btnToggle) {
      if (task.status === 'downloading') {
        btnToggle.innerHTML = '<i class="fa-solid fa-pause"></i>';
        btnToggle.style.display = 'flex';
      } else if (task.status === 'paused') {
        btnToggle.innerHTML = '<i class="fa-solid fa-play"></i>';
        btnToggle.style.display = 'flex';
      } else {
        btnToggle.style.display = 'none';
      }
    }

    // Media Preview Button
    const btnPreview = document.getElementById(`btn-preview-${task.id}`);
    if (btnPreview && (task.category === 'video' || task.category === 'audio') && task.status === 'completed') {
      btnPreview.classList.remove('hidden');
    }

    // Render Chunks in Visualizer Grid
    this.updateChunksGrid(task);
  }

  updateChunksGrid(task) {
    const grid = document.getElementById(`chunks-grid-${task.id}`);
    if (!grid) return;

    // If chunks exist in task
    if (task.chunks && task.chunks.length > 0) {
      grid.style.gridTemplateColumns = `repeat(${Math.min(task.chunks.length, 16)}, 1fr)`;
      
      task.chunks.forEach((chunk, idx) => {
        let block = document.getElementById(`chunk-block-${task.id}-${idx}`);
        if (!block) {
          block = document.createElement('div');
          block.id = `chunk-block-${task.id}-${idx}`;
          block.className = 'chunk-block';
          block.innerHTML = `<div class="chunk-fill" style="width: 0%"></div>`;
          grid.appendChild(block);
        }

        const fill = block.querySelector('.chunk-fill');
        if (fill) fill.style.width = `${chunk.progress || 0}%`;

        if (chunk.progress >= 100) {
          block.className = 'chunk-block done';
        } else if (chunk.active) {
          block.className = 'chunk-block active';
        } else {
          block.className = 'chunk-block';
        }
      });
    }
  }

  openMediaPlayer(task) {
    if (!task) return;
    this.playerTitle.innerText = task.filename;
    this.playerModal.classList.add('active');

    const previewUrl = `/api/preview/${task.id}`;
    if (task.category === 'video') {
      this.inAppAudio.classList.add('hidden');
      this.inAppVideo.classList.remove('hidden');
      this.inAppVideo.src = previewUrl;
      this.inAppVideo.play().catch(() => {});
    } else {
      this.inAppVideo.classList.add('hidden');
      this.inAppAudio.classList.remove('hidden');
      this.inAppAudio.src = previewUrl;
      this.inAppAudio.play().catch(() => {});
    }
  }

  formatStatus(status, errorMsg) {
    switch (status) {
      case 'downloading': return '⚡ Turbo Downloading...';
      case 'merging': return '🔄 Assembling Multi-Thread Chunks...';
      case 'paused': return '⏸️ Download Paused';
      case 'completed': return '✅ Download Completed';
      case 'queued': return '⏳ Queued';
      case 'error': return `❌ Error: ${errorMsg || 'Failed'}`;
      default: return status;
    }
  }

  getCategoryIcon(cat) {
    switch (cat) {
      case 'video': return 'fa-solid fa-film';
      case 'audio': return 'fa-solid fa-music';
      case 'document': return 'fa-solid fa-file-lines';
      case 'archive': return 'fa-solid fa-box-archive';
      case 'executable': return 'fa-solid fa-rocket';
      default: return 'fa-solid fa-file';
    }
  }

  formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let size = parseFloat(bytes);
    while (size >= 1024.0 && i < units.length - 1) {
      size /= 1024.0;
      i++;
    }
    return `${size.toFixed(2)} ${units[i]}`;
  }
}

// Instantiate on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.pulseApp = new PulseGetApp();
});
