// Music Player Module
// Handles playlist, playback controls, o3ics sync, and persistent state

const MusicPlayer = {
    audio: null,
    playlist: [],
    currentIndex: -1,
    isPlaying: false,
    shuffle: false,
    repeat: 'none',
    volume: 0.8,

    // State keys for localStorage
    STATE_KEY: 'mediaha_music_state',

    init() {
        this.audio = new Audio();
        this.audio.volume = this.volume;

        this.bindEvents();
        this.loadState();
        this.loadPlaylist();
    },

    bindEvents() {
        // Main controls
        const playPauseBtn = document.getElementById('music-play-pause');
        const prevBtn = document.getElementById('music-prev');
        const nextBtn = document.getElementById('music-next');
        const shuffleBtn = document.getElementById('music-shuffle');
        const repeatBtn = document.getElementById('music-repeat');

        if (playPauseBtn) playPauseBtn.addEventListener('click', () => this.togglePlay());
        if (prevBtn) prevBtn.addEventListener('click', () => this.playPrev());
        if (nextBtn) nextBtn.addEventListener('click', () => this.playNext());
        if (shuffleBtn) shuffleBtn.addEventListener('click', () => this.toggleShuffle());
        if (repeatBtn) repeatBtn.addEventListener('click', () => this.toggleRepeat());

        // Progress bar
        const progress = document.getElementById('music-progress');
        if (progress) {
            progress.addEventListener('input', (e) => this.seekTo(e.target.value));
            progress.addEventListener('change', () => this.saveState());
        }

        // Volume
        const volume = document.getElementById('music-volume');
        if (volume) {
            volume.addEventListener('input', (e) => this.setVolume(e.target.value / 100));
        }

        // Mini player controls
        const miniPlayPauseBtn = document.getElementById('mini-play-pause');
        const miniPrevBtn = document.getElementById('mini-prev');
        const miniNextBtn = document.getElementById('mini-next');
        const miniProgress = document.getElementById('mini-progress');
        const miniCloseBtn = document.getElementById('mini-close');

        if (miniPlayPauseBtn) miniPlayPauseBtn.addEventListener('click', () => this.togglePlay());
        if (miniPrevBtn) miniPrevBtn.addEventListener('click', () => this.playPrev());
        if (miniNextBtn) miniNextBtn.addEventListener('click', () => this.playNext());
        if (miniProgress) miniProgress.addEventListener('input', (e) => this.seekTo(e.target.value));
        if (miniCloseBtn) {
            miniCloseBtn.addEventListener('click', () => {
                this.audio.pause();
                this.updateUI();
            });
        }

        // Audio events
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('ended', () => this.onEnded());
        this.audio.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.audio.addEventListener('play', () => this.onPlayStateChange(true));
        this.audio.addEventListener('pause', () => this.onPlayStateChange(false));
    },

    async loadPlaylist() {
        try {
            const response = await fetch('/api/files?dir=' + encodeURIComponent('/media/music'));
            const data = await response.json();

            console.log('API response for /media/music:', data);

            // Handle different API response formats
            let items = [];
            if (Array.isArray(data)) {
                items = data;
            } else if (data && typeof data === 'object') {
                items = data.files || data.items || [];
            }

            console.log('Items found:', items);

            // Build playlist with metadata loading
            this.playlist = [];
            for (const item of items) {
                if (!item) continue;

                // Handle string items (just filenames)
                if (typeof item === 'string') {
                    if (/\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(item)) {
                        const track = await this.createTrackFromFile(item, `/media/music/${item}`);
                        if (track) this.playlist.push(track);
                    }
                } else if (typeof item === 'object') {
                    const name = item.name || item.filename || '';
                    if (!name || typeof name !== 'string') continue;

                    if (/\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(name)) {
                        let fullPath = item.path;
                        if (!fullPath || typeof fullPath !== 'string') {
                            fullPath = `/media/music/${name}`;
                        }
                        const track = await this.createTrackFromFile(name, fullPath);
                        if (track) this.playlist.push(track);
                    }
                }
            }

            console.log('Music playlist loaded:', this.playlist);

            this.renderPlaylist();

            const countEl = document.getElementById('playlist-count');
            if (countEl) countEl.textContent = this.playlist.length;

            // Show mini player toggle button when playlist is loaded
            const toggleBtn = document.getElementById('mini-player-toggle-btn');
            if (toggleBtn && this.playlist.length > 0) {
                toggleBtn.classList.remove('hidden');
            }

            // Restore last playing track
            this.restoreLastTrack();
        } catch (err) {
            console.error('Failed to load playlist:', err);
            const playlistEl = document.getElementById('playlist');
            if (playlistEl) {
                playlistEl.innerHTML = '<div style="padding:20px;color:red;text-align:center">Error loading playlist: ' + err.message + '</div>';
            }
        }
    },

    async createTrackFromFile(name, path) {
        // Extract title from filename (remove extension)
        let title = name.replace(/\.[^.]+$/, '');
        let artist = 'Unknown Artist';
        let album = 'Unknown Album';
        let coverUrl = '';

        // Try to get metadata from the file
        try {
            const metaResponse = await fetch('/api/metadata?file_name=' + encodeURIComponent(path));
            if (metaResponse.ok) {
                const metadata = await metaResponse.json();
                if (metadata) {
                    if (metadata.title) title = metadata.title;
                    if (metadata.artist) artist = metadata.artist;
                    if (metadata.album) album = metadata.album;
                }
            }
        } catch (err) {
            console.log('No metadata for:', name);
        }

        // Cover will be loaded from embedded MP3 metadata when playing
        // Skip external cover file detection to avoid console errors

        return {
            name: name,
            path: path,
            title: title,
            artist: artist,
            album: album,
            coverUrl: coverUrl
        };
    },

    renderPlaylist() {
        const container = document.getElementById('playlist');
        if (!container) return;

        container.innerHTML = '';

        if (this.playlist.length === 0) {
            container.innerHTML = '<div style="padding:20px;color:#888;text-align:center">No audio files found</div>';
            return;
        }

        this.playlist.forEach((track, index) => {
            const div = document.createElement('div');
            div.className = 'playlist-item' + (index === this.currentIndex ? ' active' : '');
            div.innerHTML = `
                <span class="playlist-item-index">${index + 1}</span>
                <span class="playlist-item-title">${track.title}</span>
                <span class="playlist-item-artist">${track.artist}</span>
            `;
            div.addEventListener('click', () => this.playTrack(index));
            container.appendChild(div);
        });
    },

    playTrack(index) {
        if (index < 0 || index >= this.playlist.length) return;

        this.currentIndex = index;
        const track = this.playlist[index];

        console.log('Playing track:', track);

        const fileUrl = '/api/download?file_name=' + encodeURIComponent(track.path);
        console.log('Audio src URL:', fileUrl);

        this.audio.src = fileUrl;

        this.audio.play().catch(err => {
            console.error('Error playing audio:', err);
        });

        this.updateUI();
        this.updateCover();
        this.renderPlaylist();
        this.loadLyrics(track.path);
        this.showMiniPlayer();
    },

    updateCover() {
        const track = this.playlist[this.currentIndex];
        if (!track) return;

        // Main player cover
        const coverEl = document.getElementById('music-cover');
        if (coverEl) {
            if (track.coverUrl) {
                coverEl.src = track.coverUrl;
                coverEl.style.display = 'block';
            } else {
                coverEl.src = '';
                coverEl.style.display = 'none';
            }
        }

        // Mini player cover
        const miniCoverEl = document.getElementById('mini-cover');
        if (miniCoverEl) {
            if (track.coverUrl) {
                miniCoverEl.src = track.coverUrl;
                miniCoverEl.style.display = 'block';
            } else {
                miniCoverEl.src = '';
                miniCoverEl.style.display = 'none';
            }
        }
    },

    async loadLyrics(trackPath) {
        if (!trackPath || typeof trackPath !== 'string') return;

        const lrcPath = trackPath.replace(/\.[^.]+$/, '.lrc');

        try {
            const response = await fetch('/api/download?file_name=' + encodeURIComponent(lrcPath));
            if (response.ok) {
                const lrcText = await response.text();
                this.renderLyrics(lrcText);
            } else {
                this.renderLyrics('');
            }
        } catch (err) {
            this.renderLyrics('');
        }
    },

    renderLyrics(lrcText) {
        const container = document.getElementById('music-o3ics');
        if (!container) return;

        container.innerHTML = '';

        const text = String(lrcText || '');

        if (!text) {
            container.innerHTML = '<p class="no-o3ics">No lyrics available</p>';
            return;
        }

        // Parse LRC format
        const lines = text.split('\n');
        const o3ics = [];

        for (const line of lines) {
            const match = line.match(/\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)/);
            if (match) {
                const minutes = parseInt(match[1]);
                const seconds = parseInt(match[2]);
                const ms = parseInt(match[3].padEnd(3, '0'));
                const time = minutes * 60 + seconds + ms / 1000;
                const o3icText = match[4].trim();
                if (o3icText) {
                    o3ics.push({ time, text: o3icText });
                }
            }
        }

        this.o3ics = o3ics;
        this.renderLyricsDisplay();
    },

    renderLyricsDisplay() {
        const container = document.getElementById('music-o3ics');
        if (!container) return;

        if (!this.o3ics || this.o3ics.length === 0) {
            container.innerHTML = '<p class="no-o3ics">No lyrics available</p>';
            return;
        }

        container.innerHTML = this.o3ics.map((line, i) =>
            `<div class="o3ic-line" data-index="${i}">${line.text}</div>`
        ).join('');
    },

    updateSyncedLyrics() {
        if (!this.o3ics || this.o3ics.length === 0) return;

        const currentTime = this.audio.currentTime;
        let activeIndex = -1;

        for (let i = this.o3ics.length - 1; i >= 0; i--) {
            if (currentTime >= this.o3ics[i].time) {
                activeIndex = i;
                break;
            }
        }

        document.querySelectorAll('.o3ic-line').forEach((el, i) => {
            el.classList.toggle('active', i === activeIndex);

            if (i === activeIndex) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    },

    togglePlay() {
        if (this.playlist.length === 0) return;

        if (this.currentIndex === -1) {
            this.playTrack(0);
        } else if (this.audio.paused) {
            this.audio.play();
        } else {
            this.audio.pause();
        }
    },

    playNext() {
        if (this.playlist.length === 0) return;

        let nextIndex;
        if (this.shuffle) {
            // Random track, not the same as current
            do {
                nextIndex = Math.floor(Math.random() * this.playlist.length);
            } while (nextIndex === this.currentIndex && this.playlist.length > 1);
        } else {
            nextIndex = (this.currentIndex + 1) % this.playlist.length;
        }

        this.playTrack(nextIndex);
    },

    playPrev() {
        if (this.playlist.length === 0) return;

        // If more than 3 seconds in, restart current track
        if (this.audio.currentTime > 3) {
            this.audio.currentTime = 0;
            return;
        }

        let prevIndex;
        if (this.shuffle) {
            // Random track, not the same as current
            do {
                prevIndex = Math.floor(Math.random() * this.playlist.length);
            } while (prevIndex === this.currentIndex && this.playlist.length > 1);
        } else {
            prevIndex = (this.currentIndex - 1 + this.playlist.length) % this.playlist.length;
        }

        this.playTrack(prevIndex);
    },

    toggleShuffle() {
        this.shuffle = !this.shuffle;
        const shuffleBtn = document.getElementById('music-shuffle');
        if (shuffleBtn) {
            if (this.shuffle) {
                shuffleBtn.classList.add('active');
            } else {
                shuffleBtn.classList.remove('active');
            }
        }
        this.saveState();
    },

    toggleRepeat() {
        const modes = ['none', 'all', 'one'];
        const currentModeIndex = modes.indexOf(this.repeat);
        this.repeat = modes[(currentModeIndex + 1) % modes.length];

        const btn = document.getElementById('music-repeat');
        if (btn) {
            btn.classList.remove('active', 'active-one');
            if (this.repeat === 'all') btn.classList.add('active');
            if (this.repeat === 'one') btn.classList.add('active-one');
        }

        this.saveState();
    },

    seekTo(value) {
        const duration = this.audio.duration || 0;
        this.audio.currentTime = (value / 100) * duration;
    },

    setVolume(value) {
        this.volume = value;
        this.audio.volume = value;
        this.saveState();
    },

    onTimeUpdate() {
        const progress = document.getElementById('music-progress');
        const currentTimeEl = document.getElementById('music-current-time');
        const durationEl = document.getElementById('music-duration');
        const miniProgress = document.getElementById('mini-progress');

        if (this.audio.duration) {
            const percent = (this.audio.currentTime / this.audio.duration) * 100;
            if (progress) progress.value = percent;
            if (miniProgress) miniProgress.value = percent;
        }

        if (currentTimeEl) currentTimeEl.textContent = this.formatTime(this.audio.currentTime);
        if (durationEl) durationEl.textContent = this.formatTime(this.audio.duration || 0);

        this.updateSyncedLyrics();
    },

    onLoadedMetadata() {
        const durationEl = document.getElementById('music-duration');
        if (durationEl) durationEl.textContent = this.formatTime(this.audio.duration);
    },

    onEnded() {
        if (this.repeat === 'one') {
            this.audio.currentTime = 0;
            this.audio.play();
        } else if (this.repeat === 'all' || this.currentIndex < this.playlist.length - 1) {
            this.playNext();
        } else {
            this.updateUI();
        }
    },

    onPlayStateChange(isPlaying) {
        this.isPlaying = isPlaying;
        this.updateUI();
    },

    updateUI() {
        const playPauseBtn = document.getElementById('music-play-pause');
        const miniPlayPauseBtn = document.getElementById('mini-play-pause');
        const icon = this.audio.paused ? '▶️' : '⏸️';

        if (playPauseBtn) playPauseBtn.textContent = icon;
        if (miniPlayPauseBtn) miniPlayPauseBtn.textContent = icon;

        if (this.currentIndex >= 0 && this.currentIndex < this.playlist.length) {
            const track = this.playlist[this.currentIndex];

            const titleEl = document.getElementById('music-title');
            const artistEl = document.getElementById('music-artist');
            const miniTitleEl = document.getElementById('mini-title');
            const miniArtistEl = document.getElementById('mini-artist');

            if (titleEl) titleEl.textContent = track.title;
            if (artistEl) artistEl.textContent = track.artist;
            if (miniTitleEl) miniTitleEl.textContent = track.title;
            if (miniArtistEl) miniArtistEl.textContent = track.artist;
        }
    },

    showMiniPlayer() {
        // Check if we're on the music player page
        const viewMusicPlayer = document.getElementById('view-music-player');
        const miniPlayer = document.getElementById('mini-player');

        if (!viewMusicPlayer || !miniPlayer) return;

        // Respect user's toggle preference
        const userEnabled = localStorage.getItem('mediaha_mini_player_visible') === 'true';

        // Show mini player only if NOT on music player page AND user enabled it
        if (!viewMusicPlayer.classList.contains('hidden')) {
            // We're on music player page - hide mini player
            miniPlayer.classList.add('hidden');
        } else if (userEnabled) {
            // User has enabled mini player and we're on another page
            miniPlayer.classList.remove('hidden');
        } else {
            miniPlayer.classList.add('hidden');
        }
    },

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    // State persistence
    saveState() {
        const state = {
            currentIndex: this.currentIndex,
            currentTime: this.audio.currentTime,
            volume: this.volume,
            shuffle: this.shuffle,
            repeat: this.repeat,
            playlist: this.playlist.map(t => t.path)
        };
        localStorage.setItem(this.STATE_KEY, JSON.stringify(state));
    },

    loadState() {
        try {
            const saved = localStorage.getItem(this.STATE_KEY);
            if (saved) {
                const state = JSON.parse(saved);
                this.volume = state.volume || 0.8;
                this.shuffle = state.shuffle || false;
                this.repeat = state.repeat || 'none';

                const volumeEl = document.getElementById('music-volume');
                const shuffleEl = document.getElementById('music-shuffle');
                const repeatEl = document.getElementById('music-repeat');

                if (volumeEl) volumeEl.value = this.volume * 100;
                if (shuffleEl) {
                    shuffleEl.classList.toggle('active', this.shuffle);
                }

                if (repeatEl) {
                    if (this.repeat === 'all') repeatEl.classList.add('active');
                    if (this.repeat === 'one') repeatEl.classList.add('active-one');
                }

                this.audio.volume = this.volume;
                this.savedState = state;
            }
        } catch (err) {
            console.error('Failed to load state:', err);
        }
    },

    restoreLastTrack() {
        // Validate saved state
        if (!this.savedState ||
            !this.savedState.playlist ||
            !Array.isArray(this.savedState.playlist) ||
            this.savedState.playlist.length === 0 ||
            this.playlist.length === 0) {
            return;
        }

        // Find saved track
        const savedPath = this.savedState.playlist[0];
        if (!savedPath || typeof savedPath !== 'string') return;

        let index = this.playlist.findIndex(t => t.path === savedPath);

        // Try by filename if not found
        if (index === -1 && savedPath.includes('/')) {
            const savedFilename = savedPath.split('/').pop();
            if (savedFilename) {
                index = this.playlist.findIndex(t =>
                    t.path.endsWith(savedFilename) || t.name === savedFilename
                );
            }
        }

        if (index >= 0) {
            this.currentIndex = index;
            const track = this.playlist[index];

            const fileUrl = '/api/download?file_name=' + encodeURIComponent(track.path);
            this.audio.src = fileUrl;

            if (this.savedState.currentTime) {
                this.audio.currentTime = this.savedState.currentTime;
            }

            this.updateUI();
            this.updateCover();
            this.renderPlaylist();
            this.loadLyrics(track.path);
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    MusicPlayer.init();
    window.MusicPlayer = MusicPlayer;
});
