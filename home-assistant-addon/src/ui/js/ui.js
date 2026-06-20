// UI initialization module

export const ui = {
    initTheme() {
        // Ensure localStorage has a default theme to prevent flash
        if (!localStorage.getItem('theme')) {
            localStorage.setItem('theme', 'light');
        }

        const themeToggle = document.getElementById('theme-toggle');
        const savedTheme = localStorage.getItem('theme') || 'light';

        // Apply theme before first paint
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
            const icon = themeToggle.querySelector('.theme-toggle-icon');
            if (icon) {
                icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
        }
    },

    initMobileNav() {
        const toggleBtn = document.getElementById('mobile-nav-toggle');
        const sidebar = document.querySelector('.sidebar');

        if (!toggleBtn || !sidebar) return;

        const openSidebar = () => {
            sidebar.classList.add('open');
            document.body.style.overflow = 'hidden';
        };

        const closeSidebar = () => {
            sidebar.classList.remove('open');
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
        if (!menu) return;

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

            setTimeout(() => {
                resultMessage.className = '';
                resultMessage.textContent = '';
            }, 5000);
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    ui.initTheme();
    ui.initMobileNav();
});
