import { api } from './api.js';

export const assEditor = {
    modal: null,
    titleEl: null,
    offsetInput: null,
    offsetDisplay: null,
    previewSection: null,
    previewBody: null,
    previewSummary: null,
    contentEditor: null,
    currentFile: null,
    originalContent: null,
    currentOffset: 0,

    init() {
        this.modal = document.getElementById('ass-editor-modal');
        this.titleEl = document.getElementById('ass-editor-title');
        this.offsetInput = document.getElementById('ass-offset-input');
        this.offsetDisplay = document.getElementById('ass-offset-display');
        this.previewSection = document.getElementById('ass-preview-section');
        this.previewBody = document.getElementById('ass-preview-body');
        this.previewSummary = document.getElementById('ass-preview-summary');
        this.contentEditor = document.getElementById('ass-content-editor');

        // Close button
        const closeBtn = document.getElementById('close-ass-editor');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }

        // Offset buttons
        document.getElementById('ass-minus-10')?.addEventListener('click', () => this.adjustOffset(-10));
        document.getElementById('ass-minus-1')?.addEventListener('click', () => this.adjustOffset(-1));
        document.getElementById('ass-plus-1')?.addEventListener('click', () => this.adjustOffset(1));
        document.getElementById('ass-plus-10')?.addEventListener('click', () => this.adjustOffset(10));

        // Offset input change
        this.offsetInput?.addEventListener('change', () => {
            this.currentOffset = parseFloat(this.offsetInput.value) || 0;
            this.updateOffsetDisplay();
        });

        // Preview button
        document.getElementById('ass-preview-btn')?.addEventListener('click', () => this.previewOffset());

        // Reset button
        document.getElementById('ass-reset-btn')?.addEventListener('click', () => this.reset());

        // Save button
        document.getElementById('ass-save-btn')?.addEventListener('click', () => this.save());

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal && !this.modal.classList.contains('hidden')) {
                this.close();
            }
        });
    },

    async open(file) {
        if (!this.modal) this.init();

        this.currentFile = file;
        this.currentOffset = 0;
        this.originalContent = null;

        if (this.titleEl) this.titleEl.textContent = file.name;
        if (this.offsetInput) this.offsetInput.value = '0';
        if (this.contentEditor) this.contentEditor.value = 'Loading...';
        if (this.previewSection) this.previewSection.classList.add('hidden');
        this.updateOffsetDisplay();

        this.modal?.classList.remove('hidden');

        // Load file content
        try {
            const result = await api.readAssFile(file.path);
            this.originalContent = result.content;
            if (this.contentEditor) {
                this.contentEditor.value = result.content;
            }
        } catch (err) {
            console.error('Error loading ASS file:', err);
            if (this.contentEditor) {
                this.contentEditor.value = `Error loading file: ${err.message}`;
            }
            alert('Error loading ASS file: ' + err.message);
        }
    },

    close() {
        if (this.modal) {
            this.modal.classList.add('hidden');
        }
        this.currentFile = null;
        this.originalContent = null;
        this.currentOffset = 0;
    },

    adjustOffset(delta) {
        this.currentOffset = (parseFloat(this.offsetInput?.value) || 0) + delta;
        if (this.offsetInput) this.offsetInput.value = this.currentOffset.toFixed(1);
        this.updateOffsetDisplay();
        this.previewOffset();
    },

    updateOffsetDisplay() {
        if (this.offsetDisplay) {
            const sign = this.currentOffset >= 0 ? '+' : '';
            this.offsetDisplay.textContent = `Current offset: ${sign}${this.currentOffset}s`;
        }
    },

    async previewOffset() {
        if (!this.currentFile) return;

        if (this.currentOffset === 0) {
            if (this.previewSection) this.previewSection.classList.add('hidden');
            return;
        }

        try {
            const result = await api.previewAssOffset(this.currentFile.path, this.currentOffset);
            this.showPreview(result);
        } catch (err) {
            console.error('Error previewing offset:', err);
            alert('Error previewing offset: ' + err.message);
        }
    },

    showPreview(result) {
        if (!this.previewSection || !this.previewBody || !this.previewSummary) return;

        this.previewBody.innerHTML = '';

        if (result.preview && result.preview.length > 0) {
            result.preview.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${item.index}</td>
                    <td>${this.escapeHtml(item.original)}</td>
                    <td>${this.escapeHtml(item.modified)}</td>
                `;
                this.previewBody.appendChild(tr);
            });

            this.previewSummary.textContent = `Showing first ${result.preview.length} of ${result.total_dialogues} dialogue lines. Offset: ${result.offset >= 0 ? '+' : ''}${result.offset}s`;
            this.previewSection.classList.remove('hidden');
        } else {
            this.previewSummary.textContent = 'No dialogue lines found to preview.';
            this.previewSection.classList.remove('hidden');
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    reset() {
        if (this.contentEditor && this.originalContent !== null) {
            this.contentEditor.value = this.originalContent;
        }
        this.currentOffset = 0;
        if (this.offsetInput) this.offsetInput.value = '0';
        if (this.previewSection) this.previewSection.classList.add('hidden');
        this.updateOffsetDisplay();
    },

    async save() {
        if (!this.currentFile) return;

        const content = this.contentEditor?.value || '';
        const offset = this.currentOffset;

        if (offset === 0) {
            // Just save the raw content
            try {
                await api.saveAssFile(this.currentFile.path, content, 0);
                alert('File saved successfully!');
                this.close();
            } catch (err) {
                console.error('Error saving ASS file:', err);
                alert('Error saving file: ' + err.message);
            }
        } else {
            // Confirm with offset
            const sign = offset >= 0 ? '+' : '';
            const confirmMsg = `Save with ${sign}${offset}s time offset? This will modify all subtitle timings.`;
            if (!confirm(confirmMsg)) return;

            try {
                // Pass null for content since we want backend to read and apply offset
                await api.saveAssFile(this.currentFile.path, null, offset);
                alert('File saved successfully with time offset applied!');
                this.close();
            } catch (err) {
                console.error('Error saving ASS file:', err);
                alert('Error saving file: ' + err.message);
            }
        }
    }
};
