const fs = require('fs');
let css = fs.readFileSync('home-assistant-addon/src/ui/styles.css', 'utf8');

css = css.replace(/#context-menu \{\n    background: var\(--context-menu-bg\);\n    border-color: var\(--border-color\);\n\}/, 
`#context-menu {
    background: var(--context-menu-bg);
    border: 1px solid var(--border-color);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    border-radius: 8px;
    padding: 4px 0;
}`);

css = css.replace(/\.menu-item \{\n    padding: 10px 15px;\n    cursor: pointer;\n\}/, 
`.menu-item {
    padding: 10px 20px;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s, color 0.15s;
}`);

css = css.replace(/\.file-item \{\n    padding: 10px;\n    border-bottom: 1px solid #eee;\n    cursor: pointer;\n    display: flex;\n    align-items: center;\n    user-select: none;\n\}/, 
`.file-item {
    padding: 14px 16px;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    display: flex;
    align-items: center;
    user-select: none;
    transition: background 0.2s;
}`);

// Scrollbars inside file browser
css += `
#file-browser::-webkit-scrollbar {
    width: 8px;
}
#file-browser::-webkit-scrollbar-track {
    background: transparent;
}
#file-browser::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 10px;
}
#file-browser::-webkit-scrollbar-thumb:hover {
    background: #bbb;
}
`;

fs.writeFileSync('home-assistant-addon/src/ui/styles.css', css);
