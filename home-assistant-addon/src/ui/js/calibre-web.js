// Calibre Library Sync Module
export const calibreWeb = {
    init() {
        this.libraryPathInput = document.getElementById('calibre-library-path');
        this.folderInput = document.getElementById('calibre-folder');
        this.comicFolderInput = document.getElementById('comic-folder');
        this.clearCheckbox = document.getElementById('calibre-clear');
        this.saveBtn = document.getElementById('save-calibre-settings');
        this.syncBtn = document.getElementById('sync-calibre-btn');
        this.syncComicBtn = document.getElementById('sync-comic-btn');
        this.logOutput = document.getElementById('calibre-log-output');
        this.comicLogOutput = document.getElementById('comic-log-output');

        if (!this.libraryPathInput) return;

        this.bindEvents();
        this.loadSettings();
    },

    bindEvents() {
        this.saveBtn.addEventListener('click', () => this.saveSettings());
        this.syncBtn.addEventListener('click', () => this.syncEpub());
        if (this.syncComicBtn) {
            this.syncComicBtn.addEventListener('click', () => this.syncComics());
        }
    },

    async loadSettings() {
        try {
            const response = await fetch('/api/calibre/settings');
            const data = await response.json();

            if (data.calibre_library_path) this.libraryPathInput.value = data.calibre_library_path;
            if (data.epub_folder) this.folderInput.value = data.epub_folder;
            if (data.comic_folder && this.comicFolderInput) this.comicFolderInput.value = data.comic_folder;
            if (data.clear_before_sync !== undefined) this.clearCheckbox.checked = data.clear_before_sync;
        } catch (error) {
            console.error('Failed to load Calibre settings:', error);
        }
    },

    async saveSettings() {
        const settings = {
            calibre_library_path: this.libraryPathInput.value.trim(),
            epub_folder: this.folderInput.value.trim(),
            comic_folder: this.comicFolderInput ? this.comicFolderInput.value.trim() : '',
            clear_before_sync: this.clearCheckbox.checked
        };

        try {
            this.saveBtn.disabled = true;
            this.saveBtn.textContent = 'Saving...';

            const response = await fetch('/api/calibre/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                this.showLog('Settings saved successfully!', 'success');
            } else {
                throw new Error('Failed to save settings');
            }
        } catch (error) {
            this.showLog('Error saving settings: ' + error.message, 'error');
        } finally {
            this.saveBtn.disabled = false;
            this.saveBtn.textContent = 'Save Settings';
        }
    },

    async syncEpub() {
        if (this.syncBtn.disabled) return;

        // Check if settings are configured
        if (!this.libraryPathInput.value.trim()) {
            this.showLog('Please configure Calibre Library Path first!', 'error');
            return;
        }
        if (!this.folderInput.value.trim()) {
            this.showLog('Please configure EPUB Source Folder Path first!', 'error');
            return;
        }

        this.syncBtn.disabled = true;
        this.syncBtn.innerHTML = '<span class="spinner"></span> Syncing...';
        this.logOutput.textContent = '';

        this.showLog('Starting EPUB sync to Calibre Library...', 'info');
        this.showLog('This will clear the library and rebuild it from scratch.', 'info');

        try {
            // Save settings first
            await this.saveSettings();

            const response = await fetch('/api/calibre/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.status === 401) {
                window.location.href = '/login.html';
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Sync failed');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());

                for (const line of lines) {
                    try {
                        const data = JSON.parse(line);
                        if (data.type === 'log') {
                            this.showLog(data.message, data.level || 'info');
                        } else if (data.type === 'progress') {
                            this.showLog(`[${data.current}/${data.total}] ${data.message}`, 'info');
                        } else if (data.type === 'error') {
                            this.showLog('ERROR: ' + data.message, 'error');
                        } else if (data.type === 'success') {
                            this.showLog('SUCCESS: ' + data.message, 'success');
                        }
                    } catch (e) {
                        // Skip invalid JSON
                    }
                }
            }

            this.showLog('\n=== Sync completed ===', 'success');
        } catch (error) {
            this.showLog('Sync failed: ' + error.message, 'error');
        } finally {
            this.syncBtn.disabled = false;
            this.syncBtn.innerHTML = '<span class="material-icons" style="font-size: 20px; vertical-align: middle;">sync</span> Sync EPUB to Calibre Library';
        }
    },

    showLog(message, level = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const prefix = level === 'error' ? '❌' : level === 'success' ? '✅' : 'ℹ️';

        this.logOutput.textContent += `[${timestamp}] ${prefix} ${message}\n`;
        this.logOutput.scrollTop = this.logOutput.scrollHeight;
    },

    async syncComics() {
        if (!this.syncComicBtn || this.syncComicBtn.disabled) return;

        if (!this.libraryPathInput.value.trim()) {
            this.showLog('Please configure Calibre Library Path first!', 'error');
            return;
        }
        if (!this.comicFolderInput || !this.comicFolderInput.value.trim()) {
            this.showLog('Please configure Comic Source Folder Path first!', 'error');
            return;
        }

        this.syncComicBtn.disabled = true;
        this.syncComicBtn.innerHTML = '<span class="spinner"></span> Syncing...';
        if (this.comicLogOutput) this.comicLogOutput.textContent = '';

        this.showLog('Starting Comic sync to Calibre Library...', 'info');

        try {
            await this.saveSettings();

            const response = await fetch('/api/comic/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.status === 401) {
                window.location.href = '/login.html';
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Sync failed');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());

                for (const line of lines) {
                    try {
                        const data = JSON.parse(line);
                        if (this.comicLogOutput) {
                            this.showComicLog(data.message, data.level || 'info');
                        }
                    } catch (e) {}
                }
            }

            this.showLog('=== Comic sync completed ===', 'success');
        } catch (error) {
            this.showLog('Comic sync failed: ' + error.message, 'error');
        } finally {
            this.syncComicBtn.disabled = false;
            this.syncComicBtn.innerHTML = '<span class="material-icons" style="font-size: 20px; vertical-align: middle;">sync</span> Sync Comics to Calibre Library';
        }
    },

    showComicLog(message, level = 'info') {
        if (!this.comicLogOutput) return;
        const timestamp = new Date().toLocaleTimeString();
        const prefix = level === 'error' ? '❌' : level === 'success' ? '✅' : 'ℹ️';

        this.comicLogOutput.textContent += `[${timestamp}] ${prefix} ${message}\n`;
        this.comicLogOutput.scrollTop = this.comicLogOutput.scrollHeight;
    }
};

// Make loadSettings available for tab switch
window.loadCalibreSettings = function() {
    calibreWeb.loadSettings();
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    calibreWeb.init();
});
