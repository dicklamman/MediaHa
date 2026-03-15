export const ui = {
    initTheme() {
        const themeToggle = document.getElementById('theme-toggle');
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeToggleIcon(savedTheme);

        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-theme');
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('theme', newTheme);
                this.updateThemeToggleIcon(newTheme);

                window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: newTheme } }));
            });
        }
    },

    updateThemeToggleIcon(theme) {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.textContent = theme === 'dark' ? '\u2600' : '\u263D';
        }
    },

    initMobileNav() {
        const toggleBtn = document.getElementById('mobile-nav-toggle');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');

        if (!toggleBtn || !sidebar) return;

        const openSidebar = () => {
            sidebar.classList.add('open');
            overlay?.classList.add('visible');
            document.body.style.overflow = 'hidden';
        };

        const closeSidebar = () => {
            sidebar.classList.remove('open');
            overlay?.classList.remove('visible');
            document.body.style.overflow = '';
        };

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        overlay?.addEventListener('click', closeSidebar);

        // Close sidebar when clicking a nav item (mobile)
        const navItems = sidebar.querySelectorAll('.sidebar-nav li');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    closeSidebar();
                }
            });
        });

        // Close sidebar on resize to desktop
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                closeSidebar();
            }
        });
    },

    showContextMenu(x, y) {
        const menu = document.getElementById('context-menu');

        // Adjust position to keep menu within viewport
        const menuWidth = 180;
        const menuHeight = 150;
        const adjustedX = Math.min(x, window.innerWidth - menuWidth - 10);
        const adjustedY = Math.min(y, window.innerHeight - menuHeight - 10);

        menu.style.left = adjustedX + 'px';
        menu.style.top = adjustedY + 'px';
        menu.classList.remove('hidden');
    },

    hideContextMenu() {
        const menu = document.getElementById('context-menu');
        if (menu) menu.classList.add('hidden');
    },

    showResultMessage(type, message) {
        const resultMessage = document.getElementById('result');
        if (resultMessage) {
            resultMessage.className = type;
            resultMessage.textContent = message;

            // Auto-hide after 5 seconds
            setTimeout(() => {
                resultMessage.className = '';
                resultMessage.textContent = '';
            }, 5000);
        }
    },

    initTabs() {
        const tabEpub = document.getElementById('tab-epub');
        const tabMp3 = document.getElementById('tab-mp3');
        const tabMusicPlayer = document.getElementById('tab-music-player');
        const tabAlistVideo = document.getElementById('tab-alist-video');
        const tabAlist = document.getElementById('tab-alist');
        const tabDropbox = document.getElementById('tab-dropbox');
        const pageTitle = document.getElementById('page-title');
        const viewBrowser = document.getElementById('view-file-browser');
        const viewMusicPlayer = document.getElementById('view-music-player');
        const viewAlist = document.getElementById('view-alist');
        const viewDropbox = document.getElementById('view-dropbox');

        const setActiveTab = (activeTab, title) => {
            [tabEpub, tabMp3, tabMusicPlayer, tabAlistVideo, tabAlist, tabDropbox].forEach(tab => {
                if (tab) tab.classList.remove('active');
            });
            if (activeTab) activeTab.classList.add('active');
            if (pageTitle) pageTitle.textContent = title || '';
        };

        if (tabEpub && tabMp3 && tabAlistVideo && tabAlist) {
            tabEpub.addEventListener('click', async () => {
                setActiveTab(tabEpub, 'EPUB Converter');
                viewBrowser.classList.remove('hidden');
                viewBrowser.style.display = '';
                viewMusicPlayer.classList.add('hidden');
                viewAlist.classList.add('hidden');
                if (viewDropbox) {
                    viewDropbox.classList.add('hidden');
                    viewDropbox.style.display = 'none';
                }
                // Show mini player if there's a track loaded
                const miniPlayer = document.getElementById('mini-player');
                if (miniPlayer && window.MusicPlayer && window.MusicPlayer.currentIndex >= 0) {
                    miniPlayer.classList.remove('hidden');
                }
                const { fileBrowser } = await import('./fileBrowser.js');
                fileBrowser.setBasePath('eBook');
            });

            tabMp3.addEventListener('click', async () => {
                setActiveTab(tabMp3, 'MP3 Converter');
                viewBrowser.classList.remove('hidden');
                viewBrowser.style.display = '';
                viewMusicPlayer.classList.add('hidden');
                viewAlist.classList.add('hidden');
                if (viewDropbox) {
                    viewDropbox.classList.add('hidden');
                    viewDropbox.style.display = 'none';
                }
                // Show mini player if there's a track loaded
                const miniPlayer3 = document.getElementById('mini-player');
                if (miniPlayer3 && window.MusicPlayer && window.MusicPlayer.currentIndex >= 0) {
                    miniPlayer3.classList.remove('hidden');
                }
                const { fileBrowser } = await import('./fileBrowser.js');
                fileBrowser.setBasePath('music');
            });

            if (tabMusicPlayer) {
                tabMusicPlayer.addEventListener('click', async () => {
                    setActiveTab(tabMusicPlayer, 'Music Player');
                    viewBrowser.classList.add('hidden');
                    viewBrowser.style.display = 'none';
                    viewMusicPlayer.classList.remove('hidden');
                    viewAlist.classList.add('hidden');
                    if (viewDropbox) {
                        viewDropbox.classList.add('hidden');
                        viewDropbox.style.display = 'none';
                    }
                    // Hide mini player when on music player page
                    document.getElementById('mini-player').classList.add('hidden');
                });
            }

            tabAlistVideo.addEventListener('click', async () => {
                setActiveTab(tabAlistVideo, 'AList Video');
                viewBrowser.classList.remove('hidden');
                viewBrowser.style.display = '';
                viewMusicPlayer.classList.add('hidden');
                viewAlist.classList.add('hidden');
                if (viewDropbox) {
                    viewDropbox.classList.add('hidden');
                    viewDropbox.style.display = 'none';
                }
                // Show mini player if there's a track loaded
                const miniPlayer4 = document.getElementById('mini-player');
                if (miniPlayer4 && window.MusicPlayer && window.MusicPlayer.currentIndex >= 0) {
                    miniPlayer4.classList.remove('hidden');
                }
                const { fileBrowser } = await import('./fileBrowser.js');
                fileBrowser.setBasePath('alist');
            });

            tabAlist.addEventListener('click', () => {
                setActiveTab(tabAlist, 'AList to STRM');
                viewBrowser.classList.add('hidden');
                viewBrowser.style.display = 'none';
                viewMusicPlayer.classList.add('hidden');
                viewAlist.classList.remove('hidden');
                if (viewDropbox) {
                    viewDropbox.classList.add('hidden');
                    viewDropbox.style.display = 'none';
                }
                // Show mini player if there's a track loaded
                const miniPlayer5 = document.getElementById('mini-player');
                if (miniPlayer5 && window.MusicPlayer && window.MusicPlayer.currentIndex >= 0) {
                    miniPlayer5.classList.remove('hidden');
                }
            });

            if (tabDropbox) {
                tabDropbox.addEventListener('click', () => {
                    setActiveTab(tabDropbox, 'Dropbox Sync');
                    viewBrowser.classList.add('hidden');
                    viewBrowser.style.display = 'none';
                    viewMusicPlayer.classList.add('hidden');
                    viewAlist.classList.add('hidden');
                    if (viewDropbox) {
                        viewDropbox.classList.remove('hidden');
                        viewDropbox.style.display = '';
                    }
                    // Show mini player if there's a track loaded
                    const miniPlayer6 = document.getElementById('mini-player');
                    if (miniPlayer6 && window.MusicPlayer && window.MusicPlayer.currentIndex >= 0) {
                        miniPlayer6.classList.remove('hidden');
                    }
                });
            }
        }
    }
};
