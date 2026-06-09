// Calibre Web Sync Module
(function() {
    'use strict';

    // DOM Elements
    const calibreUrlInput = document.getElementById('calibre-url');
    const calibreUserInput = document.getElementById('calibre-user');
    const calibrePassInput = document.getElementById('calibre-pass');
    const calibreFolderInput = document.getElementById('calibre-folder');
    const saveCalibreBtn = document.getElementById('save-calibre-settings');
    const syncCalibreBtn = document.getElementById('sync-calibre-btn');
    const calibreLogOutput = document.getElementById('calibre-log-output');

    let isSyncing = false;

    // Load settings on init
    async function loadSettings() {
        try {
            const settings = await api.getCalibreSettings();
            if (settings.calibre_url) calibreUrlInput.value = settings.calibre_url;
            if (settings.username) calibreUserInput.value = settings.username;
            if (settings.password) calibrePassInput.value = settings.password;
            if (settings.epub_folder) calibreFolderInput.value = settings.epub_folder;
        } catch (e) {
            console.error('Failed to load Calibre settings:', e);
        }
    }

    // Save settings
    async function saveSettings() {
        const settings = {
            calibre_url: calibreUrlInput.value.trim(),
            username: calibreUserInput.value.trim(),
            password: calibrePassInput.value,
            epub_folder: calibreFolderInput.value.trim()
        };

        try {
            await api.saveCalibreSettings(settings);
            showLog('Settings saved successfully!', 'success');
        } catch (e) {
            showLog('Failed to save settings: ' + e.message, 'error');
        }
    }

    // Sync EPUB files
    async function syncEpub() {
        if (isSyncing) return;

        // Check if settings are configured
        if (!calibreUrlInput.value.trim()) {
            showLog('Please configure Calibre-Web URL first!', 'error');
            return;
        }
        if (!calibreFolderInput.value.trim()) {
            showLog('Please configure EPUB Folder Path first!', 'error');
            return;
        }

        isSyncing = true;
        syncCalibreBtn.disabled = true;
        syncCalibreBtn.innerHTML = '<span class="spinner"></span> Syncing...';
        calibreLogOutput.textContent = '';

        showLog('Starting EPUB sync to Calibre-Web...', 'info');

        try {
            await api.syncCalibre((data) => {
                if (data.type === 'log') {
                    showLog(data.message, data.level || 'info');
                } else if (data.type === 'progress') {
                    showLog(`[${data.current}/${data.total}] ${data.message}`, 'info');
                } else if (data.type === 'error') {
                    showLog('ERROR: ' + data.message, 'error');
                } else if (data.type === 'success') {
                    showLog('SUCCESS: ' + data.message, 'success');
                }
            });

            showLog('\n=== Sync completed ===', 'success');
        } catch (e) {
            showLog('Sync failed: ' + e.message, 'error');
        } finally {
            isSyncing = false;
            syncCalibreBtn.disabled = false;
            syncCalibreBtn.innerHTML = '<span class="material-icons" style="font-size: 20px; vertical-align: middle;">sync</span> Sync EPUB to Calibre-Web';
        }
    }

    // Show log message
    function showLog(message, level = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const prefix = level === 'error' ? '❌' : level === 'success' ? '✅' : 'ℹ️';

        calibreLogOutput.textContent += `[${timestamp}] ${prefix} ${message}\n`;
        calibreLogOutput.scrollTop = calibreLogOutput.scrollHeight;
    }

    // Event Listeners
    saveCalibreBtn.addEventListener('click', saveSettings);
    syncCalibreBtn.addEventListener('click', syncEpub);

    // Initialize
    loadSettings();

    // Make loadSettings available for tab switch
    window.loadCalibreSettings = loadSettings;
})();
