export const mp3Player = {
    currentFile: null,
    api: null,
    pendingCover: null,
    lrcData: [],
    activeIndex: -1,

    init() {
        const closeMp3Btn = document.getElementById('close-mp3');
        if (closeMp3Btn) closeMp3Btn.addEventListener('click', () => this.close());

        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');
        const cancelBtn = document.getElementById('cancel-metadata-btn');
        const autoEnhanceBtn = document.getElementById('auto-enhance-btn');

        if (editBtn) editBtn.addEventListener('click', () => this.toggleEditMode(true));
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveMetadata());
        if (cancelBtn) cancelBtn.addEventListener('click', () => {
            this.pendingCover = null;
            this.toggleEditMode(false);
            this.loadMetadata(); // revert inputs to current saved metadata
        });
        if (autoEnhanceBtn) autoEnhanceBtn.addEventListener('click', () => this.autoEnhance());

        const mp3Audio = document.getElementById('mp3-audio');
        if (mp3Audio) {
            mp3Audio.addEventListener('timeupdate', () => this.updateSyncedLyrics(mp3Audio.currentTime));
        }

        // Revert buttons logic
        document.querySelectorAll('.revert-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const field = btn.getAttribute('data-field');
                if (!this.originalMetadata) return;
                
                const isReverting = btn.textContent === 'Revert to Existing';

                if (isReverting) {
                    // Revert to original
                    if (field === 'cover') {
                        this.pendingCover = null;
                        const mp3Cover = document.getElementById('mp3-cover');
                        if (this.originalMetadata.cover) {
                            mp3Cover.src = this.originalMetadata.cover;
                            mp3Cover.style.display = 'block';
                        } else {
                            if (mp3Cover) mp3Cover.style.display = 'none';
                        }
                    } else if (field === 'lyrics') {
                        document.getElementById('meta-input-lyrics').value = this.originalMetadata.lyrics || '';
                    } else {
                        document.getElementById('meta-input-' + field).value = this.originalMetadata[field] || '';
                    }
                    btn.textContent = 'Restore Enhanced Version';
                    btn.style.background = '#28a745'; // green to match enhance
                } else {
                    // Restore enhanced
                    if (!this.enhancedMetadata) return;
                    if (field === 'cover') {
                        this.pendingCover = this.enhancedMetadata.cover;
                        const mp3Cover = document.getElementById('mp3-cover');
                        if (this.enhancedMetadata.cover) {
                            mp3Cover.src = this.enhancedMetadata.cover;
                            mp3Cover.style.display = 'block';
                        }
                    } else if (field === 'lyrics') {
                        document.getElementById('meta-input-lyrics').value = this.enhancedMetadata.lyrics || '';
                    } else {
                        document.getElementById('meta-input-' + field).value = this.enhancedMetadata[field] || '';
                    }
                    btn.textContent = 'Revert to Existing';
                    btn.style.background = '#6c757d'; // grey for revert
                }
            });
        });
    },

    async open(file, apiInstance) {
        if (!file || file.type === 'folder') return;
        this.currentFile = file;
        this.api = apiInstance || window.api; 
        this.pendingCover = null;

        const mp3Modal = document.getElementById('mp3-modal');
        const mp3Title = document.getElementById('mp3-title');
        const mp3Audio = document.getElementById('mp3-audio');
        const mp3Cover = document.getElementById('mp3-cover');
        const mp3Lyrics = document.getElementById('mp3-lyrics');

        this.toggleEditMode(false);

        if (mp3Modal && mp3Title && mp3Audio) {
            mp3Title.textContent = file.name;
            const fileUrl = '/api/download?file_name=' + encodeURIComponent(file.path);
            
            mp3Audio.src = fileUrl;

            if (mp3Cover) {
                mp3Cover.src = '';
                mp3Cover.style.display = 'none';
            }
            if (mp3Lyrics) mp3Lyrics.textContent = 'Loading metadata...';

            document.getElementById('meta-disp-title').textContent = 'Loading...';
            document.getElementById('meta-disp-artist').textContent = 'Loading...';
            document.getElementById('meta-disp-album').textContent = 'Loading...';

            mp3Modal.classList.remove('hidden');
            mp3Audio.play().catch(e => console.log('Autoplay prevented', e));

            if (this.api) {
                await this.loadMetadata();
            }
        }
    },

    parseLRC(text) {
        if (!text) return [];
        const lines = text.split('\n');
        const parsed = [];
        const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/g;
        
        lines.forEach(line => {
            const matches = [...line.matchAll(timeRegex)];
            const textContent = line.replace(timeRegex, '').trim();
            if (matches.length > 0 && textContent) {
                matches.forEach(match => {
                    const m = parseInt(match[1], 10);
                    const s = parseInt(match[2], 10);
                    const ms = match[3].length === 2 ? parseInt(match[3], 10) * 10 : parseInt(match[3], 10);
                    const time = (m * 60) + s + (ms / 1000);
                    parsed.push({ time, text: textContent });
                });
            }
        });
        return parsed.sort((a, b) => a.time - b.time);
    },

    renderLyrics(text) {
        const lyricsDiv = document.getElementById('mp3-lyrics');
        if (!lyricsDiv) return;

        this.lrcData = this.parseLRC(text);
        this.activeIndex = -1;

        if (this.lrcData.length > 0) {
            lyricsDiv.classList.add('synced');
            lyricsDiv.innerHTML = '';
            this.lrcData.forEach((line, index) => {
                const p = document.createElement('p');
                p.textContent = line.text;
                p.id = 'lrc-line-' + index;
                lyricsDiv.appendChild(p);
            });
        } else {
            lyricsDiv.classList.remove('synced');
            lyricsDiv.textContent = text || 'No lyrics found for this item.';
        }
    },

    updateSyncedLyrics(currentTime) {
        if (!this.lrcData || this.lrcData.length === 0) return;
        
        let newIndex = -1;
        for (let i = 0; i < this.lrcData.length; i++) {
            if (currentTime >= this.lrcData[i].time) {
                newIndex = i;
            } else {
                break;
            }
        }

        if (newIndex !== this.activeIndex && newIndex !== -1) {
            if (this.activeIndex !== -1) {
                const oldEl = document.getElementById('lrc-line-' + this.activeIndex);
                if (oldEl) oldEl.classList.remove('active');
            }
            
            this.activeIndex = newIndex;
            const newEl = document.getElementById('lrc-line-' + this.activeIndex);
            if (newEl) {
                newEl.classList.add('active');
                
                const container = document.getElementById('mp3-lyrics');
                const scrollPos = newEl.offsetTop - container.offsetTop - (container.clientHeight / 2) + (newEl.clientHeight / 2);
                container.scrollTo({ top: scrollPos, behavior: 'smooth' });
            }
        }
    },

    async loadMetadata() {
        try {
            const metadata = await this.api.getMetadata(this.currentFile.path);
            this.originalMetadata = metadata; // Keep original
            document.querySelectorAll(".revert-btn").forEach(btn => btn.style.display = "none");

            // Populate Display
            document.getElementById('meta-disp-title').textContent = metadata.title || 'Unknown Title';
            document.getElementById('meta-disp-artist').textContent = metadata.artist || 'Unknown Artist';
            document.getElementById('meta-disp-album').textContent = metadata.album || 'Unknown Album';

            // Populate Inputs for editing
            document.getElementById('meta-input-title').value = metadata.title || '';
            document.getElementById('meta-input-artist').value = metadata.artist || '';
            document.getElementById('meta-input-album').value = metadata.album || '';
            document.getElementById('meta-input-lyrics').value = metadata.lyrics || '';

            const mp3Lyrics = document.getElementById('mp3-lyrics');
            this.renderLyrics(metadata.lyrics);

            const mp3Cover = document.getElementById('mp3-cover');
            if (metadata.cover) {
                mp3Cover.src = metadata.cover;
                mp3Cover.style.display = 'block';
            } else {
                if (mp3Cover) mp3Cover.style.display = 'none';
            }

            const mp3Title = document.getElementById('mp3-title');
            if (metadata.title) mp3Title.textContent = metadata.title + (metadata.artist ? ' - ' + metadata.artist : '');

        } catch (err) {
            document.getElementById('mp3-lyrics').textContent = 'Failed to load metadata.';
            console.error("Metadata error:", err);
        }
    },

    async autoEnhance() {
        if (!this.api || !this.currentFile) return;
        const autoBtn = document.getElementById('auto-enhance-btn');
        const originalText = autoBtn.textContent;
        autoBtn.textContent = 'Searching...';
        autoBtn.disabled = true;

        try {
            const data = await this.api.enhanceMp3(this.currentFile.path);
            this.enhancedMetadata = data;
            
            // Populate form with fetched data
            if (data.title) {
                document.getElementById('meta-input-title').value = data.title;
                const b = document.querySelector('.revert-btn[data-field="title"]'); b.style.display = "inline-block"; b.textContent = "Revert to Existing"; b.style.background = "#6c757d";
            }
            if (data.artist) {
                document.getElementById('meta-input-artist').value = data.artist;
                const b = document.querySelector('.revert-btn[data-field="artist"]'); b.style.display = "inline-block"; b.textContent = "Revert to Existing"; b.style.background = "#6c757d";
            }
            if (data.album) {
                document.getElementById('meta-input-album').value = data.album;
                const b = document.querySelector('.revert-btn[data-field="album"]'); b.style.display = "inline-block"; b.textContent = "Revert to Existing"; b.style.background = "#6c757d";
            }
            if (data.lyrics) {
                document.getElementById('meta-input-lyrics').value = data.lyrics;
                const b = document.querySelector('.revert-btn[data-field="lyrics"]'); b.style.display = "inline-block"; b.textContent = "Revert to Existing"; b.style.background = "#6c757d";
            }
            
            // Preview image
            if (data.cover) {
                this.pendingCover = data.cover;
                const b = document.querySelector('.revert-btn[data-field="cover"]'); b.style.display = "inline-block"; b.textContent = "Revert to Existing"; b.style.background = "#6c757d";
                const mp3Cover = document.getElementById('mp3-cover');
                if (mp3Cover) {
                    mp3Cover.src = data.cover;
                    mp3Cover.style.display = 'block';
                }
            }

            // Enter edit mode so user reviews and saves
            this.toggleEditMode(true);
            

        } catch(err) {
            alert('Failed to find enhancement data.');
            console.error(err);
        } finally {
            autoBtn.textContent = originalText;
            autoBtn.disabled = false;
        }
    },

    toggleEditMode(isEdit) {
        const displayDiv = document.getElementById('metadata-display');
        const editorDiv = document.getElementById('metadata-editor');
        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');
        const cancelBtn = document.getElementById('cancel-metadata-btn');
        const autoBtn = document.getElementById('auto-enhance-btn');
        const lyricsDiv = document.getElementById('mp3-lyrics');

        if (isEdit) {
            displayDiv.classList.add('hidden');
            editorDiv.classList.remove('hidden');
            editBtn.classList.add('hidden');
            if (autoBtn) autoBtn.classList.add('hidden');
            saveBtn.classList.remove('hidden');
            if (cancelBtn) cancelBtn.classList.remove('hidden');
            lyricsDiv.classList.add('hidden');
        } else {
            displayDiv.classList.remove('hidden');
            editorDiv.classList.add('hidden');
            editBtn.classList.remove('hidden');
            if (autoBtn) autoBtn.classList.remove('hidden');
            saveBtn.classList.add('hidden');
            if (cancelBtn) cancelBtn.classList.add('hidden');
            lyricsDiv.classList.remove('hidden');
        }
    },

    async saveMetadata() {
        const saveBtn = document.getElementById('save-metadata-btn');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;

        const data = {
            title: document.getElementById('meta-input-title').value,
            artist: document.getElementById('meta-input-artist').value,
            album: document.getElementById('meta-input-album').value,
            lyrics: document.getElementById('meta-input-lyrics').value
        };

        if (this.pendingCover) {
            data.cover = this.pendingCover;
        }

        try {
            await this.api.updateMetadata(this.currentFile.path, data);
            this.pendingCover = null;
            await this.loadMetadata();
            this.toggleEditMode(false);
        } catch (err) {
            alert("Failed to save metadata.");
            console.error(err);
        } finally {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    },

    close() {
        const mp3Modal = document.getElementById('mp3-modal');
        const mp3Audio = document.getElementById('mp3-audio');
        if (mp3Audio) {
            mp3Audio.pause();
            mp3Audio.src = '';
        }
        if (mp3Modal) {
            mp3Modal.classList.add('hidden');
        }
    }
};
