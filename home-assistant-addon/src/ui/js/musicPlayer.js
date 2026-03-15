// Music Player Module
// Handles playlist, playback controls, lyrics sync, and persistent state

const MusicPlayer = {
    audio: null,
    playlist: [],
    currentIndex: -1,
    isPlaying: false,
    shuffle: false,
    repeat: 'none', // 'none', 'one', 'all'
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

    bindTabEvents() {
        const tab = document.getElementById('tab-music-player');
        const view = document.getElementById('view-music-player');

        if (tab && view) {
            tab.addEventListener('click', () => {
                this.showView();
            });
        }
    },

    showView() {
        // Hide all views
        document.querySelectorAll('.main-wrapper > div').forEach(div => {
            if (div.id !== 'view-music-player') {
                div.classList.add('hidden');
            }
        });
        document.getElementById('view-music-player').classList.remove('hidden');

        // Update sidebar active state
        document.querySelectorAll('.sidebar-nav li').forEach(li => li.classList.remove('active'));
        document.getElementById('tab-music-player').classList.add('active');

        // Hide mini player when in music player view
        document.getElementById('mini-player').classList.add('hidden');
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
                items = data.files || data.items || data || [];
            }

            console.log('Items found:', items);

            // Build playlist - handle various item formats
            this.playlist = [];
            for (const item of items) {
                // Handle string items (just filenames)
                if (typeof item === 'string') {
                    if (/\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(item)) {
                        this.playlist.push({
                            name: item,
                            path: `/media/music/${item}`,
                            title: item.replace(/\.[^.]+$/, ''),
                            artist: 'Unknown Artist'
                        });
                    }
                } else if (item && typeof item === 'object') {
                    // Handle object items
                    const name = item.name || item.filename || '';
                    if (/\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(name)) {
                        // Use the path if available, otherwise construct it
                        let fullPath = item.path;
                        if (!fullPath || fullPath === name) {
                            // If path is just the filename or missing, prepend /media/music/
                            fullPath = `/media/music/${name}`;
                        }
                        this.playlist.push({
                            name: name,
                            path: fullPath,
                            title: name.replace(/\.[^.]+$/, ''),
                            artist: 'Unknown Artist'
                        });
                    }
                }
            }

            console.log('Music playlist loaded:', this.playlist);

            // Show message if no tracks found
            if (this.playlist.length === 0) {
                document.getElementById('playlist').innerHTML = '<div style="padding:20px;color:#888;text-align:center">No audio files found in /media/music</div>';
            }

            this.renderPlaylist();
            document.getElementById('playlist-count').textContent = this.playlist.length;

            // Restore last playing track
            this.restoreLastTrack();
        } catch (err) {
            console.error('Failed to load playlist:', err);
            document.getElementById('playlist').innerHTML = '<div style="padding:20px;color:red;text-align:center">Error loading playlist: ' + err.message + '</div>';
        }
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
        this.renderPlaylist();
        this.loadLyrics(track.path);
        this.showMiniPlayer();
    },

    async loadLyrics(trackPath) {
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
        container.innerHTML = '';

        if (!lrcText) {
            container.innerHTML = '<p class="no-lyrics">No lyrics available</p>';
            return;
        }

        // Parse LRC format
        const lines = lrcText.split('\n');
        const lyrics = [];

        for (const line of lines) {
            const match = line.match(/\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)/);
            if (match) {
                const minutes = parseInt(match[1]);
                const seconds = parseInt(match[2]);
                const ms = parseInt(match[3].padEnd(3, '0'));
                const time = minutes * 60 + seconds + ms / 1000;
                const text = match[4].trim();
                if (text) {
                    lyrics.push({ time, text });
                }
            }
        }

        this.lyrics = lyrics;
        this.renderLyricsDisplay();
    },

    renderLyricsDisplay() {
        const container = document.getElementById('music-o3ics');

        if (!this.lyrics || this.lyrics.length === 0) {
            container.innerHTML = '<p class="no-lyrics">No lyrics available</p>';
            return;
        }

        container.innerHTML = this.lyrics.map((line, i) =>
            `<div class="lyric-line" data-index="${i}">${line.text}</div>`
        ).join('');
    },

    updateSyncedLyrics() {
        if (!this.lyrics || this.lyrics.length === 0) return;

        const currentTime = this.audio.currentTime;
        let activeIndex = -1;

        for (let i = this.lyrics.length - 1; i >= 0; i--) {
            if (currentTime >= this.lyrics[i].time) {
                activeIndex = i;
                break;
            }
        }

        document.querySelectorAll('.lyric-line').forEach((el, i) => {
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
            nextIndex = Math.floor(Math.random() * this.playlist.length);
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
            prevIndex = Math.floor(Math.random() * this.playlist.length);
        } else {
            prevIndex = (this.currentIndex - 1 + this.playlist.length) % this.playlist.length;
        }

        this.playTrack(prevIndex);
    },

    toggleShuffle() {
        this.shuffle = !this.shuffle;
        document.getElementById('music-shuffle').classList.toggle('active', this.shuffle);
        this.saveState();
    },

    toggleRepeat() {
        const modes = ['none', 'all', 'one'];
        const currentModeIndex = modes.indexOf(this.repeat);
        this.repeat = modes[(currentModeIndex + 1) % modes.length];

        const btn = document.getElementById('music-repeat');
        btn.classList.remove('active', 'active-one');
        if (this.repeat === 'all') btn.classList.add('active');
        if (this.repeat === 'one') btn.classList.add('active-one');

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
            progress.value = percent;
            miniProgress.value = percent;
        }

        currentTimeEl.textContent = this.formatTime(this.audio.currentTime);
        durationEl.textContent = this.formatTime(this.audio.duration || 0);

        this.updateSyncedLyrics();
    },

    onLoadedMetadata() {
        document.getElementById('music-duration').textContent = this.formatTime(this.audio.duration);
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

        playPauseBtn.textContent = icon;
        miniPlayPauseBtn.textContent = icon;

        if (this.currentIndex >= 0 && this.currentIndex < this.playlist.length) {
            const track = this.playlist[this.currentIndex];

            // Main player
            document.getElementById('music-title').textContent = track.title;
            document.getElementById('music-artist').textContent = track.artist;

            // Mini player
            document.getElementById('mini-title').textContent = track.title;
            document.getElementById('mini-artist').textContent = track.artist;
        }
    },

    showMiniPlayer() {
        // Only show mini player if not on music player page
        const viewMusicPlayer = document.getElementById('view-music-player');
        if (viewMusicPlayer.classList.contains('hidden')) {
            document.getElementById('mini-player').classList.remove('hidden');
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

                // Restore UI state - check elements exist first
                const volumeEl = document.getElementById('music-volume');
                const shuffleEl = document.getElementById('music-shuffle');
                const repeatEl = document.getElementById('music-repeat');

                if (volumeEl) volumeEl.value = this.volume * 100;
                if (shuffleEl) shuffleEl.classList.toggle('active', this.shuffle);

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
        if (!this.savedState || !this.savedState.playlist || this.playlist.length === 0) return;

        // Find saved track index by path
        const savedPath = this.savedState.playlist[0];
        let index = this.playlist.findIndex(t => t.path === savedPath);

        // If not found by exact path, try to find by filename
        if (index === -1) {
            const savedFilename = savedPath.split('/').pop();
            index = this.playlist.findIndex(t => t.path.endsWith(savedFilename) || t.name === savedFilename);
        }

        if (index >= 0) {
            this.currentIndex = index;
            const track = this.playlist[index];

            // Set up audio but don't auto-play
            const fileUrl = '/api/download?file_name=' + encodeURIComponent(track.path);
            this.audio.src = fileUrl;

            // Restore position
            if (this.savedState.currentTime) {
                this.audio.currentTime = this.savedState.currentTime;
            }

            this.updateUI();
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
