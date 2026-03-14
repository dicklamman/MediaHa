const fs = require('fs');

let html = fs.readFileSync('home-assistant-addon/src/ui/index.html', 'utf8');
const oldHtml = `        <div id="video-content" style="flex: 1; background: #000; display: flex; justify-content: center; align-items: center;">
            <video id="video-player" controls style="max-width: 100%; max-height: 100%; width: 100%;"></video>
        </div>
    </div>`;
const newHtml = `        <div id="video-content" style="flex: 1; background: #000; display: flex; justify-content: center; align-items: center; position: relative;">
            <video id="video-player" controls style="max-width: 100%; max-height: 100%; width: 100%;"></video>
            <div id="video-error-overlay" class="hidden" style="position: absolute; text-align: center; color: white; background: rgba(0,0,0,0.8); padding: 30px; border-radius: 12px; max-width: 80%;">
                <h3 style="margin-top:0; color: #ffeb3b;">Video Format Not Supported</h3>
                <p>Your browser cannot natively play this video format (e.g. MKV/AVI).</p>
                <p>Please use the direct links below to open it in an external player.</p>
            </div>
        </div>
        <div id="video-actions" style="padding: 10px 15px; background: var(--modal-header-bg); text-align: center; border-top: 1px solid var(--border-color); display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;">
            <a id="video-link-direct" href="#" target="_blank" class="btn" style="text-decoration:none; display:inline-block; font-size: 0.9em; padding: 6px 12px;">Open Direct Link</a>
            <button id="video-btn-copy" class="btn" style="font-size: 0.9em; padding: 6px 12px; background: #6c757d;">Copy URL</button>
            <a id="video-link-pot" href="#" class="btn" style="text-decoration:none; display:inline-block; background:#fbc02d; color:#000; font-size: 0.9em; padding: 6px 12px;">PotPlayer</a>
            <a id="video-link-vlc" href="#" class="btn" style="text-decoration:none; display:inline-block; background:#ff8800; font-size: 0.9em; padding: 6px 12px;">VLC</a>
            <a id="video-link-iina" href="#" class="btn" style="text-decoration:none; display:inline-block; background:#000; font-size: 0.9em; padding: 6px 12px;">IINA</a>
        </div>
    </div>`;

html = html.replace(oldHtml, newHtml);
fs.writeFileSync('home-assistant-addon/src/ui/index.html', html);

let js = `import { api } from './api.js';

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
};`;
fs.writeFileSync('home-assistant-addon/src/ui/js/videoPlayer.js', js);
