import json

js = """document.addEventListener('DOMContentLoaded', () => {
    const fileBrowser = document.getElementById('file-browser');
    const dynamicCrumbs = document.getElementById('dynamic-crumbs');
    const rootCrumb = document.getElementById('root-crumb');
    const resultMessage = document.getElementById('result');
    const contextMenu = document.getElementById('context-menu');
    const menuConvert = document.getElementById('menu-convert');
    
    let currentPath = '';
    let selectedFile = null;

    if(rootCrumb) { rootCrumb.addEventListener('click', () => loadFiles('')); }

    function updateBreadcrumb() {
        if(!dynamicCrumbs) return;
        dynamicCrumbs.innerHTML = '';
        if (!currentPath) return;
        
        const pathParts = currentPath.split('/');
        let builtPath = '';
        
        pathParts.forEach((part, index) => {
            if (!part) return;
            builtPath += (builtPath ? '/' : '') + part;
            
            const separator = document.createElement('span');
            separator.textContent = ' / ';
            dynamicCrumbs.appendChild(separator);
            
            const crumb = document.createElement('span');
            crumb.textContent = part;
            crumb.className = 'crumb';
            crumb.style.cursor = 'pointer';
            crumb.style.color = '#0056b3';
            crumb.style.textDecoration = 'underline';
            
            const targetPath = builtPath;
            crumb.addEventListener('click', () => {
                loadFiles(targetPath);
            });
            dynamicCrumbs.appendChild(crumb);
        });
    }

    async function loadFiles(dir = '') {
        currentPath = dir;
        updateBreadcrumb();
        fileBrowser.innerHTML = '<div style="padding:10px;">Loading...</div>';
        try {
            const response = await fetch('/api/files?dir=' + encodeURIComponent(dir));
            if (!response.ok) throw new Error('Failed to load files');
            const items = await response.json();
            renderFiles(items);
        } catch (err) {
            fileBrowser.innerHTML = '<div style="padding:10px;color:red">Error loading files. Ensure /media/eBook exists!</div>';
        }
    }

    function renderFiles(items) {
        fileBrowser.innerHTML = '';
        
        if (currentPath !== '') {
            const upDiv = document.createElement('div');
            upDiv.className = 'file-item';
            upDiv.innerHTML = '<span class="icon">📁</span> ..';
            upDiv.addEventListener('click', () => {
                const parts = currentPath.split('/');
                parts.pop();
                loadFiles(parts.join('/'));
            });
            fileBrowser.appendChild(upDiv);
        }

        if (items.length === 0 && currentPath === '') {
            fileBrowser.innerHTML += '<div style="padding:10px;color:#888;">No EPUB files found in /media/eBook</div>';
            return;
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'file-item';
            div.innerHTML = '<span class="icon">' + (item.type === 'folder' ? '📁' : '📄') + '</span> ' + item.name;
            
            if (item.type === 'folder') {
                div.addEventListener('click', () => {
                    loadFiles(item.path);
                });
            } else {
                div.addEventListener('click', () => {
                    resultMessage.className = 'info';
                    resultMessage.textContent = "Right-click '" + item.name + "' and select 'Convert to 繁體' to process.";
                });
            }

            div.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                if (item.type === 'file') {
                    selectedFile = item;
                    contextMenu.style.left = e.pageX + 'px';
                    contextMenu.style.top = e.pageY + 'px';
                    contextMenu.classList.remove('hidden');
                }
            });

            fileBrowser.appendChild(div);
        });
    }

    document.addEventListener('click', () => {
        if(contextMenu) contextMenu.classList.add('hidden');
    });

    if(menuConvert) {
        menuConvert.addEventListener('click', async () => {
            if (!selectedFile) return;
            
            resultMessage.className = 'info';
            resultMessage.textContent = 'Converting "' + selectedFile.name + '"... this may take a moment.';
            contextMenu.classList.add('hidden');
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_name: selectedFile.path }),
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Conversion failed');
                }

                const result = await response.json();
                resultMessage.className = 'success';
                resultMessage.textContent = 'Conversion successful! File exported to: ' + result.output_file;
                
                setTimeout(() => loadFiles(currentPath), 1500);
            } catch (error) {
                resultMessage.className = 'error';
                resultMessage.textContent = 'Error: ' + error.message;
            }
        });
    }

    loadFiles();
});"""

html = """<!DOCTYPE html>
<html lang="zh-HK">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPUB Converter</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h1>EPUB Converter</h1>
        <div id="breadcrumb-container"><span class="crumb" id="root-crumb" style="cursor:pointer; font-weight:bold; color:#0056b3;">/media/eBook</span><span id="dynamic-crumbs"></span></div>
        <div id="file-browser">
            <!-- Items populated here -->
        </div>
        <div id="result"></div>
    </div>

    <!-- Right-click context menu -->
    <div id="context-menu" class="hidden">
        <div class="menu-item" id="menu-convert">Convert to 繁體 (Traditional)</div>
    </div>

    <script src="app.js"></script>
</body>
</html>"""

with open('home-assistant-addon/src/ui/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
    
with open('home-assistant-addon/src/ui/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
