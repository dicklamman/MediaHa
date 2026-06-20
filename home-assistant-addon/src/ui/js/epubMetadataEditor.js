// EPUB Metadata Editor Module

export const epubMetadataEditor = {
    currentFile: null,

    open(file, api) {
        this.currentFile = file;
        const modal = document.getElementById('epub-metadata-modal');
        if (!modal) return;

        // Load metadata
        this.loadMetadata(api);

        // Show modal
        modal.classList.remove('hidden');
    },

    async loadMetadata(api) {
        if (!this.currentFile) return;

        try {
            const metadata = await api.getEpubMetadata(this.currentFile.path);

            // Fill form fields
            document.getElementById('epub-title').value = metadata.title || '';
            document.getElementById('epub-creator').value = metadata.creator || '';
            document.getElementById('epub-publisher').value = metadata.publisher || '';
            document.getElementById('epub-language').value = metadata.language || '';
            document.getElementById('epub-description').value = metadata.description || '';
            document.getElementById('epub-identifier').value = metadata.identifier || '';
            document.getElementById('epub-date').value = metadata.date || '';
            document.getElementById('epub-rights').value = metadata.rights || '';
            document.getElementById('epub-subjects').value = Array.isArray(metadata.subjects) ? metadata.subjects.join(', ') : (metadata.subjects || '');
        } catch (error) {
            console.error('Failed to load EPUB metadata:', error);
            ui.showResultMessage('error', 'Failed to load metadata: ' + error.message);
        }
    },

    async saveMetadata(api) {
        if (!this.currentFile) return;

        const metadata = {
            title: document.getElementById('epub-title').value,
            creator: document.getElementById('epub-creator').value,
            publisher: document.getElementById('epub-publisher').value,
            language: document.getElementById('epub-language').value,
            description: document.getElementById('epub-description').value,
            identifier: document.getElementById('epub-identifier').value,
            date: document.getElementById('epub-date').value,
            rights: document.getElementById('epub-rights').value,
            subjects: document.getElementById('epub-subjects').value.split(',').map(s => s.trim()).filter(s => s)
        };

        try {
            await api.saveEpubMetadata(this.currentFile.path, metadata);
            ui.showResultMessage('success', 'Metadata saved successfully');
            this.close();
        } catch (error) {
            console.error('Failed to save EPUB metadata:', error);
            ui.showResultMessage('error', 'Failed to save metadata: ' + error.message);
        }
    },

    close() {
        const modal = document.getElementById('epub-metadata-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        this.currentFile = null;

        // Clear form
        const fields = ['epub-title', 'epub-creator', 'epub-publisher', 'epub-language',
            'epub-description', 'epub-identifier', 'epub-date', 'epub-rights', 'epub-subjects'];
        fields.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
    }
};

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-epub-metadata');
    const cancelBtn = document.getElementById('cancel-epub-metadata');
    const saveBtn = document.getElementById('save-epub-metadata');

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            epubMetadataEditor.close();
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            epubMetadataEditor.close();
        });
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            // Use global api variable from main.js
            epubMetadataEditor.saveMetadata(window.api || api);
        });
    }
});
