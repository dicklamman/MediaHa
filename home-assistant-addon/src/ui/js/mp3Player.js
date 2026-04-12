export const mp3Player = {
    currentFile: null,
    api: null,
    pendingCover: null,
    pendingCoverIndex: 0,
    coverOptions: [],
    pendingO3ics: null,
    pendingO3icsIndex: 0,
    o3icsOptions: [],
    lrcData: [],
    activeIndex: -1,
    savedOriginalDisplay: null,
    selectedCoverSource: 'all',
    selectedO3icsSource: 'all',
    lrcEditorTimedLines: null,
    currentLrcEditorIndex: -1,
    lrcEditorAudioHandler: null,
    isInLrcEditMode: false,

    init() {
        const closeMp3Btn = document.getElementById('close-mp3');
        if (closeMp3Btn) closeMp3Btn.addEventListener('click', () => this.close());

        // Image preview modal
        const closeImagePreviewBtn = document.getElementById('close-image-preview');
        if (closeImagePreviewBtn) {
            closeImagePreviewBtn.addEventListener('click', () => {
                document.getElementById('image-preview-modal').classList.add('hidden');
            });
        }

        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');
        const cancelBtn = document.getElementById('cancel-metadata-btn');
        const autoEnhanceBtn = document.getElementById('auto-enhance-btn');

        if (editBtn) editBtn.addEventListener('click', () => this.toggleEditMode(true));
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveMetadata());
        if (cancelBtn) cancelBtn.addEventListener('click', () => {
            this.pendingCover = null;
            this.resetCoverEditor();
            this.toggleEditMode(false);
            this.loadMetadata();
        });
        if (autoEnhanceBtn) autoEnhanceBtn.addEventListener('click', () => this.autoEnhance());

        const confirmEnhanceBtn = document.getElementById('confirm-enhance-btn');
        if (confirmEnhanceBtn) confirmEnhanceBtn.addEventListener('click', () => this.confirmEnhance());

        const cancelEnhanceBtn = document.getElementById('cancel-enhance-btn');
        if (cancelEnhanceBtn) cancelEnhanceBtn.addEventListener('click', () => this.cancelEnhance());

        // LRC Editor buttons
        const editLrcBtn = document.getElementById('edit-lrc-btn');
        if (editLrcBtn) editLrcBtn.addEventListener('click', () => this.showLrcEditor());

        const saveLrcBtn = document.getElementById('save-lrc-btn');
        if (saveLrcBtn) saveLrcBtn.addEventListener('click', () => this.saveLrc());

        const cancelLrcBtn = document.getElementById('cancel-lrc-btn');
        if (cancelLrcBtn) cancelLrcBtn.addEventListener('click', () => this.cancelLrc());

        const lrcAddBtn = document.getElementById('lrc-add-btn');
        if (lrcAddBtn) lrcAddBtn.addEventListener('click', () => this.applyLrcOffset(1));

        const lrcSubtractBtn = document.getElementById('lrc-subtract-btn');
        if (lrcSubtractBtn) lrcSubtractBtn.addEventListener('click', () => this.applyLrcOffset(-1));

        // Cover upload handlers
        const uploadCoverBtn = document.getElementById('upload-cover-btn');
        const coverFileInput = document.getElementById('cover-file-input');
        const urlCoverBtn = document.getElementById('url-cover-btn');
        const coverUrlInput = document.getElementById('cover-url-input');
        const applyUrlCoverBtn = document.getElementById('apply-url-cover-btn');
        const removeCoverBtn = document.getElementById('remove-cover-btn');

        if (uploadCoverBtn && coverFileInput) {
            uploadCoverBtn.addEventListener('click', () => coverFileInput.click());
            coverFileInput.addEventListener('change', (e) => this.handleCoverFileUpload(e));
        }

        if (urlCoverBtn && coverUrlInput) {
            urlCoverBtn.addEventListener('click', () => {
                const isVisible = coverUrlInput.style.display !== 'none';
                coverUrlInput.style.display = isVisible ? 'none' : 'block';
                applyUrlCoverBtn.classList.toggle('hidden', isVisible);
            });
        }

        if (applyUrlCoverBtn) {
            applyUrlCoverBtn.addEventListener('click', () => this.handleCoverUrlInput());
        }

        if (removeCoverBtn) {
            removeCoverBtn.addEventListener('click', () => this.handleRemoveCover());
        }

        // LRC offset input change handler
        const lrcOffsetInput = document.getElementById('lrc-offset-input');
        if (lrcOffsetInput) {
            lrcOffsetInput.addEventListener('input', () => this.updateLrcEditorPreview());
        }

        // Handle cover source selection
        document.querySelectorAll('.cover-source-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const source = btn.getAttribute('data-source');
                this.selectedCoverSource = source;
                // Update button styles
                document.querySelectorAll('.cover-source-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Handle o3ics source selection
        document.querySelectorAll('.o3ics-source-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const source = btn.getAttribute('data-source');
                this.selectedO3icsSource = source;
                // Update button styles
                document.querySelectorAll('.o3ics-source-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

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

        // Handle refresh enhance button clicks
        document.querySelectorAll('.refresh-enhance-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const field = btn.getAttribute('data-field');
                this.refreshEnhance(field);
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
        if (autoBtn) {
            autoBtn.textContent = 'Auto Enhance';
            autoBtn.classList.remove('hidden');
        }
        
        // Reset button states for enhance preview
        document.getElementById('enhance-preview')?.classList.add('hidden');
        document.getElementById('metadata-display')?.classList.remove('hidden');
        document.getElementById('confirm-enhance-btn')?.classList.add('hidden');
        document.getElementById('cancel-enhance-btn')?.classList.add('hidden');
        document.getElementById('edit-metadata-btn')?.classList.remove('hidden');

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
            // Remove leading ] (and any extra ones)
            while (textContent.startsWith(']')) {
                textContent = textContent.substring(1).trim();
            }
            // Remove trailing ] if present (handles malformed LRC)
            if (textContent.endsWith(']')) {
                textContent = textContent.slice(0, -1).trim();
            }

            if (matches.length > 0 && textContent !== undefined) {
                matches.forEach(match => {
                    const m = parseInt(match[1], 10);
                    const s = parseInt(match[2], 10);
                    const ms = match[3].length === 2 ? parseInt(match[3], 10) * 10 : parseInt(match[3], 10);
                    const time = (m * 60) + s + (ms / 1000);
                    parsed.push({ time, text: textContent === '' ? '<span class="material-icons" style="font-size:14px">music_note</span>' : textContent });
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
        // Skip if in LRC edit mode (editor handles its own sync)
        if (this.isInLrcEditMode) return;

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

            // Track sources for each field
            const sources = {
                title: null,
                artist: null,
                album: null,
                cover: null,
                o3ics: null
            };

            // Get search info from API response
            const searchInfo = data.search_info || {};

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

            // Check what data is available and set sources
            // iTunes provides: title, artist, album, cover
            // LrcLib provides: o3ics
            if (data.title && data.title !== this.savedOriginalDisplay.title) {
                sources.title = 'itunes';
            }
            if (data.artist && data.artist !== this.savedOriginalDisplay.artist) {
                sources.artist = 'itunes';
            }
            if (data.album && data.album !== this.savedOriginalDisplay.album) {
                sources.album = 'itunes';
            }
            if (data.cover && data.cover !== (this.originalMetadata?.cover || '')) {
                sources.cover = 'itunes';
            }
            if (o3icsValue && o3icsValue !== this.savedOriginalDisplay.o3ics) {
                sources.o3ics = 'lrclib';
            }

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

            // Store cover options and show selector
            this.coverOptions = data.cover_options || [];
            if (this.coverOptions.length > 0) {
                this.showCoverOptions();
            }

            // Store o3ics options and show selector
            this.o3icsOptions = data.o3ics_options || [];
            if (this.o3icsOptions.length > 0) {
                this.showO3icsOptions();
            }

            // If any data found, show preview and confirm/cancel buttons
            if (data.title || data.artist || data.album || data.cover || o3icsValue) {
                // Populate enhance-preview section with original vs new values
                document.getElementById('enhance-orig-title').textContent = this.savedOriginalDisplay.title || '-';
                document.getElementById('enhance-new-title').textContent = data.title || '';
                document.getElementById('enhance-orig-artist').textContent = this.savedOriginalDisplay.artist || '-';
                document.getElementById('enhance-new-artist').textContent = data.artist || '';
                document.getElementById('enhance-orig-album').textContent = this.savedOriginalDisplay.album || '-';
                document.getElementById('enhance-new-album').textContent = data.album || '';
                
                // Show actual lyrics content (first 3 lines as preview)
                const origO3icsText = this.savedOriginalDisplay.o3ics || '';
                const newO3icsText = o3icsValue || '';
                const origPreview = origO3icsText.split('\n').slice(0, 3).join('\n') || '(No lyrics)';
                const newPreview = newO3icsText.split('\n').slice(0, 3).join('\n') || '';
                document.getElementById('enhance-orig-o3ics').textContent = origPreview;
                document.getElementById('enhance-new-o3ics').textContent = newPreview;

                // Update source badges
                this.updateSourceBadge('title', sources.title, searchInfo);
                this.updateSourceBadge('artist', sources.artist, searchInfo);
                this.updateSourceBadge('album', sources.album, searchInfo);
                this.updateSourceBadge('cover', sources.cover, searchInfo);
                this.updateSourceBadge('o3ics', sources.o3ics, searchInfo);

                // Populate cover previews - use saved original cover
                const origCover = document.getElementById('enhance-orig-cover');
                const newCover = document.getElementById('enhance-new-cover');
                const origPlaceholder = document.getElementById('enhance-orig-cover-placeholder');
                const newPlaceholder = document.getElementById('enhance-new-cover-placeholder');
                
                // Use the cover from originalMetadata (loaded when file opened)
                const origCoverUrl = this.originalMetadata && this.originalMetadata.cover ? this.originalMetadata.cover : '';
                const newCoverUrl = data.cover ? data.cover : '';
                
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

    async refreshEnhance(field) {
        if (!this.api || !this.currentFile) return;

        const refreshBtn = document.querySelector(`.refresh-enhance-btn[data-field="${field}"]`);
        if (refreshBtn) {
            refreshBtn.classList.add('loading');
            const icon = refreshBtn.querySelector('.material-icons');
            if (icon) icon.textContent = 'sync';
        }

        // Track the current offset for this field
        if (!this.refreshOffsets) this.refreshOffsets = {};
        const currentOffset = this.refreshOffsets[field] || 0;
        const nextOffset = currentOffset + 1;
        this.refreshOffsets[field] = nextOffset;

        try {
            const data = await this.api.enhanceMp3(this.currentFile.path, nextOffset, this.selectedCoverSource);
            this.enhancedMetadata = data;

            // Update cover options
            this.coverOptions = data.cover_options || [];

            switch (field) {
                case 'cover':
                    if (data.cover) {
                        this.pendingCover = data.cover;
                        document.getElementById('mp3-cover').src = data.cover;
                        document.getElementById('mp3-cover').style.display = 'block';
                        const newCover = document.getElementById('enhance-new-cover');
                        if (newCover) {
                            newCover.src = data.cover;
                            newCover.classList.add('has-image');
                        }
                        const newPlaceholder = document.getElementById('enhance-new-cover-placeholder');
                        if (newPlaceholder) newPlaceholder.classList.remove('show');
                    }
                    if (this.coverOptions.length > 0) {
                        this.showCoverOptions();
                    }
                    // Determine actual source from search_info
                    const searchInfo = data.search_info || {};
                    if (searchInfo.musicbrainz?.found) {
                        this.updateSourceBadge('cover', 'musicbrainz', searchInfo);
                    } else if (searchInfo.spotify?.found) {
                        this.updateSourceBadge('cover', 'deezer', searchInfo);
                    } else {
                        this.updateSourceBadge('cover', 'itunes', searchInfo);
                    }
                    break;

                case 'o3ics':
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
                    if (o3icsValue) {
                        // Store o3ics options
                        this.o3icsOptions = data.o3ics_options || [];
                        if (this.o3icsOptions.length > 0) {
                            this.showO3icsOptions();
                        }

                        const newPreview = o3icsValue.split('\n').slice(0, 3).join('\n') || '';
                        document.getElementById('enhance-new-o3ics').textContent = newPreview;

                        // Determine source
                        const searchInfo = data.search_info || {};
                        if (searchInfo.genius?.found) {
                            this.updateSourceBadge('o3ics', 'genius', searchInfo);
                        } else {
                            this.updateSourceBadge('o3ics', 'lrclib', searchInfo);
                        }
                    }
                    break;

                case 'album':
                    if (data.album) {
                        document.getElementById('meta-disp-album').textContent = data.album;
                        document.getElementById('meta-input-album').value = data.album;
                        document.getElementById('enhance-new-album').textContent = data.album;
                        this.updateSourceBadge('album', 'itunes', data.search_info);
                    }
                    break;
            }
        } catch (err) {
            console.error(`Failed to refresh ${field}:`, err);
        } finally {
            if (refreshBtn) {
                refreshBtn.classList.remove('loading');
                const icon = refreshBtn.querySelector('.material-icons');
                if (icon) icon.textContent = 'refresh';
            }
        }
    },

    updateSourceBadge(field, source, searchInfo) {
        const badge = document.getElementById('enhance-source-' + field);
        if (!badge) return;

        if (source) {
            let label = source === 'itunes' ? 'iTunes' : (source === 'lrclib' ? 'LrcLib' : source);
            
            // Add search info if available
            if (searchInfo && searchInfo[source]) {
                const info = searchInfo[source];
                let searchDetails = '';
                
                if (source === 'itunes' && info.search_term) {
                    searchDetails = ` (${info.search_term})`;
                } else if (source === 'lrclib') {
                    const parts = [];
                    if (info.search_track) parts.push(`"${info.search_track}"`);
                    if (info.search_artist) parts.push(`"${info.search_artist}"`);
                    if (parts.length > 0) {
                        searchDetails = ` (${parts.join(', ')})`;
                    }
                }
                
                label += searchDetails;
            }
            
            badge.textContent = label;
            badge.className = 'enhance-source-badge visible ' + source;
        } else {
            badge.textContent = '';
            badge.className = 'enhance-source-badge';
        }
    },

    showCoverOptions() {
        const container = document.getElementById('cover-source-selector');
        const optionsContainer = document.getElementById('cover-options-container');
        const optionsList = document.getElementById('cover-options-list');

        if (!container || !optionsContainer || !optionsList) return;
        if (!this.coverOptions || this.coverOptions.length === 0) {
            container.classList.add('hidden');
            optionsContainer.classList.add('hidden');
            return;
        }

        // Show source selector
        container.classList.remove('hidden');

        // Show cover options list
        optionsContainer.classList.remove('hidden');
        optionsList.innerHTML = '';

        this.coverOptions.forEach((option, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'cover-option-item' + (index === this.pendingCoverIndex ? ' selected' : '');
            optionDiv.innerHTML = `
                <img src="${option.cover || ''}" alt="${option.source}" class="cover-option-thumb" onclick="mp3Player.selectCoverOption(${index})">
                <span class="cover-option-source">${option.source}</span>
            `;
            optionsList.appendChild(optionDiv);
        });
    },

    selectCoverOption(index) {
        if (!this.coverOptions || !this.coverOptions[index]) return;

        this.pendingCoverIndex = index;
        const option = this.coverOptions[index];
        this.pendingCover = option.cover;

        // Update display
        const mp3Cover = document.getElementById('mp3-cover');
        if (mp3Cover) {
            mp3Cover.src = option.cover;
            mp3Cover.style.display = 'block';
        }
        const newCover = document.getElementById('enhance-new-cover');
        if (newCover) {
            newCover.src = option.cover;
            newCover.classList.add('has-image');
        }
        const newPlaceholder = document.getElementById('enhance-new-cover-placeholder');
        if (newPlaceholder) newPlaceholder.classList.remove('show');

        // Update selection UI
        document.querySelectorAll('.cover-option-item').forEach((item, i) => {
            item.classList.toggle('selected', i === index);
        });
    },

    showO3icsOptions() {
        const container = document.getElementById('o3ics-source-selector');
        const optionsContainer = document.getElementById('o3ics-options-container');
        const optionsList = document.getElementById('o3ics-options-list');

        if (!container || !optionsContainer || !optionsList) return;
        if (!this.o3icsOptions || this.o3icsOptions.length === 0) {
            container.classList.add('hidden');
            optionsContainer.classList.add('hidden');
            return;
        }

        // Show source selector
        container.classList.remove('hidden');

        // Show o3ics options list
        optionsContainer.classList.remove('hidden');
        optionsList.innerHTML = '';

        this.o3icsOptions.forEach((option, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'o3ics-option-item' + (index === this.pendingO3icsIndex ? ' selected' : '');
            const preview = (option.o3ics || '').split('\n').slice(0, 2).join(' ').substring(0, 80);
            optionDiv.innerHTML = `
                <span class="o3ics-option-source">${option.source}</span>
                <span class="o3ics-option-preview">${preview || '(No preview)'}</span>
            `;
            optionDiv.onclick = () => this.selectO3icsOption(index);
            optionsList.appendChild(optionDiv);
        });
    },

    selectO3icsOption(index) {
        if (!this.o3icsOptions || !this.o3icsOptions[index]) return;

        this.pendingO3icsIndex = index;
        const option = this.o3icsOptions[index];
        this.pendingO3ics = option.o3ics;

        // Update display
        document.getElementById('meta-input-o3ics').value = option.o3ics || '';
        const newPreview = (option.o3ics || '').split('\n').slice(0, 3).join('\n') || '';
        document.getElementById('enhance-new-o3ics').textContent = newPreview;

        // Update selection UI
        document.querySelectorAll('.o3ics-option-item').forEach((item, i) => {
            item.classList.toggle('selected', i === index);
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
                o3ics: this.useEnhanced.o3ics ? (this.pendingO3ics || this.enhancedMetadata.o3ics || Object.values(this.enhancedMetadata).find(v => typeof v === 'string' && v.includes('[ti:')) || '') : (this.originalMetadata.o3ics || '')
            };

            console.log('confirmEnhance - useEnhanced:', this.useEnhanced);
            console.log('confirmEnhance - enhancedMetadata.cover:', this.enhancedMetadata?.cover ? 'exists' : 'null');

            // Cover: use pendingCover first (from cover selector), then enhancedMetadata
            if (this.pendingCover) {
                data.cover = this.pendingCover;
                console.log('confirmEnhance - using pendingCover, length:', data.cover.length);
            } else if (this.useEnhanced.cover && this.enhancedMetadata?.cover) {
                data.cover = this.enhancedMetadata.cover;
                console.log('confirmEnhance - using enhancedMetadata.cover, length:', data.cover.length);
            }

            console.log('confirmEnhance - final data keys:', Object.keys(data));
            const result = await this.api.updateMetadata(this.currentFile.path, data);
            console.log('confirmEnhance - updateMetadata result:', result);

            // Reload metadata to get the saved data
            await this.loadMetadata();

            // Update main cover display if cover was saved
            if (this.pendingCover || (this.useEnhanced.cover && this.enhancedMetadata?.cover)) {
                const mp3Cover = document.getElementById('mp3-cover');
                const coverToUse = this.pendingCover || this.enhancedMetadata.cover;
                if (mp3Cover && coverToUse) {
                    mp3Cover.src = coverToUse;
                    mp3Cover.style.display = 'block';
                }
            }

            // Reset enhance UI state (but DON'T restore original display values)
            this.resetEnhanceUI();

            // Re-render lyrics with new data
            const o3icsValue = data.o3ics || this.originalMetadata?.o3ics || '';
            this.renderLyrics(o3icsValue);

        } catch (err) {
            alert('Failed to save enhanced metadata: ' + err.message);
            console.error('confirmEnhance error:', err);
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

        // Hide cover options
        const container = document.getElementById('cover-source-selector');
        const optionsContainer = document.getElementById('cover-options-container');
        if (container) container.classList.add('hidden');
        if (optionsContainer) optionsContainer.classList.add('hidden');

        // Hide o3ics options
        const o3icsContainer = document.getElementById('o3ics-source-selector');
        const o3icsOptionsContainer = document.getElementById('o3ics-options-container');
        if (o3icsContainer) o3icsContainer.classList.add('hidden');
        if (o3icsOptionsContainer) o3icsOptionsContainer.classList.add('hidden');

        this.enhancedMetadata = null;
        this.useEnhanced = {};
        this.refreshOffsets = {};
        this.coverOptions = [];
        this.pendingCoverIndex = 0;
        this.o3icsOptions = [];
        this.pendingO3icsIndex = 0;
        this.pendingCover = null;
        this.pendingO3ics = null;
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
        this.refreshOffsets = {};
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

            // Initialize cover editor state
            this.initCoverEditor();
        } else {
            if (displayDiv) displayDiv.classList.remove('hidden');
            if (editorDiv) editorDiv.classList.add('hidden');
            if (editBtn) editBtn.classList.remove('hidden');
            if (saveBtn) saveBtn.classList.add('hidden');
            if (cancelBtn) cancelBtn.classList.add('hidden');
            if (o3icsDiv) o3icsDiv.classList.remove('hidden');
        }
    },

    initCoverEditor() {
        // Get current cover from display
        const mp3Cover = document.getElementById('mp3-cover');
        const editorPreview = document.getElementById('editor-cover-preview');
        const editorPlaceholder = document.getElementById('editor-cover-placeholder');
        const removeCoverBtn = document.getElementById('remove-cover-btn');

        const currentCoverSrc = mp3Cover?.src || '';

        if (currentCoverSrc && mp3Cover?.style.display !== 'none') {
            if (editorPreview) {
                editorPreview.src = currentCoverSrc;
                editorPreview.classList.remove('hidden');
            }
            if (editorPlaceholder) editorPlaceholder.classList.add('hidden');
            if (removeCoverBtn) removeCoverBtn.classList.remove('hidden');
        } else {
            if (editorPreview) {
                editorPreview.src = '';
                editorPreview.classList.add('hidden');
            }
            if (editorPlaceholder) editorPlaceholder.classList.remove('hidden');
            if (removeCoverBtn) removeCoverBtn.classList.add('hidden');
        }

        // Reset URL input
        const coverUrlInput = document.getElementById('cover-url-input');
        const applyUrlCoverBtn = document.getElementById('apply-url-cover-btn');
        if (coverUrlInput) coverUrlInput.style.display = 'none';
        if (coverUrlInput) coverUrlInput.value = '';
        if (applyUrlCoverBtn) applyUrlCoverBtn.classList.add('hidden');

        // Store the original cover for cancel
        this.originalCoverInEditor = currentCoverSrc;
    },

    handleCoverFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = e.target.result;
            console.log('handleCoverFileUpload - setting pendingCover with dataURL');
            this.pendingCover = dataUrl;

            // Update preview
            const editorPreview = document.getElementById('editor-cover-preview');
            const editorPlaceholder = document.getElementById('editor-cover-placeholder');
            const removeCoverBtn = document.getElementById('remove-cover-btn');

            if (editorPreview) {
                editorPreview.src = dataUrl;
                editorPreview.classList.remove('hidden');
            }
            if (editorPlaceholder) editorPlaceholder.classList.add('hidden');
            if (removeCoverBtn) removeCoverBtn.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    },

    handleCoverUrlInput() {
        const coverUrlInput = document.getElementById('cover-url-input');
        const applyUrlCoverBtn = document.getElementById('apply-url-cover-btn');
        if (!coverUrlInput) return;

        const url = coverUrlInput.value.trim();
        if (!url) {
            alert('Please enter a valid URL');
            return;
        }

        // Validate URL
        try {
            new URL(url);
        } catch (e) {
            alert('Please enter a valid URL');
            return;
        }

        console.log('handleCoverUrlInput - setting pendingCover to:', url);
        this.pendingCover = url;

        // Update preview
        const editorPreview = document.getElementById('editor-cover-preview');
        const editorPlaceholder = document.getElementById('editor-cover-placeholder');
        const removeCoverBtn = document.getElementById('remove-cover-btn');

        if (editorPreview) {
            editorPreview.src = url;
            editorPreview.classList.remove('hidden');
        }
        if (editorPlaceholder) editorPlaceholder.classList.add('hidden');
        if (removeCoverBtn) removeCoverBtn.classList.remove('hidden');

        // Hide URL input and Apply button after successful apply
        if (coverUrlInput) coverUrlInput.style.display = 'none';
        if (applyUrlCoverBtn) applyUrlCoverBtn.classList.add('hidden');
    },

    handleRemoveCover() {
        console.log('handleRemoveCover - clearing pendingCover');
        this.pendingCover = null;

        // Reset preview
        const editorPreview = document.getElementById('editor-cover-preview');
        const editorPlaceholder = document.getElementById('editor-cover-placeholder');
        const removeCoverBtn = document.getElementById('remove-cover-btn');

        if (editorPreview) {
            editorPreview.src = '';
            editorPreview.classList.add('hidden');
        }
        if (editorPlaceholder) editorPlaceholder.classList.remove('hidden');
        if (removeCoverBtn) removeCoverBtn.classList.add('hidden');
    },

    resetCoverEditor() {
        const editorPreview = document.getElementById('editor-cover-preview');
        const editorPlaceholder = document.getElementById('editor-cover-placeholder');
        const removeCoverBtn = document.getElementById('remove-cover-btn');
        const coverUrlInput = document.getElementById('cover-url-input');
        const applyUrlCoverBtn = document.getElementById('apply-url-cover-btn');

        if (editorPreview) {
            editorPreview.src = '';
            editorPreview.classList.add('hidden');
        }
        if (editorPlaceholder) editorPlaceholder.classList.remove('hidden');
        if (removeCoverBtn) removeCoverBtn.classList.add('hidden');
        if (coverUrlInput) {
            coverUrlInput.value = '';
            coverUrlInput.style.display = 'none';
        }
        if (applyUrlCoverBtn) applyUrlCoverBtn.classList.add('hidden');

        this.originalCoverInEditor = null;
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

            console.log('saveMetadata - pendingCover:', this.pendingCover);

            // Use pendingCover if set (from file upload or apply URL)
            if (this.pendingCover) {
                console.log('saveMetadata - saving cover to metadata');
                data.cover = this.pendingCover;
            }

            console.log('saveMetadata - data to send:', { ...data, cover: data.cover ? '***' : undefined });

            await this.api.updateMetadata(this.currentFile.path, data);

            console.log('saveMetadata - updateMetadata completed');
            this.pendingCover = null;
            this.resetCoverEditor();
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

    // LRC Timeline Editor
    showLrcEditor() {
        const lrcEditor = document.getElementById('lrc-editor');
        const mp3O3ics = document.getElementById('mp3-o3ics');
        const metadataDisplay = document.getElementById('metadata-display');
        const enhancePreview = document.getElementById('enhance-preview');
        const metadataEditor = document.getElementById('metadata-editor');

        // Hide other sections, keep mp3-o3ics visible for preview
        if (lrcEditor) lrcEditor.classList.remove('hidden');
        if (mp3O3ics) mp3O3ics.classList.remove('hidden'); // Keep visible for preview
        if (metadataDisplay) metadataDisplay.classList.add('hidden');
        if (enhancePreview) enhancePreview.classList.add('hidden');
        if (metadataEditor) metadataEditor.classList.add('hidden');

        // Store original o3ics for cancel
        this.originalLrcText = document.getElementById('meta-input-o3ics')?.value || '';
        this.isInLrcEditMode = true;

        // Reset offset input
        const offsetInput = document.getElementById('lrc-offset-input');
        if (offsetInput) offsetInput.value = '0';

        // Show the original lyrics preview first
        this.updateLrcEditorPreview();
    },

    updateLrcEditorPreview() {
        const preview = document.getElementById('lrc-editor-preview');
        const offsetInput = document.getElementById('lrc-offset-input');
        if (!offsetInput) return;

        const offset = parseFloat(offsetInput.value) || 0;
        const lines = this.originalLrcText.split('\n');

        // Parse and adjust timestamps, then render preview
        const adjustedLines = lines.map(line => {
            // Try to parse LRC timestamp
            const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/;
            const match = line.match(timeRegex);

            if (match) {
                const m = parseInt(match[1], 10);
                const s = parseInt(match[2], 10);
                const ms = match[3].length === 2 ? parseInt(match[3], 10) * 10 : parseInt(match[3], 10);
                const time = (m * 60) + s + (ms / 1000);
                const newTime = Math.max(0, time + offset);

                const newM = Math.floor(newTime / 60);
                const newS = Math.floor(newTime % 60);
                const newMs = Math.round((newTime % 1) * 1000);
                const newMsStr = newMs < 100 ? String(newMs).padStart(2, '0') : String(newMs).slice(0, 3);

                const textContent = line.replace(timeRegex, '').trim();
                return {
                    time: newTime,
                    text: textContent === '' ? '<span class="material-icons" style="font-size:14px">music_note</span>' : textContent
                };
            }
            return { time: null, text: line };
        });

        // Update text preview
        if (preview) {
            preview.innerHTML = lines.map((line, i) => {
                const adjLine = adjustedLines[i];
                const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/;
                if (adjLine.time !== null) {
                    const newM = Math.floor(adjLine.time / 60);
                    const newS = Math.floor(adjLine.time % 60);
                    const newMs = Math.round((adjLine.time % 1) * 1000);
                    const newMsStr = newMs < 100 ? String(newMs).padStart(2, '0') : String(newMs).slice(0, 3);
                    const newLine = `[${String(newM).padStart(2, '0')}:${String(newS).padStart(2, '0')}.${newMsStr}]${line.replace(timeRegex, '')}`;
                    return `<div class="lrc-preview-line">${this.escapeHtml(newLine)}</div>`;
                }
                return `<div class="lrc-preview-line">${this.escapeHtml(line)}</div>`;
            }).join('');
        }

        // Update mp3-o3ics preview with adjusted timestamps
        const mp3O3ics = document.getElementById('mp3-o3ics');
        if (mp3O3ics) {
            mp3O3ics.classList.add('synced');
            mp3O3ics.innerHTML = '';

            // Only show lines with timestamps
            const timedLines = adjustedLines.filter(l => l.time !== null);
            timedLines.forEach((line, index) => {
                const p = document.createElement('p');
                p.innerHTML = line.text;
                p.id = 'lrc-preview-line-' + index;
                p.dataset.time = line.time;
                // Mark as preview
                p.classList.add('lrc-preview-item');
                mp3O3ics.appendChild(p);
            });

            // Show any non-timed lines as well
            adjustedLines.filter(l => l.time === null).forEach(line => {
                const p = document.createElement('p');
                p.innerHTML = this.escapeHtml(line.text);
                p.style.color = 'var(--color-text-muted)';
                p.style.fontSize = '0.9em';
                mp3O3ics.appendChild(p);
            });

            // Store timed lines and start audio sync
            this.lrcEditorTimedLines = timedLines;
            this.currentLrcEditorIndex = -1;
            this.startLrcEditorAudioSync();
        }
    },

    startLrcEditorAudioSync() {
        const mp3Audio = document.getElementById('mp3-audio');
        if (!mp3Audio) return;

        // Remove existing listener
        if (this.lrcEditorAudioHandler) {
            mp3Audio.removeEventListener('timeupdate', this.lrcEditorAudioHandler);
        }

        // Create and bind handler
        this.lrcEditorAudioHandler = () => this.updateLrcEditorAudioSync();
        mp3Audio.addEventListener('timeupdate', this.lrcEditorAudioHandler);

        // Initial sync
        this.updateLrcEditorAudioSync();
    },

    updateLrcEditorAudioSync() {
        if (!this.lrcEditorTimedLines || this.lrcEditorTimedLines.length === 0) return;

        const mp3Audio = document.getElementById('mp3-audio');
        if (!mp3Audio) return;

        const currentTime = mp3Audio.currentTime;
        let newIndex = -1;

        for (let i = 0; i < this.lrcEditorTimedLines.length; i++) {
            if (currentTime >= this.lrcEditorTimedLines[i].time) {
                newIndex = i;
            } else {
                break;
            }
        }

        if (newIndex !== this.currentLrcEditorIndex) {
            // Remove highlight from previous
            if (this.currentLrcEditorIndex !== -1) {
                const oldEl = document.getElementById('lrc-preview-line-' + this.currentLrcEditorIndex);
                if (oldEl) oldEl.classList.remove('highlight');
            }

            this.currentLrcEditorIndex = newIndex;

            // Add highlight to new
            if (newIndex !== -1) {
                const newEl = document.getElementById('lrc-preview-line-' + newIndex);
                if (newEl) {
                    newEl.classList.add('highlight');

                    // Scroll to center
                    const container = document.getElementById('mp3-o3ics');
                    if (container) {
                        const scrollPos = newEl.offsetTop - container.offsetTop - (container.clientHeight / 2) + (newEl.clientHeight / 2);
                        container.scrollTo({ top: scrollPos, behavior: 'smooth' });
                    }
                }
            }
        }
    },

    stopLrcEditorAudioSync() {
        const mp3Audio = document.getElementById('mp3-audio');
        if (mp3Audio && this.lrcEditorAudioHandler) {
            mp3Audio.removeEventListener('timeupdate', this.lrcEditorAudioHandler);
            this.lrcEditorAudioHandler = null;
        }
        this.lrcEditorTimedLines = null;
        this.currentLrcEditorIndex = -1;
    },

    applyLrcOffset(multiplier) {
        const offsetInput = document.getElementById('lrc-offset-input');
        if (!offsetInput) return;

        const current = parseFloat(offsetInput.value) || 0;
        const step = multiplier;
        offsetInput.value = (current + step).toFixed(1);
        this.updateLrcEditorPreview();
    },

    async saveLrc() {
        const offsetInput = document.getElementById('lrc-offset-input');
        if (!offsetInput) return;

        const offset = parseFloat(offsetInput.value) || 0;
        if (offset === 0) {
            this.hideLrcEditor();
            return;
        }

        const lines = this.originalLrcText.split('\n');
        const newLines = lines.map(line => {
            const timeRegex = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/;
            const match = line.match(timeRegex);

            if (match) {
                const m = parseInt(match[1], 10);
                const s = parseInt(match[2], 10);
                const ms = match[3].length === 2 ? parseInt(match[3], 10) * 10 : parseInt(match[3], 10);
                const time = (m * 60) + s + (ms / 1000);
                const newTime = Math.max(0, time + offset);

                const newM = Math.floor(newTime / 60);
                const newS = Math.floor(newTime % 60);
                const newMs = Math.round((newTime % 1) * 1000);
                const newMsStr = newMs < 100 ? String(newMs).padStart(2, '0') : String(newMs).slice(0, 3);

                return `[${String(newM).padStart(2, '0')}:${String(newS).padStart(2, '0')}.${newMsStr}]${line.replace(timeRegex, '')}`;
            }
            return line;
        });

        const newLrcText = newLines.join('\n');

        // Update the input field
        const o3icsInput = document.getElementById('meta-input-o3ics');
        if (o3icsInput) o3icsInput.value = newLrcText;

        // Save to metadata
        try {
            const data = { o3ics: newLrcText };
            if (this.pendingCover) data.cover = this.pendingCover;
            await this.api.updateMetadata(this.currentFile.path, data);

            // Update display and re-render
            await this.loadMetadata();
        } catch (err) {
            alert('Failed to save LRC: ' + err.message);
        }

        this.hideLrcEditor();
    },

    cancelLrc() {
        this.isInLrcEditMode = false;
        this.hideLrcEditor();
    },

    hideLrcEditor() {
        // Stop audio sync first
        this.stopLrcEditorAudioSync();

        const lrcEditor = document.getElementById('lrc-editor');
        const mp3O3ics = document.getElementById('mp3-o3ics');
        const metadataDisplay = document.getElementById('metadata-display');

        if (lrcEditor) lrcEditor.classList.add('hidden');
        if (mp3O3ics) {
            mp3O3ics.classList.remove('hidden');
            mp3O3ics.classList.remove('lrc-edit-mode'); // Remove edit mode styling
            // Re-render with current input value
            const o3icsValue = document.getElementById('meta-input-o3ics')?.value || this.originalMetadata?.o3ics || '';
            this.renderLyrics(o3icsValue);
        }
        if (metadataDisplay) metadataDisplay.classList.remove('hidden');

        // Reset edit mode flag
        this.isInLrcEditMode = false;
        this.originalLrcText = null;
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    close() {
        const mp3Modal = document.getElementById('mp3-modal');
        const mp3Audio = document.getElementById('mp3-audio');

        // Stop and reset audio
        if (mp3Audio) {
            mp3Audio.pause();
            mp3Audio.currentTime = 0;
            mp3Audio.src = '';
        }

        // Clear current file
        this.currentFile = null;

        // Reset all state variables
        this.pendingCover = null;
        this.pendingCoverIndex = 0;
        this.coverOptions = [];
        this.pendingO3ics = null;
        this.pendingO3icsIndex = 0;
        this.o3icsOptions = [];
        this.lrcData = [];
        this.activeIndex = -1;
        this.selectedCoverSource = 'all';
        this.selectedO3icsSource = 'all';
        this.originalLrcText = null;

        // Clear display elements
        const clearElement = (id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '-';
        };

        clearElement('mp3-title');
        clearElement('meta-disp-title');
        clearElement('meta-disp-artist');
        clearElement('meta-disp-album');

        const coverEl = document.getElementById('mp3-cover');
        if (coverEl) {
            coverEl.src = '';
            coverEl.style.display = 'none';
        }

        const o3icsEl = document.getElementById('mp3-o3ics');
        if (o3icsEl) o3icsEl.innerHTML = '';

        // Clear editor inputs
        const clearInput = (id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        };

        clearInput('meta-input-title');
        clearInput('meta-input-artist');
        clearInput('meta-input-album');
        clearInput('meta-input-o3ics');

        // Reset enhance preview elements
        const clearEnhance = (id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '-';
        };

        clearEnhance('enhance-new-title');
        clearEnhance('enhance-new-artist');
        clearEnhance('enhance-new-album');
        clearEnhance('enhance-new-o3ics');

        const newCoverEl = document.getElementById('enhance-new-cover');
        if (newCoverEl) {
            newCoverEl.src = '';
            newCoverEl.classList.remove('has-image');
        }

        // Hide enhance containers
        const hideContainer = (id) => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        };

        hideContainer('enhance-preview');
        hideContainer('enhance-new-cover');
        hideContainer('cover-options-container');
        hideContainer('o3ics-options-container');
        hideContainer('cover-source-selector');
        hideContainer('o3ics-source-selector');
        hideContainer('lrc-editor');

        // Clear cover/lyrics options lists
        const coverList = document.getElementById('cover-options-list');
        if (coverList) coverList.innerHTML = '';

        const o3icsList = document.getElementById('o3ics-options-list');
        if (o3icsList) o3icsList.innerHTML = '';

        // Reset edit mode (cancels any edits)
        this.toggleEditMode(false);

        // Reset edit button visibility
        document.getElementById('edit-metadata-btn')?.classList.remove('hidden');
        document.getElementById('cancel-metadata-btn')?.classList.add('hidden');
        document.getElementById('save-metadata-btn')?.classList.add('hidden');

        // Hide modal
        if (mp3Modal) mp3Modal.classList.add('hidden');
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

// Make showCoverPreview available globally for onclick handlers
window.showCoverPreview = function(imgElement) {
    const src = imgElement.src;
    if (!src) return;
    const modal = document.getElementById('image-preview-modal');
    const img = document.getElementById('image-preview-img');
    if (modal && img) {
        img.src = src;
        modal.classList.remove('hidden');
    }
};


// Also set as global for HTML onclick handlers
window.mp3Player = mp3Player;




