const fs = require('fs');
let code = fs.readFileSync('home-assistant-addon/src/ui/js/main.js', 'utf8');

code = code.replace(
    /const previewModal = document\.getElementById\('preview-modal'\);[\s\S]*?if \(pContent\) pContent\.innerHTML = '';\s*\}\s*\}/,
    `const previewModal = document.getElementById('preview-modal');
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
        }`
);

fs.writeFileSync('home-assistant-addon/src/ui/js/main.js', code);
