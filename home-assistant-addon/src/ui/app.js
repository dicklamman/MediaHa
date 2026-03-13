document.addEventListener('DOMContentLoaded', () => {
    const fileBrowser = document.getElementById('file-browser');
    const dynamicCrumbs = document.getElementById('dynamic-crumbs');
    const rootCrumb = document.getElementById('root-crumb');
    const resultMessage = document.getElementById('result');
    const contextMenu = document.getElementById('context-menu');
    const menuConvert = document.getElementById('menu-convert');
    
    let currentPath = '';
    let selectedFile = null;

    if (rootCrumb) {
        rootCrumb.addEventListener('click', () => loadFiles(''));
    }

    function updateBreadcrumb() {
        if (!dynamicCrumbs) return;
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
                selectedFile = item;
                if (item.type === 'folder') {
                    menuConvert.textContent = 'Convert all in Folder to 繁體';
                } else {
                    menuConvert.textContent = 'Convert to 繁體 (Traditional)';
                }
                contextMenu.style.left = e.pageX + 'px';
                contextMenu.style.top = e.pageY + 'px';
                contextMenu.classList.remove('hidden');
            });

            fileBrowser.appendChild(div);
        });
    }

    document.addEventListener('click', () => {
        contextMenu.classList.add('hidden');
    });

    menuConvert.addEventListener('click', async () => {
        if (!selectedFile) return;
        contextMenu.classList.add('hidden');

        if (selectedFile.type === 'folder') {
            await convertFolder(selectedFile);
        } else {
            await convertSingleFile(selectedFile);
        }
    });

    async function convertSingleFile(fileItem) {
        resultMessage.className = 'info';
        resultMessage.textContent = 'Converting "' + fileItem.name + '"... this may take a moment.';
        
        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_name: fileItem.path }),
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
    }

    async function convertFolder(folderItem) {
        resultMessage.className = 'info';
        resultMessage.textContent = 'Scanning folder "' + folderItem.name + '"...';
        try {
            const response = await fetch('/api/files?dir=' + encodeURIComponent(folderItem.path));
            if (!response.ok) throw new Error('Failed to list files');
            const items = await response.json();
            const epubs = items.filter(i => i.type === 'file' && i.name.toLowerCase().endsWith('.epub'));
            
            if (epubs.length === 0) {
                resultMessage.className = 'info';
                resultMessage.textContent = 'No EPUB files found in this folder.';
                return;
            }

            let successCount = 0;
            let errorCount = 0;

            for (let i = 0; i < epubs.length; i++) {
                const epub = epubs[i];
                resultMessage.className = 'info';
                resultMessage.textContent = `Converting ${i + 1} of ${epubs.length}: "${epub.name}"...`;
                
                try {
                    const res = await fetch('/convert', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ file_name: epub.path }),
                    });
                    if (!res.ok) throw new Error('Failed');
                    successCount++;
                } catch (e) {
                    errorCount++;
                }
            }
            
            resultMessage.className = errorCount === 0 ? 'success' : 'info';
            resultMessage.textContent = `Batch conversion complete! ${successCount} successful, ${errorCount} failed.`;
            setTimeout(() => loadFiles(currentPath), 2500);
        } catch (err) {
            resultMessage.className = 'error';
            resultMessage.textContent = 'Error reading folder: ' + err.message;
        }
    }

    loadFiles();
});
