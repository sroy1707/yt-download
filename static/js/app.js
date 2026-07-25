let eventSource = null;
let currentFolder = '';
let parsedVideoItems = [];
let inputDebounceTimer = null;
let activeFilter = 'all';
let searchQuery = '';

function initApp() {
    // Theme setup
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
    }

    // Saved Palette setup
    const savedPalette = localStorage.getItem('palette') || 'emerald';
    setThemePalette(savedPalette);

    // Saved path setup
    const savedPath = localStorage.getItem('download_path');
    const defaultPath = savedPath || './downloads';
    setDownloadPath(defaultPath);

    // Load quick system dirs & detect OS
    loadQuickDirs();

    // Start SSE tracking
    startProgressSSE();

    // Setup keyboard shortcuts & drag drop
    setupKeyboardShortcuts();
    setupDragAndDrop();

    // Light dismiss listener for dialogs
    setupDialogFallbacks();

    // Auto-parse inputs if browser restored text in the input box on refresh
    const textarea = document.getElementById('urls_input');
    if (textarea && textarea.value.trim()) {
        parseUrlsFromTextarea();
    }
}

function setThemePalette(paletteName, element) {
    document.body.classList.remove('theme-emerald', 'theme-crimson', 'theme-indigo', 'theme-amber');
    if (paletteName !== 'emerald') {
        document.body.classList.add(`theme-${paletteName}`);
    }

    localStorage.setItem('palette', paletteName);

    // Update active dot in nav
    document.querySelectorAll('.color-dot').forEach(dot => dot.classList.remove('active'));
    const activeDot = element || document.querySelector(`.dot-${paletteName}`);
    if (activeDot) activeDot.classList.add('active');
}

function setDownloadPath(path) {
    document.getElementById('download_path').value = path;
    document.getElementById('active-folder-display').innerText = path;
    document.getElementById('active-folder-display').title = path;
    localStorage.setItem('download_path', path);
}

function onUrlsInput() {
    clearTimeout(inputDebounceTimer);
    inputDebounceTimer = setTimeout(() => {
        parseUrlsFromTextarea();
    }, 300);
}

async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            const textarea = document.getElementById('urls_input');
            textarea.value = textarea.value ? textarea.value + '\n' + text : text;
            parseUrlsFromTextarea();
            showToast('Pasted links from clipboard!', 'success');
        }
    } catch (err) {
        showToast('Permission denied to read clipboard', 'error');
    }
}

function cleanInputText() {
    parseUrlsFromTextarea();
    if (parsedVideoItems.length > 0) {
        const cleanedUrls = parsedVideoItems.map(item => item.url).join('\n');
        document.getElementById('urls_input').value = cleanedUrls;
        showToast('Removed duplicate YouTube URLs!', 'success');
    }
}

function parseUrlsFromTextarea() {
    const rawText = document.getElementById('urls_input').value;
    const regex = /(https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be)\/[^\s]+)/gi;
    const matches = rawText.match(regex) || [];

    const uniqueUrls = Array.from(new Set(matches.map(u => u.trim())));

    const newItems = uniqueUrls.map(url => {
        const existing = parsedVideoItems.find(item => item.url === url);
        if (existing) return existing;
        return {
            url: url,
            fetched_title: '',
            thumbnail: '',
            author: '',
            isFetching: false
        };
    });

    parsedVideoItems = newItems;
    renderPreviewCards();

    parsedVideoItems.forEach(item => {
        if (!item.fetched_title && !item.isFetching) {
            fetchItemMetadata(item);
        }
    });
}

async function fetchItemMetadata(item) {
    item.isFetching = true;
    renderPreviewCards();

    try {
        const response = await fetch('/api/video_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: item.url })
        });

        const result = await response.json();
        if (result.success && result.data) {
            item.fetched_title = result.data.title || '';
            item.thumbnail = result.data.thumbnail || '';
            item.author = result.data.author || '';
        }
    } catch (err) {
    } finally {
        item.isFetching = false;
        renderPreviewCards();
    }
}

