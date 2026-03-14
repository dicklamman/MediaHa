const fs = require('fs');
let css = fs.readFileSync('home-assistant-addon/src/ui/styles.css', 'utf8');

// Modernize modals
css = css.replace(/#preview-modal \{\n    position: fixed; top: 3%; left: 5%; right: 5%; bottom: 3%;\n    background: white; border: 1px solid #ccc;\n    box-shadow: 0 0 15px rgba\(0,0,0,0\.5\);\n    z-index: 2000;\n    display: flex; flex-direction: column;\n    border-radius: 8px;\n    overflow: hidden;\n\}/g,
`#preview-modal {
    position: fixed; top: 5%; left: 5%; right: 5%; bottom: 5%;
    background: var(--modal-bg);
    border: 1px solid var(--border-color);
    box-shadow: 0 12px 24px rgba(0,0,0,0.15);
    z-index: 2000;
    display: flex; flex-direction: column;
    border-radius: 12px;
    overflow: hidden;
}`);

css = css.replace(/#mp3-modal \{\n    position: fixed; top: 3%; left: 5%; right: 5%; bottom: 3%;\n    background: var\(--modal-bg\); border: 1px solid var\(--border-color\);\n    box-shadow: 0 0 15px var\(--modal-overlay\);\n    z-index: 2000;\n    display: flex; flex-direction: column;\n    border-radius: 8px;\n    overflow: hidden;\n\}/g,
`#mp3-modal {
    position: fixed; top: 5%; left: 5%; right: 5%; bottom: 5%;
    background: var(--modal-bg);
    border: 1px solid var(--border-color);
    box-shadow: 0 12px 24px rgba(0,0,0,0.15);
    z-index: 2000;
    display: flex; flex-direction: column;
    border-radius: 12px;
    overflow: hidden;
}`);

// Change buttons inline colors to use CSS variables
fs.writeFileSync('home-assistant-addon/src/ui/styles.css', css);
