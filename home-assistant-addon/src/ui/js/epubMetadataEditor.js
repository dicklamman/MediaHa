// EPUB Metadata Editor Module

// Store current file path globally for the save button
window.currentEpubFile = null;

export const epubMetadataEditor = {
    currentFile: null,
    api: null,

    open(file, apiInstance) {
        this.currentFile = file;
        this.api = apiInstance;
        const modal = document.getElementById('epub-metadata-modal');
        if (!modal) {
            console.error('EPUB metadata modal not found');
            return;
        }

        // Store file path globally for save button
        window.currentEpubFile = file.path;

        // Load metadata
        this.loadMetadata();

        // Show modal
        modal.classList.remove('hidden');
    },

    async loadMetadata() {
        if (!this.currentFile || !this.api) return;

        try {
            const metadata = await this.api.getEpubMetadata(this.currentFile.path);

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

            // Display cover image
            const coverImg = document.getElementById('epub-cover');
            const coverPlaceholder = document.getElementById('epub-cover-placeholder');
            if (metadata.cover) {
                coverImg.src = 'data:image/jpeg;base64,' + metadata.cover;
                coverImg.classList.remove('hidden');
                if (coverPlaceholder) coverPlaceholder.classList.add('hidden');
            } else {
                coverImg.classList.add('hidden');
                if (coverPlaceholder) coverPlaceholder.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Failed to load EPUB metadata:', error);
            if (typeof ui !== 'undefined' && ui.showResultMessage) {
                ui.showResultMessage('error', 'Failed to load metadata: ' + error.message);
            }
        }
    },

    async saveMetadata() {
        if (!this.currentFile || !this.api) return;

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
            await this.api.saveEpubMetadata(this.currentFile.path, metadata);
            if (typeof ui !== 'undefined' && ui.showResultMessage) {
                ui.showResultMessage('success', 'Metadata saved successfully');
            }
            this.close();
        } catch (error) {
            console.error('Failed to save EPUB metadata:', error);
            if (typeof ui !== 'undefined' && ui.showResultMessage) {
                ui.showResultMessage('error', 'Failed to save metadata: ' + error.message);
            }
        }
    },

    close() {
        const modal = document.getElementById('epub-metadata-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        this.currentFile = null;
        window.currentEpubFile = null;

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
    const modal = document.getElementById('epub-metadata-modal');

    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            epubMetadataEditor.close();
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            epubMetadataEditor.close();
        });
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            epubMetadataEditor.saveMetadata();
        });
    }

    // Close modal when clicking on overlay
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                epubMetadataEditor.close();
            }
        });
    }
});
