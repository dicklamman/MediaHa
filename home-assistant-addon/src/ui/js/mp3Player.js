export const mp3Player = {
    currentFile: null,
    api: null,
    pendingCover: null,
    lrcData: [],
    activeIndex: -1,
    savedOriginalDisplay: null,

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
            this.loadMetadata();
        });
        if (autoEnhanceBtn) autoEnhanceBtn.addEventListener('click', () => this.autoEnhance());

        const confirmEnhanceBtn = document.getElementById('confirm-enhance-btn');
        if (confirmEnhanceBtn) confirmEnhanceBtn.addEventListener('click', () => this.confirmEnhance());

        const cancelEnhanceBtn = document.getElementById('cancel-enhance-btn');
        if (cancelEnhanceBtn) cancelEnhanceBtn.addEventListener('click', () => this.cancelEnhance());

        // Handle enhance preview button clicks
        document.querySelectorAll('.use-enhance-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const field = btn.getAttribute('data-field');
                this.useEnhanced[field] = true;
                this.updateEnhanceButtons();
            });
        });

        document.querySelectorAll('.revert-enhance-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const field = btn.getAttribute('data-field');
                this.useEnhanced[field] = false;
                this.updateEnhanceButtons();
            });
        });

        const mp3Audio = document.getElementById('mp3-audio');
        if (mp3Audio) {
            mp3Audio.addEventListener('timeupdate', () => this.updateSyncedLyrics(mp3Audio.currentTime));
        }

        document.querySelectorAll('.revert-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const field = btn.getAttribute('data-field');
                if (!this.originalMetadata) return;

                const isReverting = btn.textContent === 'Revert to Existing';

                if (isReverting) {
                    if (field === 'cover') {
                        this.pendingCover = null;
                        const mp3Cover = document.getElementById('mp3-cover');
                        if (this.originalMetadata.cover) {
                            mp3Cover.src = this.originalMetadata.cover;
                            mp3Cover.style.display = 'block';
                        } else {
                            if (mp3Cover) mp3Cover.style.display = 'none';
                        }
                    } else if (field === 'o3ics') {
                        document.getElementById('meta-input-o3ics').value = this.originalMetadata.o3ics || '';
                    } else {
                        document.getElementById('meta-input-' + field).value = this.originalMetadata[field] || '';
                    }
                    btn.textContent = 'Restore Enhanced Version';
                    btn.style.background = '#28a745';
                } else {
                    if (!this.enhancedMetadata) return;
                    if (field === 'cover') {
                        this.pendingCover = this.enhancedMetadata.cover;
                        const mp3Cover = document.getElementById('mp3-cover');
                        if (this.enhancedMetadata.cover) {
                            mp3Cover.src = this.enhancedMetadata.cover;
                            mp3Cover.style.display = 'block';
                        }
                    } else if (field === 'o3ics') {
                        document.getElementById('meta-input-o3ics').value = this.enhancedMetadata.o3ics || '';
                    } else {
                        document.getElementById('meta-input-' + field).value = this.enhancedMetadata[field] || '';
                    }
                    btn.textContent = 'Revert to Existing';
                    btn.style.background = '#6c757d';
                }
            });
        });
    },

    async open(file, apiInstance) {
        if (!file || file.type === 'folder') return;
        this.currentFile = file;
        this.api = apiInstance || window.api;
        this.pendingCover = null;
        this.enhancedMetadata = null;
        this.savedOriginalDisplay = null;

        // Reset enhance status
        const enhanceStatus = document.getElementById('enhance-status');
        if (enhanceStatus) {
            enhanceStatus.textContent = '';
            enhanceStatus.classList.add('hidden');
        }
        const autoBtn = document.getElementById('auto-enhance-btn');
        if (autoBtn) autoBtn.textContent = 'Auto Enhance';

        const mp3Modal = document.getElementById('mp3-modal');
        const mp3Title = document.getElementById('mp3-title');
        const mp3Audio = document.getElementById('mp3-audio');
        const mp3Cover = document.getElementById('mp3-cover');
        const mp3Lyrics = document.getElementById('mp3-o3ics');

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
            if (mp3Lyrics) mp3Lyrics.classList.remove('synced');

            const titleEl = document.getElementById('meta-disp-title');
            const artistEl = document.getElementById('meta-disp-artist');
            const albumEl = document.getElementById('meta-disp-album');
            if (titleEl) titleEl.textContent = 'Loading...';
            if (artistEl) artistEl.textContent = 'Loading...';
            if (albumEl) albumEl.textContent = 'Loading...';

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
            let textContent = line.replace(timeRegex, '').trim();
            if (textContent.startsWith(']')) {
                textContent = textContent.substring(1).trim();
            }

            if (matches.length > 0 && textContent !== undefined) {
                matches.forEach(match => {
                    const m = parseInt(match[1], 10);
                    const s = parseInt(match[2], 10);
                    const ms = match[3].length === 2 ? parseInt(match[3], 10) * 10 : parseInt(match[3], 10);
                    const time = (m * 60) + s + (ms / 1000);
                    parsed.push({ time, text: textContent === '' ? '🎵' : textContent });
                });
            }
        });
        return parsed.sort((a, b) => a.time - b.time);
    },

    async renderLyrics(text) {
        const o3icsDiv = document.getElementById('mp3-o3ics');
        if (!o3icsDiv) return;

        // Handle empty/undefined
        if (!text || (typeof text === 'string' && text.trim() === '')) {
            o3icsDiv.classList.remove('synced');
            o3icsDiv.innerHTML = '<p style="color: #888;">No o3ics available</p>';
            return;
        }

        // Save original text in case ruby API fails
        let textToUse = text;

        try {
            const res = await fetch('/api/o3ics/ruby', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });
            if (res.ok) {
                const data = await res.json();
                console.log("Ruby API response:", data);
                // Use result if it's not empty, otherwise keep original
                if (data.result && data.result.trim()) {
                    textToUse = data.result;
                    console.log("Using ruby-enhanced lyrics");
                } else {
                    console.log("Ruby API returned empty result, using original");
                }
            } else {
                console.error("Ruby API error:", res.status);
            }
        } catch (e) {
            console.error("Ruby parsing failed:", e);
            // Keep original text on error
        }

        // Parse the o3ics
        this.lrcData = this.parseLRC(textToUse);
        this.activeIndex = -1;

        if (this.lrcData.length > 0) {
            o3icsDiv.classList.add('synced');
            o3icsDiv.innerHTML = '';
            this.lrcData.forEach((line, index) => {
                const p = document.createElement('p');
                p.innerHTML = line.text;
                p.id = 'lrc-line-' + index;
                o3icsDiv.appendChild(p);
            });
        } else {
            // If no synced o3ics but we have plain text, show it
            o3icsDiv.classList.remove('synced');
            o3icsDiv.innerHTML = textToUse;
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

                const container = document.getElementById('mp3-o3ics');
                const scrollPos = newEl.offsetTop - container.offsetTop - (container.clientHeight / 2) + (newEl.clientHeight / 2);
                container.scrollTo({ top: scrollPos, behavior: 'smooth' });
            }
        }
    },

    async loadMetadata() {
        try {
            const metadata = await this.api.getMetadata(this.currentFile.path);
            this.originalMetadata = metadata;
            this.useEnhanced = {};
            document.querySelectorAll(".revert-btn").forEach(btn => btn.style.display = "none");

            const titleEl = document.getElementById('meta-disp-title');
            const artistEl = document.getElementById('meta-disp-artist');
            const albumEl = document.getElementById('meta-disp-album');
            if (titleEl) titleEl.textContent = metadata.title || 'Unknown Title';
            if (artistEl) artistEl.textContent = metadata.artist || 'Unknown Artist';
            if (albumEl) albumEl.textContent = metadata.album || 'Unknown Album';

            const titleInput = document.getElementById('meta-input-title');
            const artistInput = document.getElementById('meta-input-artist');
            const albumInput = document.getElementById('meta-input-album');
            const o3icsInput = document.getElementById('meta-input-o3ics');
            if (titleInput) titleInput.value = metadata.title || '';
            if (artistInput) artistInput.value = metadata.artist || '';
            if (albumInput) albumInput.value = metadata.album || '';

            // Find o3ics value from metadata (handles key name issues)
            let o3icsValue = metadata.o3ics || '';
            if (!o3icsValue) {
                for (const key of Object.keys(metadata)) {
                    if (key.toLowerCase().includes('o3ics') || key.toLowerCase().includes('o3ic')) {
                        o3icsValue = metadata[key] || '';
                        break;
                    }
                }
            }
            if (!o3icsValue) {
                const values = Object.values(metadata);
                for (const v of values) {
                    if (typeof v === 'string' && v.includes('[ti:')) {
                        o3icsValue = v;
                        break;
                    }
                }
            }

            // Set the input value with correctly found o3ics
            if (o3icsInput) o3icsInput.value = o3icsValue || '';
            this.originalMetadata.o3ics = o3icsValue || '';

            this.renderLyrics(o3icsValue);

            const mp3Cover = document.getElementById('mp3-cover');
            if (metadata.cover && mp3Cover) {
                mp3Cover.src = metadata.cover;
                mp3Cover.style.display = 'block';
                this.originalMetadata.cover = metadata.cover;
            } else if (mp3Cover) {
                mp3Cover.style.display = 'none';
            }

            const mp3Title = document.getElementById('mp3-title');
            if (metadata.title && mp3Title) {
                mp3Title.textContent = metadata.title + (metadata.artist ? ' - ' + metadata.artist : '');
            }

        } catch (err) {
            const o3icsEl = document.getElementById('mp3-o3ics');
            if (o3icsEl) o3icsEl.textContent = 'Failed to load metadata.';
            console.error("Metadata error:", err);
        }
    },

    async autoEnhance() {
        if (!this.api || !this.currentFile) return;
        const autoBtn = document.getElementById('auto-enhance-btn');
        if (!autoBtn) return;
        const originalText = autoBtn.textContent;
        autoBtn.innerHTML = '<span class="spinner"></span>Searching...';
        autoBtn.disabled = true;

        try {
            const data = await this.api.enhanceMp3(this.currentFile.path);
            this.enhancedMetadata = data;
            this.originalMetadata = this.originalMetadata || {};

            // Check if any data found
            let o3icsValue = data.o3ics || '';
            if (!o3icsValue) {
                for (const key of Object.keys(data)) {
                    if (key.toLowerCase().includes('o3ics') || key.toLowerCase().includes('o3ic')) {
                        o3icsValue = data[key] || '';
                        break;
                    }
                }
            }
            if (!o3icsValue) {
                const values = Object.values(data);
                for (const v of values) {
                    if (typeof v === 'string' && v.includes('[ti:')) {
                        o3icsValue = v;
                        break;
                    }
                }
            }

            // Update display section with enhanced data
            // Save original display values BEFORE overwriting for preview and restoration on cancel
            this.savedOriginalDisplay = {
                title: document.getElementById('meta-disp-title').textContent,
                artist: document.getElementById('meta-disp-artist').textContent,
                album: document.getElementById('meta-disp-album').textContent,
                o3ics: document.getElementById('meta-input-o3ics').value
            };

            if (data.title) {
                document.getElementById('meta-disp-title').textContent = data.title;
                document.getElementById('meta-input-title').value = data.title;
            }
            if (data.artist) {
                document.getElementById('meta-disp-artist').textContent = data.artist;
                document.getElementById('meta-input-artist').value = data.artist;
            }
            if (data.album) {
                document.getElementById('meta-disp-album').textContent = data.album;
                document.getElementById('meta-input-album').value = data.album;
            }
            if (o3icsValue) {
                document.getElementById('meta-input-o3ics').value = o3icsValue;
            }

            if (data.cover) {
                this.pendingCover = data.cover;
                const mp3Cover = document.getElementById('mp3-cover');
                if (mp3Cover) {
                    mp3Cover.src = data.cover;
                    mp3Cover.style.display = 'block';
                }
                
            }

            // If any data found, show preview and confirm/cancel buttons
            if (data.title || data.artist || data.album || data.cover || o3icsValue) {
                // Populate enhance-preview section with original vs new values
                document.getElementById('enhance-orig-title').textContent = this.savedOriginalDisplay.title || '-';
                document.getElementById('enhance-new-title').textContent = data.title || '-';
                document.getElementById('enhance-orig-artist').textContent = this.savedOriginalDisplay.artist || '-';
                document.getElementById('enhance-new-artist').textContent = data.artist || '-';
                document.getElementById('enhance-orig-album').textContent = this.savedOriginalDisplay.album || '-';
                document.getElementById('enhance-new-album').textContent = data.album || '-';
                
                // Show actual lyrics content (first 3 lines as preview)
                const origO3icsText = this.savedOriginalDisplay.o3ics || '';
                const newO3icsText = o3icsValue || '';
                const origPreview = origO3icsText.split('\n').slice(0, 3).join('\n') || '(No lyrics)';
                const newPreview = newO3icsText.split('\n').slice(0, 3).join('\n') || '(No lyrics)';
                document.getElementById('enhance-orig-o3ics').textContent = origPreview;
                document.getElementById('enhance-new-o3ics').textContent = newPreview;

                // Populate cover previews - use saved original cover
                const origCover = document.getElementById('enhance-orig-cover');
                const newCover = document.getElementById('enhance-new-cover');
                const origPlaceholder = document.getElementById('enhance-orig-cover-placeholder');
                const newPlaceholder = document.getElementById('enhance-new-cover-placeholder');
                
                // Use the cover from originalMetadata (loaded when file opened)
                const origCoverUrl = this.originalMetadata && this.originalMetadata.cover ? this.originalMetadata.cover : '';
                const newCoverUrl = data.cover ? data.cover : '';
                
                // Update the main cover display
                if (newCoverUrl) {
                    const mp3Cover = document.getElementById('mp3-cover');
                    if (mp3Cover) {
                        mp3Cover.src = newCoverUrl;
                        mp3Cover.style.display = 'block';
                    }
                }
                
                // Handle original cover display
                if (origCover && origPlaceholder) {
                    if (origCoverUrl) {
                        origCover.src = origCoverUrl;
                        origCover.classList.add('has-image');
                        origPlaceholder.classList.remove('show');
                    } else {
                        origCover.src = '';
                        origCover.classList.remove('has-image');
                        origPlaceholder.classList.add('show');
                    }
                }
                
                // Handle new cover display
                if (newCover && newPlaceholder) {
                    if (newCoverUrl) {
                        newCover.src = newCoverUrl;
                        newCover.classList.add('has-image');
                        newPlaceholder.classList.remove('show');
                    } else {
                        newCover.src = '';
                        newCover.classList.remove('has-image');
                        newPlaceholder.classList.add('show');
                    }
                }

                // Set default: keep original (false for all fields)
                this.useEnhanced = {
                    title: false,
                    artist: false,
                    album: false,
                    cover: false,
                    o3ics: false
                };
                this.updateEnhanceButtons();

                document.getElementById('metadata-display').classList.add('hidden');
                document.getElementById('enhance-preview').classList.remove('hidden');
                document.getElementById('auto-enhance-btn').classList.add('hidden');
                document.getElementById('confirm-enhance-btn').classList.remove('hidden');
                document.getElementById('cancel-enhance-btn').classList.remove('hidden');
                document.getElementById('edit-metadata-btn').classList.add('hidden');
            } else {
                alert('No enhancement data found. Try editing manually.');
            }

        } catch (err) {
            alert('Failed to find enhancement data: ' + err.message);
            console.error(err);
        } finally {
            autoBtn.textContent = originalText;
            autoBtn.disabled = false;
        }
    },

    updateEnhanceButtons() {
        // Update button styles based on selection
        ['title', 'artist', 'album', 'cover', 'o3ics'].forEach(field => {
            const useBtn = document.querySelector(`.use-enhance-btn[data-field="${field}"]`);
            const revertBtn = document.querySelector(`.revert-enhance-btn[data-field="${field}"]`);
            if (!useBtn || !revertBtn) return;

            if (this.useEnhanced[field]) {
                useBtn.classList.add('btn-primary');
                useBtn.classList.remove('btn-outline');
                revertBtn.classList.remove('btn-primary');
                revertBtn.classList.add('btn-outline');
            } else {
                revertBtn.classList.add('btn-primary');
                revertBtn.classList.remove('btn-outline');
                useBtn.classList.remove('btn-primary');
                useBtn.classList.add('btn-outline');
            }
        });
    },

    async confirmEnhance() {
        const confirmBtn = document.getElementById('confirm-enhance-btn');
        const originalText = confirmBtn.textContent;
        confirmBtn.innerHTML = '<span class="spinner"></span>Saving...';
        confirmBtn.disabled = true;

        try {
            // Prepare metadata with selected values
            const data = {
                title: this.useEnhanced.title && this.enhancedMetadata.title ? this.enhancedMetadata.title : this.originalMetadata.title,
                artist: this.useEnhanced.artist && this.enhancedMetadata.artist ? this.enhancedMetadata.artist : this.originalMetadata.artist,
                album: this.useEnhanced.album && this.enhancedMetadata.album ? this.enhancedMetadata.album : this.originalMetadata.album,
                o3ics: this.useEnhanced.o3ics ? (this.enhancedMetadata.o3ics || Object.values(this.enhancedMetadata).find(v => typeof v === 'string' && v.includes('[ti:')) || '') : (this.originalMetadata.o3ics || '')
            };

            if (this.useEnhanced.cover && this.enhancedMetadata.cover) {
                data.cover = this.enhancedMetadata.cover;
            }

            await this.api.updateMetadata(this.currentFile.path, data);

            // Reload metadata to get the saved data
            await this.loadMetadata();

            // Reset enhance UI state (but DON'T restore original display values)
            this.resetEnhanceUI();

            // Re-render lyrics with new data
            const o3icsValue = data.o3ics || this.originalMetadata?.o3ics || '';
            this.renderLyrics(o3icsValue);

        } catch (err) {
            alert('Failed to save enhanced metadata.');
            console.error(err);
        } finally {
            confirmBtn.textContent = originalText;
            confirmBtn.disabled = false;
        }
    },

    // Reset enhance UI state without restoring original display values
    resetEnhanceUI() {
        document.getElementById('enhance-preview').classList.add('hidden');
        document.getElementById('metadata-display').classList.remove('hidden');
        document.getElementById('auto-enhance-btn').classList.remove('hidden');
        document.getElementById('confirm-enhance-btn').classList.add('hidden');
        document.getElementById('cancel-enhance-btn').classList.add('hidden');
        document.getElementById('edit-metadata-btn').classList.remove('hidden');

        this.enhancedMetadata = null;
        this.useEnhanced = {};
    },

    cancelEnhance() {
        // Restore original display values if we have them saved
        if (this.savedOriginalDisplay) {
            document.getElementById('meta-disp-title').textContent = this.savedOriginalDisplay.title;
            document.getElementById('meta-disp-artist').textContent = this.savedOriginalDisplay.artist;
            document.getElementById('meta-disp-album').textContent = this.savedOriginalDisplay.album;
            document.getElementById('meta-input-o3ics').value = this.savedOriginalDisplay.o3ics;
            this.savedOriginalDisplay = null;
        }

        // Restore original cover if we have it
        if (this.originalMetadata && this.originalMetadata.cover) {
            const mp3Cover = document.getElementById('mp3-cover');
            if (mp3Cover) {
                mp3Cover.src = this.originalMetadata.cover;
                mp3Cover.style.display = 'block';
            }
        } else {
            const mp3Cover = document.getElementById('mp3-cover');
            if (mp3Cover) {
                mp3Cover.style.display = 'none';
            }
        }

        // Hide preview, show display
        document.getElementById('enhance-preview').classList.add('hidden');
        document.getElementById('metadata-display').classList.remove('hidden');

        // Show/hide buttons
        document.getElementById('auto-enhance-btn').classList.remove('hidden');
        document.getElementById('confirm-enhance-btn').classList.add('hidden');
        document.getElementById('cancel-enhance-btn').classList.add('hidden');
        document.getElementById('edit-metadata-btn').classList.remove('hidden');

        // Clear enhanced data
        this.enhancedMetadata = null;
        this.useEnhanced = {};
    },

    toggleEditMode(isEdit) {
        const displayDiv = document.getElementById('metadata-display');
        const editorDiv = document.getElementById('metadata-editor');
        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');
        const cancelBtn = document.getElementById('cancel-metadata-btn');
        const o3icsDiv = document.getElementById('mp3-o3ics');
        const enhancePreview = document.getElementById('enhance-preview');

        // Hide enhance preview when entering edit mode
        if (enhancePreview) enhancePreview.classList.add('hidden');

        if (isEdit) {
            if (displayDiv) displayDiv.classList.add('hidden');
            if (editorDiv) editorDiv.classList.remove('hidden');
            if (editBtn) editBtn.classList.add('hidden');
            if (saveBtn) saveBtn.classList.remove('hidden');
            if (cancelBtn) cancelBtn.classList.remove('hidden');
            if (o3icsDiv) o3icsDiv.classList.add('hidden');
        } else {
            if (displayDiv) displayDiv.classList.remove('hidden');
            if (editorDiv) editorDiv.classList.add('hidden');
            if (editBtn) editBtn.classList.remove('hidden');
            if (saveBtn) saveBtn.classList.add('hidden');
            if (cancelBtn) cancelBtn.classList.add('hidden');
            if (o3icsDiv) o3icsDiv.classList.remove('hidden');
        }
    },

    async saveMetadata() {
        const saveBtn = document.getElementById('save-metadata-btn');
        const originalText = saveBtn.textContent;
        saveBtn.innerHTML = '<span class="spinner"></span>Saving...';
        saveBtn.disabled = true;

        try {
            const title = document.getElementById('meta-input-title').value;
            const artist = document.getElementById('meta-input-artist').value;
            const album = document.getElementById('meta-input-album').value;
            const o3ics = document.getElementById('meta-input-o3ics').value;

            const data = { title, artist, album, o3ics };
            if (this.pendingCover) {
                data.cover = this.pendingCover;
            }

            await this.api.updateMetadata(this.currentFile.path, data);

            this.pendingCover = null;
            await this.loadMetadata();
            this.toggleEditMode(false);
        } catch (err) {
            alert('Failed to save metadata: ' + err.message);
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
            mp3Audio.currentTime = 0;
        }
        if (mp3Modal) mp3Modal.classList.add('hidden');

        // Reset enhance state
        this.cancelEnhance();
    },

    showFullO3ics(type) {
        let content = '';
        if (type === 'orig') {
            content = this.savedOriginalDisplay?.o3ics || this.originalMetadata?.o3ics || '';
        } else {
            content = this.enhancedMetadata?.o3ics || '';
            if (!content) {
                // Try to find o3ics in enhanced metadata
                for (const key of Object.keys(this.enhancedMetadata || {})) {
                    if (key.toLowerCase().includes('o3ics') || key.toLowerCase().includes('o3ic')) {
                        content = this.enhancedMetadata[key] || '';
                        break;
                    }
                }
            }
        }
        
        if (!content) {
            alert('No o3ics content available');
            return;
        }
        
        // Show in a modal - add a class for identification
        const modal = document.createElement('div');
        modal.className = 'o3ics-full-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;';
        modal.innerHTML = `
            <div style="background:var(--bg-primary);padding:20px;border-radius:8px;max-width:80%;max-height:80%;overflow:auto;">
                <h3 style="margin:0 0 10px 0;">${type === 'orig' ? 'Original' : 'Enhanced'} o3ics</h3>
                <pre style="white-space:pre-wrap;word-break:break-all;background:var(--bg-secondary);padding:10px;border-radius:4px;max-height:400px;overflow:auto;">${content}</pre>
                <button class="o3ics-modal-close" style="margin-top:10px;padding:8px 16px;cursor:pointer;">Close</button>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Add click handler for close button
        modal.querySelector('.o3ics-modal-close').addEventListener('click', () => {
            modal.remove();
        });
    }
};

// Make showFullO3ics available globally for onclick handlers
window.showFullO3ics = function(type) {
    mp3Player.showFullO3ics(type);
};
