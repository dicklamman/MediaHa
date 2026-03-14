import { api } from './api.js';

export const videoPlayer = {
    init() {
        this.modal = document.getElementById('video-modal');
        this.player = document.getElementById('video-player');
        this.title = document.getElementById('video-title');
        this.closeBtn = document.getElementById('close-video');
        
        this.errorOverlay = document.getElementById('video-error-overlay');
        this.btnDirect = document.getElementById('video-link-direct');
        this.btnCopy = document.getElementById('video-btn-copy');
        this.btnPot = document.getElementById('video-link-pot');
        this.btnVlc = document.getElementById('video-link-vlc');
        this.btnIina = document.getElementById('video-link-iina');

        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }

        if (this.player) {
            this.player.addEventListener('error', () => {
                const err = this.player.error;
                if (err && this.player.src && this.player.src.trim() !== '') {
                    console.log('Video Player Error:', err.code, err.message);
                    if (this.errorOverlay) this.errorOverlay.classList.remove('hidden');
                }
            });
        }

        if (this.btnCopy) {
            this.btnCopy.addEventListener('click', () => {
                if (this.currentUrl) {
                    navigator.clipboard.writeText(this.currentUrl).then(() => {
                        const original = this.btnCopy.textContent;
                        this.btnCopy.textContent = 'Copied!';
                        setTimeout(() => this.btnCopy.textContent = original, 2000);
                    });
                }
            });
        }
    },

    setupLinks(url) {
        this.currentUrl = url;
        if (this.btnDirect) this.btnDirect.href = url;
        if (this.btnPot) this.btnPot.href = 'potplayer://' + url;
        if (this.btnVlc) this.btnVlc.href = 'vlc://' + url;
        if (this.btnIina) this.btnIina.href = 'iina://weblink?url=' + encodeURIComponent(url);
        if (this.errorOverlay) this.errorOverlay.classList.add('hidden');
    },

    async open(file) {
        if (!this.modal || !this.player) return;

        this.title.textContent = file.name;
        this.modal.classList.remove('hidden');
        if (this.errorOverlay) this.errorOverlay.classList.add('hidden');

        try {
            let streamUrl = '';
            if (file.name.toLowerCase().endsWith('.strm')) {
                const res = await fetch('/api/download?file_name=' + encodeURIComponent(file.path));
                if (res.ok) {
                    streamUrl = (await res.text()).trim();
                } else {
                    alert('Failed to load stream URL');
                    return;
                }
            } else {
                // Determine direct route for internal testing
                // If it's pure MP4, play it directly from backend route
                streamUrl = window.location.origin + '/api/download?file_name=' + encodeURIComponent(file.path);
            }

            this.setupLinks(streamUrl);
            this.player.src = streamUrl;
            
            this.player.play().catch(e => {
                console.log('Autoplay play() catch:', e.name, e);
                if (e.name === 'NotSupportedError') {
                    if (this.errorOverlay) this.errorOverlay.classList.remove('hidden');
                }
            });
            
        } catch (e) {
            console.error('Error opening video', e);
        }
    },

    close() {
        if (this.modal) {
            this.modal.classList.add('hidden');
        }
        if (this.player) {
            this.player.pause();
            this.player.removeAttribute('src'); // Clean up source to stop downloading
            this.player.load();
        }
    }
};