function renderPreviewCards() {
    const previewSection = document.getElementById('preview-section');
    const previewList = document.getElementById('url-preview-list');
    const countLabel = document.getElementById('preview-count-label');

    if (parsedVideoItems.length === 0) {
        previewSection.style.display = 'none';
        previewList.innerHTML = '';
        return;
    }

    previewSection.style.display = 'block';
    countLabel.innerText = `Detected Links Queue (${parsedVideoItems.length})`;

    previewList.innerHTML = '';
    parsedVideoItems.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'preview-card';

        const thumbHtml = item.thumbnail
            ? `<img src="${item.thumbnail}" class="preview-thumb" alt="Thumb">`
            : `<div class="preview-thumb">
                ${item.isFetching ? '<span class="spin">⏳</span>' : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z"></path><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"></polygon></svg>'}
              </div>`;

        const titleText = item.fetched_title 
            ? escapeHtml(item.fetched_title) 
            : (item.isFetching ? 'Fetching YouTube Title...' : 'Will extract title on download');

        const authorText = item.author ? `👤 ${escapeHtml(item.author)}` : '';

        card.innerHTML = `
            ${thumbHtml}
            <div class="preview-info">
                <div class="preview-title">${titleText}</div>
                ${authorText ? `<div class="preview-author">${authorText}</div>` : ''}
            </div>
            <button type="button" class="btn-remove-url" onclick="removeUrlItem(${index})" title="Remove link">&times;</button>
        `;
        previewList.appendChild(card);
    });
}

function removeUrlItem(index) {
    if (index >= 0 && index < parsedVideoItems.length) {
        parsedVideoItems.splice(index, 1);
        const remainingUrls = parsedVideoItems.map(item => item.url).join('\n');
        document.getElementById('urls_input').value = remainingUrls;
        renderPreviewCards();
    }
}

function clearTextarea() {
    document.getElementById('urls_input').value = '';
    parsedVideoItems = [];
    renderPreviewCards();
}

