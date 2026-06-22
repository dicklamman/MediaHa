import { api } from './api.js';

export const alist = {
    isRunning: false,

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

    setButtonState(running) {
        this.isRunning = running;
        const btnRun = document.getElementById('run-alist');
        if (btnRun) {
            btnRun.disabled = running;
            btnRun.textContent = running ? 'Running...' : 'Run Generator';
            btnRun.classList.toggle('btn-running', running);
        }
    },

    async runGenerator() {
        if (this.isRunning) return;

        const logBox = document.getElementById('alist-log');
        if (!logBox) {
            console.error('alist-log element not found');
            return;
        }

        this.setButtonState(true);
        logBox.textContent = "Starting AList STRM Generator...\n";
        logBox.style.display = 'block';
        logBox.style.visibility = 'visible';
        logBox.style.minHeight = '300px';
        logBox.style.opacity = '1';

        try {
            const res = await fetch('/api/alist/run', { method: 'POST' });
            
            if (!res.ok) {
                logBox.textContent += `Error: HTTP ${res.status}\n`;
                this.setButtonState(false);
                return;
            }

            if (!res.body) {
                logBox.textContent += "Error: No response body (streaming not supported)\n";
                this.setButtonState(false);
                return;
            }

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
        } finally {
            this.setButtonState(false);
        }
    }
};
