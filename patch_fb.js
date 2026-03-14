const fs = require('fs');
let code = fs.readFileSync('home-assistant-addon/src/ui/js/fileBrowser.js', 'utf8');

// Injection 1: Video icon
code = code.replace(
    /else if \(item\.name\.toLowerCase\(\)\.endsWith\('\.mp3'\)\) \{\s+iconSpan\.textContent = '??';\s+\}/,
    `else if (item.name.toLowerCase().endsWith('.mp3')) {
                iconSpan.textContent = '??';
            } else if (item.name.toLowerCase().endsWith('.strm') || item.name.toLowerCase().endsWith('.mp4')) {
                iconSpan.textContent = '??';
            }`
);

// Injection 2: Click to open video player
code = code.replace(
    /else if \(item\.name\.toLowerCase\(\)\.match\(\/\\\\\.\(jpg\|jpeg\|png\|gif\|lrc\|txt\)\\\$\/\)\) \{\s+div\.addEventListener\('click', async \(\) => \{\s+const \{ mediaPreview \} = await import\('\.\/mediaPreview\.js'\);\s+mediaPreview\.open\(item\);\s+\}\);\s+\}/g,
    `else if (item.name.toLowerCase().match(/\\.(jpg|jpeg|png|gif|lrc|txt)$/)) {
                div.addEventListener('click', async () => {
                    const { mediaPreview } = await import('./mediaPreview.js');
                    mediaPreview.open(item);
                });
            } else if (item.name.toLowerCase().endsWith('.strm')) {
                div.addEventListener('click', async () => {
                    const { videoPlayer } = await import('./videoPlayer.js');
                    videoPlayer.open(item);
                });
            }`
);

fs.writeFileSync('home-assistant-addon/src/ui/js/fileBrowser.js', code);