async function startDownloads(event) {
    if (event) event.preventDefault();

    const downloadPath = document.getElementById('download_path').value.trim();
    const qualitySelect = document.getElementById('global-quality');
    const quality = qualitySelect ? qualitySelect.value : 'best';

    parseUrlsFromTextarea();

    if (parsedVideoItems.length === 0) {
        showToast('Please paste at least one valid YouTube URL.', 'error');
        return;
    }

    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spin">⏳</span> Starting Downloads...`;

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                download_path: downloadPath,
                quality: quality,
                videos: parsedVideoItems
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(`Started ${result.downloads.length} downloads!`, 'success');
            clearTextarea();
        } else {
            showToast(result.message || 'Failed to start downloads', 'error');
        }
    } catch (err) {
        showToast('Connection error occurred.', 'error');
        console.error(err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Start Downloading Queue
        `;
    }
}

async function retrySingleDownload(id) {
    const qualitySelect = document.getElementById('global-quality');
    const quality = qualitySelect ? qualitySelect.value : 'best';

    try {
        const res = await fetch('/api/retry_download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, quality: quality })
        });
        const result = await res.json();
        if (result.success) {
            showToast('Retrying download...', 'success');
        } else {
            showToast(result.message || 'Could not retry download', 'error');
        }
    } catch (err) {
        showToast('Error retrying download', 'error');
    }
}

async function retryAllFailed() {
    const qualitySelect = document.getElementById('global-quality');
    const quality = qualitySelect ? qualitySelect.value : 'best';

    try {
        const res = await fetch('/api/retry_failed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quality: quality })
        });
        const result = await res.json();
        if (result.success && result.count > 0) {
            showToast(`Retrying ${result.count} failed downloads!`, 'success');
        } else {
            showToast('No failed downloads to retry.', 'info');
        }
    } catch (err) {
        showToast('Error retrying failed downloads', 'error');
    }
}

async function clearCompleted() {
    try {
        await fetch('/api/clear', { method: 'POST' });
        showToast('Cleared completed downloads.', 'success');
    } catch (err) {
        console.error(err);
    }
}

function setFilter(filterType, element) {
    activeFilter = filterType;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    element.classList.add('active');
    filterTransfers();
}

function onSearchInput() {
    searchQuery = document.getElementById('search-input').value.toLowerCase().trim();
    filterTransfers();
}

function filterTransfers() {
    const cards = document.querySelectorAll('.download-card');
    cards.forEach(card => {
        const status = card.dataset.status;
        const title = card.dataset.title || '';
        const url = card.dataset.url || '';

        const matchesFilter = (activeFilter === 'all') || (status === activeFilter);
        const matchesSearch = !searchQuery || title.toLowerCase().includes(searchQuery) || url.toLowerCase().includes(searchQuery);

        if (matchesFilter && matchesSearch) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}

function startProgressSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource("/progress");
    eventSource.onmessage = function (event) {
        try {
            const downloads = JSON.parse(event.data);
            renderProgress(downloads);
        } catch (err) {
            console.error("SSE parse error:", err);
        }
    };
}

function renderProgress(downloads) {
    const container = document.getElementById('progress-cards');
    const noDownloadsEl = document.getElementById('no-downloads');

    let totalCount = downloads ? downloads.length : 0;
    let activeCount = 0;
    let completedCount = 0;
    let failedCount = 0;
    let totalSpeedBytes = 0;

    if (!downloads || downloads.length === 0) {
        container.innerHTML = '';
        noDownloadsEl.style.display = 'block';
        updateStats(0, 0, 0, 0, '0 B/s');
        return;
    }

    noDownloadsEl.style.display = 'none';

    downloads.forEach(dl => {
        if (dl.status === 'downloading' || dl.status === 'pending') activeCount++;
        if (dl.status === 'completed') completedCount++;
        if (dl.status === 'error') failedCount++;

        if (dl.status === 'downloading' && dl.speed) {
            const speedStr = dl.speed.trim();
            totalSpeedBytes += parseSpeedStringToBytes(speedStr);
        }
    });

    const speedDisplay = formatBytesToSpeed(totalSpeedBytes);
    updateStats(totalCount, activeCount, completedCount, failedCount, speedDisplay);

    const activeIds = new Set(downloads.map(d => d.id));
    const existingCards = container.querySelectorAll('.download-card');
    existingCards.forEach(card => {
        if (!activeIds.has(card.dataset.id)) card.remove();
    });

    downloads.forEach(dl => {
        let card = container.querySelector(`.download-card[data-id="${dl.id}"]`);

        if (!card) {
            card = document.createElement('div');
            card.className = `download-card status-${dl.status}`;
            card.dataset.id = dl.id;

            const thumbSrc = dl.thumbnail || '';
            const thumbHtml = thumbSrc 
                ? `<img src="${thumbSrc}" class="dl-thumb" alt="Thumb">` 
                : `<div class="dl-thumb" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted);">
                     <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z"></path><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"></polygon></svg>
                   </div>`;

            card.innerHTML = `
                <div class="dl-header-row">
                    ${thumbHtml}
                    <div class="dl-main-info">
                        <div class="dl-title"></div>
                        <div class="dl-path-badge" title="Saved folder path">
                            📁 <span class="dl-save-path"></span>
                        </div>
                    </div>
                    <span class="status-badge"></span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill"></div>
                </div>
                <div class="card-foot-details">
                    <span class="dl-percent">0%</span>
                    <div class="dl-speed-eta" style="display: flex; gap: 0.75rem;">
                        <span class="dl-speed">0B/s</span>
                        <span class="dl-eta">--:--</span>
                    </div>
                    <div class="card-action-btns">
                        <button type="button" class="btn-secondary retry-btn" style="padding: 0.2rem 0.5rem; font-size: 0.74rem; display:none;" title="Retry Download">
                            🔄 Retry
                        </button>
                        <button type="button" class="btn-secondary copy-path-btn" style="padding: 0.2rem 0.5rem; font-size: 0.74rem;" title="Copy save path">
                            📁 Path
                        </button>
                        <button type="button" class="btn-secondary preview-video-btn" style="padding: 0.2rem 0.5rem; font-size: 0.74rem;" title="Watch Video">
                            ▶️ Preview
                        </button>
                        <a class="btn-primary local-download-btn" style="padding: 0.2rem 0.5rem; font-size: 0.74rem; text-decoration: none; display:none; align-items: center; gap: 0.25rem;" title="Download file to your local computer">
                            ⬇️ Save to PC
                        </a>
                    </div>
                </div>
                <div class="error-box" style="display:none; color: var(--accent-error); font-size: 0.8rem; background: rgba(239,68,68,0.1); padding: 0.5rem; border-radius:6px; margin-top: 0.3rem;"></div>
            `;
            container.appendChild(card);
        }

        card.className = `download-card status-${dl.status}`;
        card.dataset.status = dl.status;
        card.dataset.title = dl.custom_title || '';
        card.dataset.url = dl.url || '';

        card.querySelector('.dl-title').innerText = dl.custom_title || 'Extracting Title...';
        
        const savePath = dl.download_path || document.getElementById('download_path').value;
        card.querySelector('.dl-save-path').innerText = savePath;

        const copyBtn = card.querySelector('.copy-path-btn');
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(savePath);
            showToast('Save directory path copied to clipboard!', 'success');
        };

        const previewBtn = card.querySelector('.preview-video-btn');
        previewBtn.onclick = () => {
            openVideoModal(dl.url);
        };

        const localDownloadBtn = card.querySelector('.local-download-btn');
        if (dl.status === 'completed') {
            localDownloadBtn.style.display = 'inline-flex';
            localDownloadBtn.href = `/api/download_file/${dl.id}`;
            localDownloadBtn.setAttribute('download', '');
        } else {
            localDownloadBtn.style.display = 'none';
        }

        const retryBtn = card.querySelector('.retry-btn');
        if (dl.status === 'error') {
            retryBtn.style.display = 'inline-flex';
            retryBtn.onclick = () => retrySingleDownload(dl.id);
        } else {
            retryBtn.style.display = 'none';
        }

        const badge = card.querySelector('.status-badge');
        badge.className = `status-badge badge-${dl.status}`;
        badge.innerText = dl.status;

        const percentVal = dl.progress || '0%';
        card.querySelector('.progress-fill').style.width = percentVal;
        card.querySelector('.dl-percent').innerText = percentVal;

        const speedEtaSection = card.querySelector('.dl-speed-eta');
        if (dl.status === 'downloading') {
            speedEtaSection.style.display = 'flex';
            card.querySelector('.dl-speed').innerText = dl.speed || '0B/s';
            card.querySelector('.dl-eta').innerText = dl.eta ? `ETA: ${dl.eta}` : '';
        } else {
            speedEtaSection.style.display = 'none';
        }

        const errBox = card.querySelector('.error-box');
        if (dl.status === 'error' && dl.error) {
            errBox.style.display = 'block';
            errBox.innerText = dl.error;
        } else {
            errBox.style.display = 'none';
        }
    });

    filterTransfers();
}

function updateStats(total, active, completed, failed, totalSpeed) {
    document.getElementById('stat-total').innerText = total;
    document.getElementById('stat-active').innerText = active;
    document.getElementById('stat-completed').innerText = completed;
    document.getElementById('stat-failed').innerText = failed;
    document.getElementById('analytics-total-speed').innerText = totalSpeed;

    const completionRate = total > 0 ? Math.round((completed / total) * 100) : 0;
    document.getElementById('analytics-completion-rate').innerText = `${completionRate}%`;
}

function parseSpeedStringToBytes(speedStr) {
    const match = speedStr.match(/([\d\.]+)\s*([a-zA-Z\/]+)/);
    if (!match) return 0;
    const val = parseFloat(match[1]);
    const unit = match[2].toUpperCase();

    if (unit.includes('GIB') || unit.includes('GB')) return val * 1024 * 1024 * 1024;
    if (unit.includes('MIB') || unit.includes('MB')) return val * 1024 * 1024;
    if (unit.includes('KIB') || unit.includes('KB')) return val * 1024;
    return val;
}

function formatBytesToSpeed(bytes) {
    if (bytes <= 0) return '0 B/s';
    if (bytes >= 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GiB/s';
    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MiB/s';
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KiB/s';
    return bytes + ' B/s';
}

// --- Video Preview Modal ---
function openVideoModal(url) {
    let embedUrl = url;
    const videoIdMatch = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]+)/);
    if (videoIdMatch) {
        embedUrl = `https://www.youtube.com/embed/${videoIdMatch[1]}?autoplay=1`;
    }
    document.getElementById('video-iframe').src = embedUrl;
    document.getElementById('video-modal').showModal();
}

