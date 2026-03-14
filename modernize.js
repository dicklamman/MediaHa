const fs = require('fs');
let css = fs.readFileSync('home-assistant-addon/src/ui/styles.css', 'utf8');

// Update font family and base styling
css = css.replace(/body \{\n    font-family: Arial, sans-serif;/g, "body {\n    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;");

// Make the container nicer
css = css.replace(/\.container \{\n    max-width: 100%;\n    margin: auto;\n    background: white;\n    padding: 20px;\n    border-radius: 8px;\n    box-shadow: 0 4px 6px rgba\(0,0,0,0.1\);\n\}/, 
`.container {
    max-width: 100%;
    margin: auto;
    background: var(--container-bg);
    padding: 24px;
    border-radius: 12px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.08);
    border: 1px solid var(--border-color);
}`);

// Buttons globally
css = css.replace(/\.btn \{ padding: 5px 15px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; \}/, 
`.btn { padding: 8px 16px; cursor: pointer; background: #0066cc; color: white; border: none; border-radius: 6px; font-weight: 500; transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(0,102,204,0.2); }
.btn:hover { background: #0052a3; transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,102,204,0.3); }
.btn:active { transform: translateY(0); }`);

// inputs
css = css.replace(/\.rename-input \{\n    font-size: 1em;\n    font-family: inherit;\n    padding: 2px 5px;\n    border: 1px solid #007bff;\n    border-radius: 3px;\n    width: 60%;\n    outline: none;\n\}/, 
`.rename-input {
    font-size: 1em;
    font-family: inherit;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    width: 100%;
    max-width: 60%;
    outline: none;
    background: var(--input-bg);
    color: var(--input-text);
    transition: all 0.2s ease;
}`);

// Inputs focus
css = css.replace(/\.rename-input:focus \{\n    box-shadow: 0 0 3px rgba\(0, 123, 255, 0\.5\);\n\}/, 
`.rename-input:focus {
    border-color: #0066cc;
    box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.2);
}`);

// Sidebar styling
css = css.replace(/\.sidebar \{\n    width: 250px;\n    background: var\(--container-bg\);\n    margin-right: 20px;\n    padding: 20px;\n    border-radius: 8px;\n    box-shadow: 0 4px 6px rgba\(0,0,0,0\.1\);\n    align-self: flex-start;\n\}/, 
`.sidebar {
    width: 260px;
    background: var(--container-bg);
    margin-right: 24px;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.08);
    border: 1px solid var(--border-color);
    align-self: flex-start;
}`);

fs.writeFileSync('home-assistant-addon/src/ui/styles.css', css);
