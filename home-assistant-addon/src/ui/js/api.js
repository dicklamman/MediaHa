export const api = {
    // ASS Subtitle Files
    async readAssFile(fileName) {
        const response = await fetch('/api/ass/read?file_name=' + encodeURIComponent(fileName));
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to read ASS file');
        }
        return await response.json();
    },
    async saveAssFile(fileName, content, offset = 0) {
        const response = await fetch('/api/ass/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: fileName, content: content, offset: offset })
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to save ASS file');
        }
        return await response.json();
    },
    async previewAssOffset(fileName, offset) {
        const response = await fetch('/api/ass/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: fileName, offset: offset })
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to preview ASS offset');
        }
        return await response.json();
    },

    async getFiles(dir) {
        const response = await fetch('/api/files?dir=' + encodeURIComponent(dir));
        if (response.status === 401) {
            window.location.href = '/login.html';
            return [];
        }
        if (!response.ok) throw new Error('Failed to load files');
        return await response.json();
    },
    async renameFile(old_path, new_name) {
        const response = await fetch('/api/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_path, new_name }),
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Rename failed');
        }
        return await response.json();
    },
    async getMetadata(path) {
        const response = await fetch('/api/metadata?file_name=' + encodeURIComponent(path));
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to load metadata');
        return await response.json();
    },
    async updateMetadata(path, data) {
        const response = await fetch('/api/metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: path, ...data })
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to update metadata');
        return await response.json();
    },
    async enhanceMp3(path, offset = 0, coverSource = 'all') {
        const response = await fetch('/api/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: path, offset: offset, cover_source: coverSource })
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to enhance MP3');
        return await response.json();
    },
    async convertFile(path) {
        const response = await fetch('/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: path }),
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Conversion failed');
        }
        return await response.json();
    },

    // Calibre Web Sync
    async getCalibreSettings() {
        const response = await fetch('/api/calibre/settings');
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to load Calibre settings');
        return await response.json();
    },
    async saveCalibreSettings(settings) {
        const response = await fetch('/api/calibre/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to save Calibre settings');
        return await response.json();
    },
    async syncCalibre(onLog) {
        const response = await fetch('/api/calibre/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (response.status === 401) {
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Sync failed');
        }

        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            // Parse each line as JSON
            const lines = chunk.split('\n').filter(line => line.trim());
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    if (onLog) onLog(data);
                } catch (e) {
                    // Skip invalid JSON
                }
            }
        }

        return { success: true };
    }
};
