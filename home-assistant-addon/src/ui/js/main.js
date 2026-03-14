import { ui } from './ui.js';
import { fileBrowser } from './fileBrowser.js';
import { epubPlayer } from './epubPlayer.js';
import { mp3Player } from './mp3Player.js';
import { api } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI components
    ui.initTheme();
    ui.initTabs();
    
    // Initialize feature modules
    fileBrowser.init();
    epubPlayer.init();
    mp3Player.init();

    // Global Event Listeners
    document.addEventListener('click', () => {
        ui.hideContextMenu();
    });

    const menuPreview = document.getElementById('menu-preview');
    const menuRename = document.getElementById('menu-rename');
    const menuConvert = document.getElementById('menu-convert');

    if (menuPreview) {
        menuPreview.addEventListener('click', () => {
            ui.hideContextMenu();
            const selectedFile = fileBrowser.selectedFile;
            if (selectedFile && selectedFile.type !== 'folder') {
                if (selectedFile.name.toLowerCase().endsWith('.mp3')) {
                    mp3Player.open(selectedFile, api);
                } else if (selectedFile.name.toLowerCase().endsWith('.epub')) {
                    epubPlayer.open(selectedFile);
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
