const fs = require('fs');
let html = fs.readFileSync('home-assistant-addon/src/ui/index.html', 'utf8');

// Update any hardcoded gray background buttons to look better or rely on CSS vars
html = html.replace(/<button id="auto-enhance-btn" class="btn" style="background:#28a745; margin-right:5px;">/g, '<button id="auto-enhance-btn" class="btn" style="background:#28a745; margin-right:8px; box-shadow: 0 2px 4px rgba(40,167,69,0.2);">');

html = html.replace(/<button class="btn btn-small revert-btn" data-field="([^"]+)" style="display:none; padding:2px 8px; font-size: 0\.8em; background:#6c757d;">/g, '<button class="btn btn-small revert-btn" data-field="$1" style="display:none; padding:4px 10px; font-size: 0.85em; background:var(--info-bg, #6c757d); color:var(--text-color, #fff); border-radius: 4px;">');

// update layout borders to test
html = html.replace(/<div style="margin-top: 15px; border: 1px solid var\(--border-color\); padding: 15px; border-radius: 8px;">/, '<div style="margin-top: 20px; border: 1px solid var(--border-color); padding: 20px; border-radius: 12px; background: var(--hover-bg); box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);">');

fs.writeFileSync('home-assistant-addon/src/ui/index.html', html);
