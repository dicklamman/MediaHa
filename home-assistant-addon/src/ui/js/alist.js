import { api } from './api.js';

export const alist = {
    async init() {
        const btnSave = document.getElementById('save-alist');
        const btnRun = document.getElementById('run-alist');

        if (btnSave && btnRun) {
            btnSave.addEventListener('click', () => this.saveSettings());
            btnRun.addEventListener('click', () => this.runGenerator());
            await this.loadSettings();
        }
    },

    async loadSettings() {
        try {
            const res = await fetch('/api/alist/settings');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('alist-url').value = data.alist_url || '';
                document.getElementById('alist-domain').value = data.public_domain || '';
                document.getElementById('alist-remote').value = data.remote_path || '';
                document.getElementById('alist-local').value = data.local_dir || '';
                document.getElementById('alist-user').value = data.username || '';
                document.getElementById('alist-pass').value = data.password || '';
            }
        } catch (e) {
            console.error('Failed to load settings', e);
        }
    },

    async saveSettings() {
        const data = {
            alist_url: document.getElementById('alist-url').value,
            public_domain: document.getElementById('alist-domain').value,
            remote_path: document.getElementById('alist-remote').value,
            local_dir: document.getElementById('alist-local').value,
            username: document.getElementById('alist-user').value,
            password: document.getElementById('alist-pass').value
        };

        try {
            const res = await fetch('/api/alist/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const status = document.getElementById('alist-status');
            if (res.ok) {
                status.textContent = 'Settings saved successfully!';
                status.style.color = '#28a745';
            } else {
                status.textContent = 'Failed to save settings.';
                status.style.color = 'red';
            }
            setTimeout(() => status.textContent = '', 3000);
        } catch (e) {
            console.error('Failed to save', e);
        }
    },

    async runGenerator() {
        const logBox = document.getElementById('alist-log');
        logBox.textContent = "Starting AList STRM Generator...\n";
        
        // Save settings first just in case
        await this.saveSettings();

        try {
            const res = await fetch('/api/alist/run', { method: 'POST' });
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                logBox.textContent += decoder.decode(value);
                logBox.scrollTop = logBox.scrollHeight;
            }
            logBox.textContent += "\nGenerator finished.";
        } catch (e) {
            logBox.textContent += `\nError: ${e.message}`;
        }
    }
};
