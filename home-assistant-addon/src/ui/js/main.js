import { ui } from './ui.js';
import { fileBrowser } from './fileBrowser.js';
import { epubPlayer } from './epubPlayer.js';
import { mp3Player } from './mp3Player.js';
import { alist } from './alist.js';
import { api } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI components
    ui.initTheme();
    ui.initTabs();
    
    // Initialize feature modules
    fileBrowser.init();
    epubPlayer.init();
    mp3Player.init();
    alist.init();

    // Global Event Listeners
    document.addEventListener('click', (e) => {
        ui.hideContextMenu();

        // Close modals if clicking outside of them
        const mp3Modal = document.getElementById('mp3-modal');
        if (mp3Modal && !mp3Modal.classList.contains('hidden')) {
            if (!mp3Modal.contains(e.target) && !e.target.closest('.file-item') && !e.target.closest('.menu-item')) {
                mp3Player.close();
            }
        }

        const previewModal = document.getElementById('preview-modal');
        if (previewModal && !previewModal.classList.contains('hidden')) {       
            if (!previewModal.contains(e.target) && !e.target.closest('.file-item') && !e.target.closest('.menu-item')) {
                epubPlayer.close();
                previewModal.classList.add('hidden');
                const pContent = document.getElementById('preview-content');    
                if (pContent) pContent.innerHTML = '';
            }
        }

        const videoModal = document.getElementById('video-modal');
        if (videoModal && !videoModal.classList.contains('hidden')) {
            if (!videoModal.contains(e.target) && !e.target.closest('.file-item') && !e.target.closest('.menu-item')) {
                import('./videoPlayer.js').then(({videoPlayer}) => videoPlayer.close());
            }
        }
    });

    const menuPreview = document.getElementById('menu-preview');
    const menuRename = document.getElementById('menu-rename');
    const menuConvert = document.getElementById('menu-convert');

    if (menuPreview) {
        menuPreview.addEventListener('click', async () => {
            ui.hideContextMenu();
            const selectedFile = fileBrowser.selectedFile;
            if (selectedFile && selectedFile.type !== 'folder') {
                if (selectedFile.name.toLowerCase().endsWith('.mp3')) {
                    mp3Player.open(selectedFile, api);
                } else if (selectedFile.name.toLowerCase().endsWith('.epub')) {
                    epubPlayer.open(selectedFile);
                } else if (selectedFile.name.toLowerCase().match(/\.(jpg|jpeg|png|gif|lrc|txt)$/)) {
                    const { mediaPreview } = await import('./mediaPreview.js');
                    mediaPreview.open(selectedFile);
                } else {
                    window.open('/api/download?file_name=' + encodeURIComponent(selectedFile.path), '_blank');
                }
            }
        });
    }

    if (menuRename) {
        menuRename.addEventListener('click', async () => {
            await fileBrowser.handleRename();
        });
    }

    if (menuConvert) {
        menuConvert.addEventListener('click', async () => {
            await fileBrowser.handleConvert();
        });
    }

    // Initial load
    fileBrowser.loadFiles('');
});
