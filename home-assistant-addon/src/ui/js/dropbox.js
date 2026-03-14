const DropboxManager = {
    init() {
        this.appKeyInput = document.getElementById('dropbox-app-key');
        this.appSecretInput = document.getElementById('dropbox-app-secret');
        this.refreshTokenInput = document.getElementById('dropbox-refresh-token');
        this.saveBtn = document.getElementById('save-dropbox-settings');
        this.syncEbookBtn = document.getElementById('sync-ebook-btn');
        this.syncMusicBtn = document.getElementById('sync-music-btn');
        this.logOutput = document.getElementById('dropbox-log-output');

        if (!this.appKeyInput) return;

        this.bindEvents();
        this.loadSettings();
    },

    bindEvents() {
        this.saveBtn.addEventListener('click', () => this.saveSettings());
        this.syncEbookBtn.addEventListener('click', () => this.runSync('ebook'));
        this.syncMusicBtn.addEventListener('click', () => this.runSync('music'));
    },

    async loadSettings() {
        try {
            const response = await fetch('/api/dropbox/settings');
            const data = await response.json();
            
            if (data.app_key) this.appKeyInput.value = data.app_key;
            if (data.app_secret) this.appSecretInput.value = data.app_secret;
            if (data.refresh_token) this.refreshTokenInput.value = data.refresh_token;
        } catch (error) {
            console.error('Failed to load Dropbox settings:', error);
        }
    },

    async saveSettings() {
        const settings = {
            app_key: this.appKeyInput.value.trim(),
            app_secret: this.appSecretInput.value.trim(),
            refresh_token: this.refreshTokenInput.value.trim()
        };

        try {
            this.saveBtn.disabled = true;
            this.saveBtn.textContent = 'Saving...';

            const response = await fetch('/api/dropbox/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                alert('Settings saved successfully!');
            } else {
                throw new Error('Failed to save settings');
            }
        } catch (error) {
            alert('Error saving settings: ' + error.message);
        } finally {
            this.saveBtn.disabled = false;
            this.saveBtn.textContent = 'Save Settings';
        }
    },

    async runSync(target) {
        if (!this.appKeyInput.value.trim() || !this.appSecretInput.value.trim() || !this.refreshTokenInput.value.trim()) {
            alert('Please save your Dropbox settings first!');
            return;
        }

        const button = target === 'ebook' ? this.syncEbookBtn : this.syncMusicBtn;
        
        try {
            this.syncEbookBtn.disabled = true;
            this.syncMusicBtn.disabled = true;
            const originalText = button.textContent;
            button.textContent = `Syncing ${target}...`;
            
            this.logOutput.textContent = `Starting ${target} sync...\n`;

            const response = await fetch('/api/dropbox/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const text = decoder.decode(value);
                this.logOutput.textContent += text;
                this.logOutput.scrollTop = this.logOutput.scrollHeight;
            }

            button.textContent = originalText;
        } catch (error) {
            this.logOutput.textContent += `\nError: ${error.message}`;
        } finally {
            this.syncEbookBtn.disabled = false;
            this.syncMusicBtn.disabled = false;
            button.textContent = target === 'ebook' ? 'Sync eBook' : 'Sync Music';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    DropboxManager.init();
});