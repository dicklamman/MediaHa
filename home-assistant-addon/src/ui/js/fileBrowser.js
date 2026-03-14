import { api } from './api.js';
import { ui } from './ui.js';

export const fileBrowser = {
    currentPath: 'eBook',
    basePath: 'eBook',
    selectedFile: null,

    init() {
        const rootCrumb = document.getElementById('root-crumb');
        if (rootCrumb) {
            rootCrumb.addEventListener('click', () => this.loadFiles(this.basePath));
        }
    },

    setBasePath(path) {
        this.basePath = path;
        const rootCrumb = document.getElementById('root-crumb');
        if (rootCrumb) {
            rootCrumb.textContent = `/media/${path}`;
        }
        this.loadFiles(path);
    },

    updateBreadcrumb() {
        const dynamicCrumbs = document.getElementById('dynamic-crumbs');
        if (!dynamicCrumbs) return;
        dynamicCrumbs.innerHTML = '';
        if (!this.currentPath) return;
        
        const pathParts = this.currentPath.split('/');
        let builtPath = '';
        
        pathParts.forEach((part) => {
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
                this.loadFiles(targetPath);
            });
            dynamicCrumbs.appendChild(crumb);
        });
    },

    async loadFiles(dir = '') {
        this.currentPath = dir;
        this.updateBreadcrumb();
        const fileBrowserEl = document.getElementById('file-browser');
        if(fileBrowserEl) fileBrowserEl.innerHTML = '<div style="padding:10px;">Loading...</div>';
        try {
            const items = await api.getFiles(dir);
            this.renderFiles(items);
        } catch (err) {
            if(fileBrowserEl) fileBrowserEl.innerHTML = '<div style="padding:10px;color:red">Error loading files. Ensure /media exists!</div>';
        }
    },

    renderFiles(items) {
        const fileBrowserEl = document.getElementById('file-browser');
        if(!fileBrowserEl) return;
        fileBrowserEl.innerHTML = '';
        
        if (this.currentPath !== '') {
            const upDiv = document.createElement('div');
            upDiv.className = 'file-item';
            upDiv.innerHTML = '<span class="icon">📁</span> ..';
            upDiv.addEventListener('click', () => {
                const parts = this.currentPath.split('/');
                parts.pop();
                this.loadFiles(parts.join('/'));
            });
            fileBrowserEl.appendChild(upDiv);
        }

        if (items.length === 0 && this.currentPath === '') {
            fileBrowserEl.innerHTML += '<div style="padding:10px;color:#888;">No files found here.</div>';
            return;
        }

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'file-item';
            
            const iconSpan = document.createElement('span');
            iconSpan.className = 'icon';
            if (item.type === 'folder') {
                iconSpan.textContent = '📁';
            } else if (item.name.toLowerCase().endsWith('.mp3')) {
                iconSpan.textContent = '🎵';
            } else if (item.name.toLowerCase().endsWith('.jpg') || item.name.toLowerCase().endsWith('.png')) {
                iconSpan.textContent = '🖼️';
            } else {
                iconSpan.textContent = '📄';
            }
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'item-name';
            nameSpan.textContent = item.name;
            
            div.appendChild(iconSpan);
            div.appendChild(nameSpan);
            
            item.nameSpan = nameSpan; 
            
            if (item.type === 'folder') {
                div.addEventListener('click', () => {
                    this.loadFiles(item.path);
                });
            }

            div.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.selectedFile = item;
                const menuConvert = document.getElementById('menu-convert');
                const menuPreview = document.getElementById('menu-preview');
                
                if (item.type === 'folder') {
                    if(menuConvert) menuConvert.textContent = 'Convert all in Folder to Traditional';
                    if (menuPreview) menuPreview.style.display = 'none';
                } else {
                    if(menuConvert) menuConvert.textContent = 'Convert to Traditional';
                    if (menuPreview) {
                        if (item.name.toLowerCase().endsWith('.mp3')) {
                            menuPreview.style.display = 'block';
                            menuPreview.textContent = 'Play MP3';
                        } else if (item.name.toLowerCase().endsWith('.epub')) {
                            menuPreview.style.display = 'block';
                            menuPreview.textContent = 'Preview Book';
                        } else {
                            menuPreview.style.display = 'none';
                        }
                    }
                }
                ui.showContextMenu(e.pageX, e.pageY);
            });

            fileBrowserEl.appendChild(div);
        });
    },

    async handleRename() {
        if (!this.selectedFile || !this.selectedFile.nameSpan) return;
        ui.hideContextMenu();
        
        const nameSpan = this.selectedFile.nameSpan;
        const originalName = this.selectedFile.name;
        
        const renameContainer = document.createElement('div');
        renameContainer.className = 'rename-container';

        const input = document.createElement('input');
        input.type = 'text';
        input.value = originalName;
        input.className = 'rename-input';
        
        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = '✔️';
        confirmBtn.className = 'rename-btn rename-confirm';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '❌';
        cancelBtn.className = 'rename-btn rename-cancel';

        renameContainer.appendChild(input);
        renameContainer.appendChild(confirmBtn);
        renameContainer.appendChild(cancelBtn);
        
        nameSpan.style.display = 'none';
        nameSpan.parentNode.insertBefore(renameContainer, nameSpan.nextSibling);
        input.focus();

        if (this.selectedFile.type === 'file') {
            const lastDot = originalName.lastIndexOf('.');
            if (lastDot > 0) input.setSelectionRange(0, lastDot);
            else input.select();
        } else {
            input.select();
        }

        let isSaving = false;

        const handleOutsideClick = (e) => {
            if (!renameContainer.contains(e.target)) cancelRename();
        };
        setTimeout(() => document.addEventListener('click', handleOutsideClick), 0);

        const cleanup = () => document.removeEventListener('click', handleOutsideClick);

        const saveRename = async () => {
            if (isSaving) return;
            isSaving = true;
            const newName = input.value.trim();
            
            if (!newName || newName === originalName) {
                cancelRename();
                return;
            }

            input.disabled = true;
            confirmBtn.disabled = true;
            cancelBtn.disabled = true;
            
            try {
                await api.renameFile(this.selectedFile.path, newName);
                cleanup();
                ui.showResultMessage('success', 'Renamed successfully!');
                this.loadFiles(this.currentPath);
            } catch (err) {
                ui.showResultMessage('error', 'Rename error: ' + err.message);
                cancelRename();
            }
        };

        const cancelRename = () => {
            cleanup();
            if (renameContainer.parentNode) renameContainer.parentNode.removeChild(renameContainer);
            nameSpan.style.display = '';
        };

        confirmBtn.addEventListener('click', (e) => { e.stopPropagation(); saveRename(); });
        cancelBtn.addEventListener('click', (e) => { e.stopPropagation(); cancelRename(); });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); saveRename(); }
            else if (e.key === 'Escape') { e.preventDefault(); cancelRename(); }
        });
        input.addEventListener('click', (e) => e.stopPropagation());
    },

    async handleConvert() {
        if (!this.selectedFile) return;
        ui.hideContextMenu();

        if (this.selectedFile.type === 'folder') {
            ui.showResultMessage('info', 'Scanning folder "' + this.selectedFile.name + '"...');
            try {
                const items = await api.getFiles(this.selectedFile.path);
                const epubs = items.filter(i => i.type === 'file' && i.name.toLowerCase().endsWith('.epub'));
                
                if (epubs.length === 0) {
                    ui.showResultMessage('info', 'No matching files found in this folder.');
                    return;
                }

                let successCount = 0; let errorCount = 0;
                for (let i = 0; i < epubs.length; i++) {
                    const epub = epubs[i];
                    ui.showResultMessage('info', `Converting ${i + 1} of ${epubs.length}: "${epub.name}"...`);
                    try {
                        await api.convertFile(epub.path);
                        successCount++;
                    } catch (e) {
                        errorCount++;
                    }
                }
                
                ui.showResultMessage(errorCount === 0 ? 'success' : 'info', `Batch conversion complete! ${successCount} successful, ${errorCount} failed.`);
                setTimeout(() => this.loadFiles(this.currentPath), 2500);
            } catch (err) {
                ui.showResultMessage('error', 'Error reading folder: ' + err.message);
            }
        } else {
            ui.showResultMessage('info', 'Converting "' + this.selectedFile.name + '"... this may take a moment.');
            try {
                const result = await api.convertFile(this.selectedFile.path);
                ui.showResultMessage('success', 'Conversion successful! File exported to: ' + result.output_file);
                setTimeout(() => this.loadFiles(this.currentPath), 1500);
            } catch (error) {
                ui.showResultMessage('error', 'Error: ' + error.message);
            }
        }
    }
};
