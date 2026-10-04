import { api } from './api.js';

export const onelist = {
    isRunning: false,

    async init() {
        const btnSave = document.getElementById('save-onelist');
        const btnRun = document.getElementById('run-onelist');

        if (btnSave && btnRun) {
            btnSave.addEventListener('click', () => this.saveSettings());
            btnRun.addEventListener('click', () => this.runGenerator());
            await this.loadSettings();
        }
    },

    async loadSettings() {
        try {
            const res = await fetch('/api/onelist/settings');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('onelist-url').value = data.alist_url || '';
                document.getElementById('onelist-domain').value = data.public_domain || '';
                document.getElementById('onelist-remote').value = data.remote_path || '';
                document.getElementById('onelist-local').value = data.local_dir || '';
                document.getElementById('onelist-user').value = data.username || '';
                document.getElementById('onelist-pass').value = data.password || '';
            }
        } catch (e) {
            console.error('Failed to load settings', e);
        }
    },

    async saveSettings() {
        const data = {
            alist_url: document.getElementById('onelist-url').value,
            public_domain: document.getElementById('onelist-domain').value,
            remote_path: document.getElementById('onelist-remote').value,
            local_dir: document.getElementById('onelist-local').value,
            username: document.getElementById('onelist-user').value,
            password: document.getElementById('onelist-pass').value
        };

        try {
            const res = await fetch('/api/onelist/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const status = document.getElementById('onelist-status');
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
        const btnRun = document.getElementById('run-onelist');
        if (btnRun) {
            btnRun.disabled = running;
            btnRun.textContent = running ? 'Running...' : 'Run Generator';
            btnRun.classList.toggle('btn-running', running);
        }
    },

    async runGenerator() {
        if (this.isRunning) return;

        const logBox = document.getElementById('onelist-log');
        if (!logBox) {
            console.error('onelist-log element not found');
            return;
        }

        this.setButtonState(true);
        logBox.textContent = "Starting OneList STRM Generator...\n";
        logBox.style.display = 'block';
        logBox.style.visibility = 'visible';
        logBox.style.minHeight = '300px';
        logBox.style.opacity = '1';

        try {
            const res = await fetch('/api/onelist/run', { method: 'POST' });
            
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
