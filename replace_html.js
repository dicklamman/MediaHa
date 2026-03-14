const fs = require('fs');
let html = fs.readFileSync('home-assistant-addon/src/ui/index.html', 'utf8');

const replacement = '<div id="mp3-content">\n' +
'            <div id="mp3-top-layout">\n' +
'                <img id="mp3-cover" src="" alt="Album Art" />\n' +
'                <div id="mp3-lyrics"></div>\n' +
'            </div>\n' +
'            \n' +
'            <audio id="mp3-audio" controls style="width: 100%; margin-top:10px;"></audio>\n\n' +
'            <!-- Metadata Reader / Editor -->';

html = html.replace(/<div id="mp3-content">[\s\S]*?<!-- Metadata Reader \/ Editor -->/, replacement);
html = html.replace('<div id="mp3-lyrics" style="max-height: 200px; overflow-y:auto; margin-top:10px; padding:10px; background:var(--info-bg); white-space:pre-wrap; border-radius: 4px;"></div>', '');

fs.writeFileSync('home-assistant-addon/src/ui/index.html', html, 'utf8');
