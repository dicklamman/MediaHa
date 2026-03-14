const fs = require('fs');
let html = fs.readFileSync('home-assistant-addon/src/ui/index.html', 'utf8');

html = html.replace(/<h1 id="page-title">EPUB Converter<\/h1>/, '<h1 id="page-title" style="margin-bottom: 20px; font-weight: 800; letter-spacing: -0.5px;">EPUB Converter</h1>');
html = html.replace(/<h1>AList to STRM<\/h1>/, '<h1 style="margin-bottom: 20px; font-weight: 800; letter-spacing: -0.5px;">AList to STRM</h1>');
html = html.replace(/<h2>Media Converter<\/h2>/, '<h2 style="font-weight: 800; letter-spacing: -0.5px; opacity: 0.9;">Media Converter</h2>');

fs.writeFileSync('home-assistant-addon/src/ui/index.html', html);
