export const mp3Player = {
    currentFile: null,
    api: null,

    init() {
        const closeMp3Btn = document.getElementById('close-mp3');
        if (closeMp3Btn) closeMp3Btn.addEventListener('click', () => this.close());

        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');

        if (editBtn) editBtn.addEventListener('click', () => this.toggleEditMode(true));
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveMetadata());
    },

    async open(file, apiInstance) {
        if (!file || file.type === 'folder') return;
        this.currentFile = file;
        this.api = apiInstance || window.api; // fallback if passed globally

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

    async loadMetadata() {
        try {
            const metadata = await this.api.getMetadata(this.currentFile.path);
            
            document.getElementById('meta-disp-title').textContent = metadata.title || 'Unknown Title';
            document.getElementById('meta-disp-artist').textContent = metadata.artist || 'Unknown Artist';
            document.getElementById('meta-disp-album').textContent = metadata.album || 'Unknown Album';

            document.getElementById('meta-input-title').value = metadata.title || '';
            document.getElementById('meta-input-artist').value = metadata.artist || '';
            document.getElementById('meta-input-album').value = metadata.album || '';
            document.getElementById('meta-input-lyrics').value = metadata.lyrics || '';

            const mp3Lyrics = document.getElementById('mp3-lyrics');
            if (mp3Lyrics) mp3Lyrics.textContent = metadata.lyrics || 'No lyrics found for this item.';

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

    toggleEditMode(isEdit) {
        const displayDiv = document.getElementById('metadata-display');
        const editorDiv = document.getElementById('metadata-editor');
        const editBtn = document.getElementById('edit-metadata-btn');
        const saveBtn = document.getElementById('save-metadata-btn');
        const lyricsDiv = document.getElementById('mp3-lyrics');

        if (isEdit) {
            displayDiv.classList.add('hidden');
            editorDiv.classList.remove('hidden');
            editBtn.classList.add('hidden');
            saveBtn.classList.remove('hidden');
            lyricsDiv.classList.add('hidden');
        } else {
            displayDiv.classList.remove('hidden');
            editorDiv.classList.add('hidden');
            editBtn.classList.remove('hidden');
            saveBtn.classList.add('hidden');
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

        try {
            await this.api.updateMetadata(this.currentFile.path, data);
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
