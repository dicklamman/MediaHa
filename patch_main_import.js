const fs = require('fs');
let code = fs.readFileSync('home-assistant-addon/src/ui/js/main.js', 'utf8');

// import videoPlayer
code = code.replace(
    /import \{ alist \} from '\.\/alist\.js';/,
    `import { alist } from './alist.js';\nimport { videoPlayer } from './videoPlayer.js';`
);

// call init
code = code.replace(
    /alist\.init\(\);/,
    `alist.init();\n    videoPlayer.init();`
);

fs.writeFileSync('home-assistant-addon/src/ui/js/main.js', code);