function closeVideoModal() {
    document.getElementById('video-iframe').src = '';
    document.getElementById('video-modal').close();
}

// --- Folder Picker Logic ---
function openFolderPicker() {
    const current = document.getElementById('download_path').value.trim();
    loadDirectory(current);
    const dialog = document.getElementById('folder-picker');
    dialog.showModal();
}

function closeFolderPicker() {
    document.getElementById('folder-picker').close();
}

async function loadQuickDirs() {
    try {
        const res = await fetch('/api/quick_dirs');
        const data = await res.json();
        if (data.success) {
            if (data.system) {
                const osBadge = document.getElementById('os-badge');
                if (osBadge) {
                    osBadge.innerText = `${data.system.icon} ${data.system.os_label}`;
                    osBadge.title = `Detected OS: ${data.system.platform_details}`;
                }
            }
            if (data.directories) {
                const container = document.getElementById('quick-dirs-container');
                if (container) {
                    container.innerHTML = '';
                }
                
                const mainContainer = document.getElementById('quick-dirs-main-container');
                if (mainContainer) {
                    mainContainer.innerHTML = '';
                }

                data.directories.forEach(d => {
                    if (container) {
                        const chip = document.createElement('button');
                        chip.type = 'button';
                        chip.className = 'chip-btn';
                        chip.innerText = d.name;
                        chip.onclick = () => loadDirectory(d.path);
                        container.appendChild(chip);
                    }

                    if (mainContainer) {
                        const mainChip = document.createElement('button');
                        mainChip.type = 'button';
                        mainChip.className = 'chip-btn';
                        mainChip.innerText = d.name;
                        mainChip.onclick = () => setDownloadPath(d.path);
                        mainContainer.appendChild(mainChip);
                    }
                });
            }
        }
    } catch (err) {}
}

