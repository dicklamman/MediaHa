export const mp3Player = {
    init() {
        const closeMp3Btn = document.getElementById('close-mp3');
        if (closeMp3Btn) {
            closeMp3Btn.addEventListener('click', () => this.close());
        }
    },
    
    open(file) {
        if (!file || file.type === 'folder') return;
        const mp3Modal = document.getElementById('mp3-modal');
        const mp3Title = document.getElementById('mp3-title');
        const mp3Audio = document.getElementById('mp3-audio');
        const mp3Cover = document.getElementById('mp3-cover');
        const mp3Lyrics = document.getElementById('mp3-lyrics');
        
        if (mp3Modal && mp3Title && mp3Audio) {
            mp3Title.textContent = file.name;
            const fileUrl = '/api/download?file_name=' + encodeURIComponent(file.path);
            
            // Set basic audio
            mp3Audio.src = fileUrl;
            
            // Reset cover and lyrics for now
            if (mp3Cover) mp3Cover.src = '';
            if (mp3Cover) mp3Cover.style.display = 'none';
            if (mp3Lyrics) mp3Lyrics.textContent = 'Loading metadata...';
            
            mp3Modal.classList.remove('hidden');
            mp3Audio.play().catch(e => console.log('Autoplay prevented', e));
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
