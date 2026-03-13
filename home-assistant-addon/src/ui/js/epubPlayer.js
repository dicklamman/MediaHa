export const epubPlayer = {
    book: null,
    rendition: null,

    init() {
        const closePreviewBtn = document.getElementById('close-preview');
        const prevPageBtn = document.getElementById('prev-page');
        const nextPageBtn = document.getElementById('next-page');

        if (closePreviewBtn) closePreviewBtn.addEventListener('click', () => this.close());
        if (prevPageBtn) prevPageBtn.addEventListener('click', () => { if (this.rendition) this.rendition.prev(); });
        if (nextPageBtn) nextPageBtn.addEventListener('click', () => { if (this.rendition) this.rendition.next(); });

        window.addEventListener('themeChanged', (e) => this.updateTheme(e.detail.theme));
    },

    open(file) {
        if (!file || file.type === 'folder') return;
        
        const previewModal = document.getElementById('preview-modal');
        const previewContent = document.getElementById('preview-content');
        const previewTitle = document.getElementById('preview-title');
        
        previewTitle.textContent = file.name;
        previewModal.classList.remove('hidden');
        previewContent.innerHTML = '<div style="padding:20px;text-align:center;">Loading preview...</div>';

        const fileUrl = '/api/download?file_name=' + encodeURIComponent(file.path);
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        
        this.book = window.ePub(fileUrl);
        previewContent.innerHTML = '';
        this.rendition = this.book.renderTo(previewContent, {
            width: "100%",
            height: "100%",
            spread: "none"
        });
        
        this.updateTheme(currentTheme);
        this.rendition.display();
    },

    updateTheme(theme) {
        if (!this.rendition) return;
        if (theme === 'dark') {
            this.rendition.themes.register("dark", {
                "body": { "background": "#2d2d2d", "color": "#e0e0e0" }
            });
            this.rendition.themes.select("dark");
        } else {
            this.rendition.themes.register("light", {
                "body": { "background": "white", "color": "#333" }
            });
            this.rendition.themes.select("light");
        }
    },

    close() {
        const previewModal = document.getElementById('preview-modal');
        const previewContent = document.getElementById('preview-content');
        if(previewModal) previewModal.classList.add('hidden');
        if (this.book) {
            this.book.destroy();
            this.book = null;
            this.rendition = null;
        }
        if(previewContent) previewContent.innerHTML = '';
    }
};
