export const mediaPreview = {
    init() {
        const closeBtn = document.getElementById('close-preview');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
    },

    setupContextMenu() {
        // Context menu setup will be handled by file browser
    },

    open(file) {
        const previewModal = document.getElementById('preview-modal');
        const previewContent = document.getElementById('preview-content');
        const previewTitle = document.getElementById('preview-title');

        if (!previewModal || !previewContent || !previewTitle) {
            console.error('Preview modal elements not found');
            return;
        }

        const prevPageBtn = document.getElementById('prev-page');
        const nextPageBtn = document.getElementById('next-page');

        if (prevPageBtn) prevPageBtn.style.display = 'none';
        if (nextPageBtn) nextPageBtn.style.display = 'none';

        previewTitle.textContent = file.name;
        previewModal.classList.remove('hidden');
        previewContent.innerHTML = '<div style="padding:20px;text-align:center;"><span class="spinner"></span> Loading preview...</div>';

        const fileUrl = '/api/download?file_name=' + encodeURIComponent(file.path);
        const ext = file.name.toLowerCase().split('.').pop();

        const isImage = ['jpg', 'jpeg', 'png', 'gif'].includes(ext);
        const isText = ['lrc', 'txt', 'md', 'json'].includes(ext);

        if (isImage) {
            previewContent.innerHTML = `<div style="display:flex;justify-content:center;align-items:center;height:100%;padding:10px;box-sizing:border-box;"><img src="${fileUrl}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;" /></div>`;
        } else if (isText) {
            fetch(fileUrl)
                .then(res => res.text())
                .then(text => {
                    previewContent.innerHTML = `<pre style="white-space:pre-wrap;word-wrap:break-word;padding:15px;overflow-y:auto;height:100%;box-sizing:border-box;margin:0;font-family:monospace;font-size:14px;background:var(--bg-color);color:var(--text-color);">${text}</pre>`;
                })
                .catch(err => {
                    previewContent.innerHTML = `<div style="color:red;padding:20px;text-align:center;">Failed to load file: ${err.message}</div>`;
                });
        } else {
            previewContent.innerHTML = `<div style="padding:20px;text-align:center;">No preview available for this file type.</div>`;
        }
    },

    close() {
        const previewModal = document.getElementById('preview-modal');
        const previewContent = document.getElementById('preview-content');
        if (previewModal) previewModal.classList.add('hidden');
        if (previewContent) previewContent.innerHTML = '';
    }
};
