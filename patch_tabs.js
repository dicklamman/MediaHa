const fs = require('fs');
let code = fs.readFileSync('home-assistant-addon/src/ui/js/ui.js', 'utf8');

const regex = /initTabs\(\) \{[\s\S]*\}\}\s*\};/;
const newInit = `initTabs() {
    const tabEpub = document.getElementById('tab-epub');
    const tabMp3 = document.getElementById('tab-mp3');
    const tabAlistVideo = document.getElementById('tab-alist-video');
    const tabAlist = document.getElementById('tab-alist');
    const pageTitle = document.getElementById('page-title');
    const viewBrowser = document.getElementById('view-file-browser');
    const viewAlist = document.getElementById('view-alist');

    if (tabEpub && tabMp3 && tabAlistVideo && tabAlist) {
        tabEpub.addEventListener('click', async () => {
            tabEpub.classList.add('active');
            tabMp3.classList.remove('active');
            tabAlistVideo.classList.remove('active');
            tabAlist.classList.remove('active');
            viewBrowser.classList.remove('hidden');
            viewAlist.classList.add('hidden');
            if (pageTitle) pageTitle.textContent = 'EPUB Converter';
            const { fileBrowser } = await import('./fileBrowser.js');
            fileBrowser.setBasePath('eBook');
        });
        tabMp3.addEventListener('click', async () => {
            tabMp3.classList.add('active');
            tabEpub.classList.remove('active');
            tabAlistVideo.classList.remove('active');
            tabAlist.classList.remove('active');
            viewBrowser.classList.remove('hidden');
            viewAlist.classList.add('hidden');
            if (pageTitle) pageTitle.textContent = 'MP3 Converter';
            const { fileBrowser } = await import('./fileBrowser.js');
            fileBrowser.setBasePath('music');
        });
        tabAlistVideo.addEventListener('click', async () => {
            tabAlistVideo.classList.add('active');
            tabEpub.classList.remove('active');
            tabMp3.classList.remove('active');
            tabAlist.classList.remove('active');
            viewBrowser.classList.remove('hidden');
            viewAlist.classList.add('hidden');
            if (pageTitle) pageTitle.textContent = 'AList Video';
            const { fileBrowser } = await import('./fileBrowser.js');
            fileBrowser.setBasePath('alist');
        });
        tabAlist.addEventListener('click', () => {
            tabAlist.classList.add('active');
            tabEpub.classList.remove('active');
            tabMp3.classList.remove('active');
            tabAlistVideo.classList.remove('active');
            viewBrowser.classList.add('hidden');
            viewAlist.classList.remove('hidden');
        });
    }
}
};`;

code = code.replace(regex, newInit);
fs.writeFileSync('home-assistant-addon/src/ui/js/ui.js', code);
