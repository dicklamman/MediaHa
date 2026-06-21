import { ui } from './ui.js';
import { fileBrowser } from './fileBrowser.js';
import { epubPlayer } from './epubPlayer.js';
import { mp3Player } from './mp3Player.js';
import { alist } from './alist.js';
import { videoPlayer } from './videoPlayer.js';
import { assEditor } from './assEditor.js';
import { api } from './api.js';

// Authentication check - redirect to login if not authenticated
async function checkAuth() {
    try {
        const response = await fetch('/api/auth/status');
        if (response.status === 401 || !response.ok) {
            window.location.href = '/login.html';
            return false;
        }
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login.html';
            return false;
        }
        return true;
    } catch (e) {
        console.error('Auth check failed:', e);
        window.location.href = '/login.html';
        return false;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication first
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) {
        return; // Stop initialization if not authenticated
    }

    // Initialize feature modules first (order matters!)
    fileBrowser.init();
    
    // Initialize UI components (uses fileBrowser.setBasePath)
    ui.initTheme();
    ui.initMobileNav();

    // Initialize feature modules
    epubPlayer.init();
    mp3Player.init();
    alist.init();
    videoPlayer.init();
    assEditor.init();
    
    // Fallback: load eBook if initTabs didn't work
    if (!fileBrowser.currentPath || fileBrowser.currentPath === '') {
        setTimeout(() => fileBrowser.setBasePath('eBook'), 200);
    }

    // Global Event Listeners
    document.addEventListener('contextmenu', (e) => {
        // Don't hide context menu if right-clicking on a file item (it will be shown by fileBrowser)
        if (e.target.closest('.file-item')) {
            e.stopPropagation();
        }
    });
    
    document.addEventListener('click', (e) => {
        // Don't hide context menu if clicking on menu item
        if (e.target.closest('.menu-item')) {
            return;
        }
        ui.hideContextMenu();

        // Close modals if clicking outside of them
        const previewModal = document.getElementById('preview-modal');
        const videoModal = document.getElementById('video-modal');

        if (previewModal && !previewModal.classList.contains('hidden')) {       
            if (!previewModal.contains(e.target) && !e.target.closest('.file-item')) {
                epubPlayer.close();
                previewModal.classList.add('hidden');
                const pContent = document.getElementById('preview-content');    
                if (pContent) pContent.innerHTML = '';
            }
        }

        if (videoModal && !videoModal.classList.contains('hidden')) {
            if (!videoModal.contains(e.target) && !e.target.closest('.file-item')) {
                import('./videoPlayer.js').then(({videoPlayer}) => videoPlayer.close());
            }
        }
    });

    const menuPreview = document.getElementById('menu-preview');
    const menuRename = document.getElementById('menu-rename');
    const menuConvert = document.getElementById('menu-convert');
    const menuEditAss = document.getElementById('menu-edit-ass');
    
    // Debug logging to check if elements exist
    console.log('main.js running');
    console.log('menu-preview:', menuPreview);
    console.log('menu-rename:', menuRename);
    console.log('menu-convert:', menuConvert);
    console.log('menu-edit-ass:', menuEditAss);

    // Global debug for menu-item clicks
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            console.log('Menu item clicked:', e.target.id, e.target.textContent);
        });
    });

    if (menuPreview) {
        console.log('Attaching click handler to menuPreview');
        menuPreview.addEventListener('click', async () => {
            console.log('menuPreview clicked!');
            ui.hideContextMenu();
            const selectedFile = fileBrowser.selectedFile;
            console.log('selectedFile:', selectedFile);
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
        console.log('Attaching click handler to menuRename');
        menuRename.addEventListener('click', async () => {
            console.log('menuRename clicked!');
            await fileBrowser.handleRename();
        });
    }

    if (menuConvert) {
        console.log('Attaching click handler to menuConvert');
        menuConvert.addEventListener('click', async () => {
            console.log('menuConvert clicked!');
            await fileBrowser.handleConvert();
        });
    }

    if (menuEditAss) {
        menuEditAss.addEventListener('click', async () => {
            ui.hideContextMenu();
            const selectedFile = fileBrowser.selectedFile;
            if (selectedFile && (selectedFile.name.toLowerCase().endsWith('.ass') || selectedFile.name.toLowerCase().endsWith('.ssa'))) {
                assEditor.open(selectedFile);
            }
        });
    }

    const menuEditEpubMetadata = document.getElementById('menu-edit-epub-metadata');
    if (menuEditEpubMetadata) {
        menuEditEpubMetadata.addEventListener('click', async () => {
            ui.hideContextMenu();
            const selectedFile = fileBrowser.selectedFile;
            if (selectedFile && selectedFile.name.toLowerCase().endsWith('.epub')) {
                const { epubMetadataEditor } = await import('./epubMetadataEditor.js');
                epubMetadataEditor.open(selectedFile, api);
            }
        });
    }

    // Initial load
    fileBrowser.loadFiles('');
});
