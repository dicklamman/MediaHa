export const api = {
    async getFiles(dir) {
        const response = await fetch('/api/files?dir=' + encodeURIComponent(dir));
        if (!response.ok) throw new Error('Failed to load files');
        return await response.json();
    },
    async renameFile(old_path, new_name) {
        const response = await fetch('/api/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_path, new_name }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Rename failed');
        }
        return await response.json();
    },
    async convertFile(path) {
        const response = await fetch('/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_name: path }),
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Conversion failed');
        }
        return await response.json();
    }
};
