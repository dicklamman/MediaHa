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
    const themeToggle = document.getElementById('theme-toggle');
    
    let currentPath = '';
    let selectedFile = null;
    let book = null;
    let rendition = null;

    // Theme Management
    const initTheme = () => {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeToggleIcon(savedTheme);
    };

    const updateThemeToggleIcon = (theme) => {
        if (themeToggle) {
            themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    };

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeToggleIcon(newTheme);
            
            // Re-render book if open to match theme
            if (rendition) {
                if (newTheme === 'dark') {
                    rendition.themes.register("dark", {
                        "body": { "background": "#2d2d2d", "color": "#e0e0e0" }
                    });
                    rendition.themes.select("dark");
                } else {
                    rendition.themes.register("light", {
                        "body": { "background": "white", "color": "#333" }
                    });
                    rendition.themes.select("light");
                }
            }
        });
    }

    initTheme();

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
            
            const iconSpan = document.createElement('span');
            iconSpan.className = 'icon';
            iconSpan.textContent = item.type === 'folder' ? '📁' : '📄';
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'item-name';
            nameSpan.textContent = item.name;
            
            div.appendChild(iconSpan);
            div.appendChild(nameSpan);
            
            item.nameSpan = nameSpan; // Store reference to inline edit later
            
            if (item.type === 'folder') {
                div.addEventListener('click', () => {
                    loadFiles(item.path);
                });
            } else {
                // Removed the right-click hint on left-click as requested
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
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            
            book = ePub(fileUrl);
            previewContent.innerHTML = '';
            rendition = book.renderTo(previewContent, {
                width: "100%",
                height: "100%",
                spread: "none"
            });
            
            if (currentTheme === 'dark') {
                rendition.themes.register("dark", {
                    "body": { "background": "#2d2d2d", "color": "#e0e0e0" }
                });
                rendition.themes.select("dark");
            }
            
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
            if (!selectedFile || !selectedFile.nameSpan) return;
            contextMenu.classList.add('hidden');
            
            const nameSpan = selectedFile.nameSpan;
            const originalName = selectedFile.name;
            
            // Create container for input and buttons
            const renameContainer = document.createElement('div');
            renameContainer.className = 'rename-container';

            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalName;
            input.className = 'rename-input';
            
            const confirmBtn = document.createElement('button');
            confirmBtn.textContent = '✓';
            confirmBtn.className = 'rename-btn rename-confirm';
            confirmBtn.title = 'Confirm Rename';

            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = '✕';
            cancelBtn.className = 'rename-btn rename-cancel';
            cancelBtn.title = 'Cancel';

            renameContainer.appendChild(input);
            renameContainer.appendChild(confirmBtn);
            renameContainer.appendChild(cancelBtn);
            
            nameSpan.style.display = 'none';
            nameSpan.parentNode.insertBefore(renameContainer, nameSpan.nextSibling);
            input.focus();

            // Select filename without extension if it's a file
            if (selectedFile.type === 'file') {
                const lastDot = originalName.lastIndexOf('.');
                if (lastDot > 0) {
                    input.setSelectionRange(0, lastDot);
                } else {
                    input.select();
                }
            } else {
                input.select();
            }

            let isSaving = false;

            const handleOutsideClick = (e) => {
                if (!renameContainer.contains(e.target)) {
                    cancelRename();
                }
            };
            
            // Short delay to avoid catching the immediate click that opened it
            setTimeout(() => document.addEventListener('click', handleOutsideClick), 0);

            const cleanup = () => {
                document.removeEventListener('click', handleOutsideClick);
            };

            const saveRename = async () => {
                if (isSaving) return;
                isSaving = true;
                
                const newName = input.value.trim();
                
                // If unchanged or empty, silently cancel
                if (!newName || newName === originalName) {
                    cancelRename();
                    return;
                }

                input.disabled = true;
                confirmBtn.disabled = true;
                cancelBtn.disabled = true;
                
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

                    cleanup();
                    resultMessage.className = 'success';
                    resultMessage.textContent = 'Renamed successfully!';
                    loadFiles(currentPath);
                } catch (err) {
                    resultMessage.className = 'error';
                    resultMessage.textContent = 'Rename error: ' + err.message;
                    cancelRename();
                }
            };

            const cancelRename = () => {
                cleanup();
                if (renameContainer.parentNode) {
                    renameContainer.parentNode.removeChild(renameContainer);
                }
                nameSpan.style.display = '';
            };

            confirmBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // prevent clicking file row
                saveRename();
            });

            cancelBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                cancelRename();
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    saveRename();
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    cancelRename();
                }
            });
            
            // Prevent file-item click event when clicking input
            input.addEventListener('click', (e) => e.stopPropagation());
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
