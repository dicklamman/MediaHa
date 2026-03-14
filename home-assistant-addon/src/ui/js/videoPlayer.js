import { api } from './api.js';

export const videoPlayer = {
    init() {
        this.modal = document.getElementById('video-modal');
        this.player = document.getElementById('video-player');
        this.title = document.getElementById('video-title');
        this.closeBtn = document.getElementById('close-video');

        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
    },

    async open(file) {
        if (!this.modal || !this.player) return;

        this.title.textContent = file.name;
        this.modal.classList.remove('hidden');

        try {
            if (file.name.toLowerCase().endsWith('.strm')) {
                // Re-fetch the strm file content directly from the server
                const res = await fetch(`/api/download?file_name=${encodeURIComponent(file.path)}`);
                if (res.ok) {
                    const streamUrl = await res.text();
                    this.player.src = streamUrl.trim();
                    this.player.play().catch(e => console.log('Autoplay blocked', e));
                } else {
                    alert('Failed to load stream URL');
                }
            } else {
                // If it's pure MP4, play it directly from backend route
                this.player.src = `/api/download?file_name=${encodeURIComponent(file.path)}`;
                this.player.play().catch(e => console.log('Autoplay blocked', e));
            }
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
            this.player.src = ''; // Clean up source to stop downloading
        }
    }
};
