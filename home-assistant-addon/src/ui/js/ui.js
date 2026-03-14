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
            themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    },
    showContextMenu(x, y) {
        const menu = document.getElementById('context-menu');
        menu.style.left = x + 'px';
        menu.style.top = y + 'px';
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
        }
    },
    initTabs() {
const tabEpub=document.getElementById('tab-epub');
const tabMp3=document.getElementById('tab-mp3');
const tabAlist=document.getElementById('tab-alist');
const pageTitle=document.getElementById('page-title');
const viewBrowser=document.getElementById('view-file-browser');
const viewAlist=document.getElementById('view-alist');
if(tabEpub&&tabMp3&&tabAlist){
tabEpub.addEventListener('click',async ()=>{
tabEpub.classList.add('active');tabMp3.classList.remove('active');tabAlist.classList.remove('active');viewBrowser.classList.remove('hidden');viewAlist.classList.add('hidden');if(pageTitle)pageTitle.textContent='EPUB Converter';const {fileBrowser}=await import('./fileBrowser.js');fileBrowser.setBasePath('eBook');});
tabMp3.addEventListener('click',async ()=>{
tabMp3.classList.add('active');tabEpub.classList.remove('active');tabAlist.classList.remove('active');viewBrowser.classList.remove('hidden');viewAlist.classList.add('hidden');if(pageTitle)pageTitle.textContent='MP3 Converter';const {fileBrowser}=await import('./fileBrowser.js');fileBrowser.setBasePath('music');});
tabAlist.addEventListener('click',()=>{tabAlist.classList.add('active');tabEpub.classList.remove('active');tabMp3.classList.remove('active');viewBrowser.classList.add('hidden');viewAlist.classList.remove('hidden');});}}
};