async function loadDirectory(path) {
    const listContainer = document.getElementById('folder-list');
    listContainer.innerHTML = '<div style="padding: 2rem; text-align:center; color: var(--text-secondary);">Loading directory folders...</div>';

    try {
        const res = await fetch('/api/list_folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const result = await res.json();

        if (result.success) {
            currentFolder = result.current_path;
            document.getElementById('current-folder-path').value = currentFolder;
            const upBtn = document.getElementById('btn-folder-up');
            if (result.parent_path) {
                upBtn.disabled = false;
                upBtn.dataset.parent = result.parent_path;
            } else {
                upBtn.disabled = true;
            }
            renderFoldersList(result.folders);
        } else {
            listContainer.innerHTML = `<div style="padding: 1.5rem; text-align:center; color: var(--accent-error);">${result.message || 'Error'}</div>`;
        }
    } catch (err) {
        listContainer.innerHTML = `<div style="padding: 1.5rem; text-align:center; color: var(--accent-error);">Failed to load folders</div>`;
    }
}

function renderFoldersList(folders) {
    const container = document.getElementById('folder-list');
    container.innerHTML = '';
    if (!folders || folders.length === 0) {
        container.innerHTML = '<div style="padding: 2rem; text-align:center; color: var(--text-muted); font-size: 0.85rem;">No subfolders found</div>';
        return;
    }
    folders.forEach(f => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'folder-item';
        btn.onclick = () => loadDirectory(f.path);
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            <span>${escapeHtml(f.name)}</span>
        `;
        container.appendChild(btn);
    });
}

function navigateFolderUp() {
    const parent = document.getElementById('btn-folder-up').dataset.parent;
    if (parent) loadDirectory(parent);
}

async function createNewFolder() {
    const input = document.getElementById('new-folder-name');
    const name = input.value.trim();
    if (!name) return showToast('Enter folder name', 'error');

    try {
        const res = await fetch('/api/create_folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_path: currentFolder, folder_name: name })
        });
        const result = await res.json();
        if (result.success) {
            showToast('Folder created!', 'success');
            input.value = '';
            loadDirectory(currentFolder);
        } else {
            showToast(result.message || 'Could not create folder', 'error');
        }
    } catch (err) {
        showToast('Error creating folder', 'error');
    }
}

function confirmFolderSelection() {
    const inputPath = document.getElementById('current-folder-path').value.trim();
    const finalPath = inputPath || currentFolder;
    if (finalPath) {
        setDownloadPath(finalPath);
        showToast('Destination save folder set!', 'success');
        closeFolderPicker();
    } else {
        showToast('Please select or enter a valid folder path', 'error');
    }
}

function setupDragAndDrop() {
    const dropzone = document.getElementById('dropzone');
    const textarea = document.getElementById('urls_input');

    if (!dropzone || !textarea) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const text = e.dataTransfer.getData('text');
        if (text) {
            textarea.value = textarea.value ? textarea.value + '\n' + text : text;
            parseUrlsFromTextarea();
            showToast('Dropped links added to queue!', 'success');
        }
    });
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            startDownloads();
        }
    });

    const folderInput = document.getElementById('current-folder-path');
    if (folderInput) {
        folderInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                loadDirectory(folderInput.value.trim());
            }
        });
    }
}

function setupDialogFallbacks() {
    document.querySelectorAll('dialog').forEach(dialog => {
        dialog.addEventListener('click', e => {
            const rect = dialog.getBoundingClientRect();
            const inDialog = (
                rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
                rect.left <= e.clientX && e.clientX <= rect.left + rect.width
            );
            if (!inDialog) {
                dialog.close();
                if (dialog.id === 'video-modal') {
                    document.getElementById('video-iframe').src = '';
                }
            }
        });
    });
}

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    const theme = document.body.classList.contains('light-theme') ? 'light' : 'dark';
    localStorage.setItem('theme', theme);
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '2rem';
    toast.style.right = '2rem';
    toast.style.padding = '0.75rem 1.4rem';
    toast.style.borderRadius = '10px';
    toast.style.color = '#FFF';
    toast.style.fontWeight = '600';
    toast.style.fontSize = '0.88rem';
    toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.35)';
    toast.style.zIndex = '9999';
    toast.style.animation = 'slideDown 0.2s ease-out';
    toast.style.backgroundColor = type === 'success' ? 'var(--accent-success)' : (type === 'info' ? '#3B82F6' : 'var(--accent-error)');
    toast.innerText = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'all 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}
