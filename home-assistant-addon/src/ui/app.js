document.addEventListener('DOMContentLoaded', () => {
    const fileBrowser = document.getElementById('file-browser');
    const dynamicCrumbs = document.getElementById('dynamic-crumbs');
    const rootCrumb = document.getElementById('root-crumb');
    const resultMessage = document.getElementById('result');
    const contextMenu = document.getElementById('context-menu');
    const menuConvert = document.getElementById('menu-convert');
    const menuPreview = document.getElementById('menu-preview');
    const menuRename = document.getElementById('menu-rename');
    const previewModal = document.getElementById('preview-modal');
    const closePreviewBtn = document.getElementById('close-preview');
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const previewContent = document.getElementById('preview-content');
    const previewTitle = document.getElementById('preview-title');
    
    let currentPath = '';
    let selectedFile = null;
    let book = null;
    let rendition = null;

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
                    if (menuPreview) menuPreview.style.display = 'none';
                } else {
                    menuConvert.textContent = 'Convert to 繁體 (Traditional)';
                    if (menuPreview) menuPreview.style.display = 'block';
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

    if (menuPreview) {
        menuPreview.addEventListener('click', () => {
            if (!selectedFile || selectedFile.type === 'folder') return;
            contextMenu.classList.add('hidden');
            
            previewTitle.textContent = selectedFile.name;
            previewModal.classList.remove('hidden');
            previewContent.innerHTML = '<div style="padding:20px;text-align:center;">Loading preview...</div>';

            const fileUrl = '/api/download?file_name=' + encodeURIComponent(selectedFile.path);
            
            book = ePub(fileUrl);
            previewContent.innerHTML = '';
            rendition = book.renderTo(previewContent, {
                width: "100%",
                height: "100%",
                spread: "none"
            });
            rendition.display();
        });
    }

    if (closePreviewBtn) {
        closePreviewBtn.addEventListener('click', () => {
            previewModal.classList.add('hidden');
            if (book) {
                book.destroy();
                book = null;
                rendition = null;
            }
            previewContent.innerHTML = '';
        });

        prevPageBtn.addEventListener('click', () => {
            if (rendition) rendition.prev();
        });

        nextPageBtn.addEventListener('click', () => {
            if (rendition) rendition.next();
        });
    }

    if (menuRename) {
        menuRename.addEventListener('click', async () => {
            if (!selectedFile) return;
            contextMenu.classList.add('hidden');
            
            const newName = prompt(`Enter new name for "${selectedFile.name}":`, selectedFile.name);
            if (!newName || newName === selectedFile.name) return;

            try {
                const response = await fetch('/api/rename', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ old_path: selectedFile.path, new_name: newName }),
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Rename failed');
                }

                resultMessage.className = 'success';
                resultMessage.textContent = 'Renamed successfully!';
                loadFiles(currentPath);
            } catch (err) {
                resultMessage.className = 'error';
                resultMessage.textContent = 'Rename error: ' + err.message;
            }
        });
    }

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
