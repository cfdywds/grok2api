// 图片管理 JavaScript

// 工作区初始化（在 DOMContentLoaded 之前异步执行）
let _workspaceReady = false;
(async () => {
    if (typeof Workspace === 'undefined') return;
    if (!Workspace.isSupported()) return;

    const handle = await Workspace.initWorkspace();
    if (handle) {
        const perm = await handle.queryPermission({ mode: 'readwrite' });
        if (perm === 'granted') {
            _workspaceReady = true;
        }
    }
})();

// 从 localStorage 读取用户偏好
function loadUserPreferences() {
    const savedPageSize = localStorage.getItem('gallery_page_size');
    const savedViewMode = localStorage.getItem('gallery_view_mode');

    // 验证 pageSize 是否在有效范围内（最大 200）
    let pageSize = savedPageSize ? parseInt(savedPageSize) : 100;
    if (pageSize > 200) {
        pageSize = 200;
        localStorage.setItem('gallery_page_size', '200');
    }

    return {
        pageSize: pageSize,
        viewMode: savedViewMode || 'grid'
    };
}

const userPrefs = loadUserPreferences();

// 全局状态
const state = {
    images: [],
    selectedIds: new Set(),
    currentPage: 1,
    pageSize: userPrefs.pageSize,
    totalPages: 0,
    total: 0,
    viewMode: userPrefs.viewMode,
    filters: {
        search: '',
        model: '',
        aspectRatio: '',
        sortBy: 'created_at',
        sortOrder: 'desc',
        favorite: null,
    },
    currentImageId: null,
    currentImageIndex: -1,
};

// Toast 通知系统
const Toast = {
    show(message, type = 'info', title = '', duration = 3000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const titles = {
            success: title || '成功',
            error: title || '错误',
            warning: title || '警告',
            info: title || '提示'
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type]}</div>
            <div class="toast-content">
                <div class="toast-title">${titles[type]}</div>
                <div class="toast-message">${message}</div>
            </div>
            <div class="toast-close">×</div>
        `;

        container.appendChild(toast);

        // 关闭按钮
        toast.querySelector('.toast-close').addEventListener('click', () => {
            this.remove(toast);
        });

        // 自动关闭
        if (duration > 0) {
            setTimeout(() => {
                this.remove(toast);
            }, duration);
        }

        return toast;
    },

    remove(toast) {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => {
            toast.remove();
        }, 300);
    },

    success(message, title = '') {
        return this.show(message, 'success', title);
    },

    error(message, title = '') {
        return this.show(message, 'error', title);
    },

    warning(message, title = '') {
        return this.show(message, 'warning', title);
    },

    info(message, title = '') {
        return this.show(message, 'info', title);
    }
};

// 自定义确认对话框
const ConfirmDialog = {
    show(options) {
        return new Promise((resolve) => {
            const {
                title = '确认操作',
                message = '确定要执行此操作吗？',
                icon = '❓',
                confirmText = '确定',
                cancelText = '取消',
                confirmClass = 'btn-danger'
            } = options;

            const dialog = document.createElement('div');
            dialog.className = 'confirm-dialog';
            dialog.innerHTML = `
                <div class="confirm-dialog-content">
                    <div class="confirm-dialog-icon">${icon}</div>
                    <div class="confirm-dialog-title">${title}</div>
                    <div class="confirm-dialog-message">${message}</div>
                    <div class="confirm-dialog-actions">
                        <button class="btn btn-secondary cancel-btn">${cancelText}</button>
                        <button class="btn ${confirmClass} confirm-btn">${confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);

            const confirmBtn = dialog.querySelector('.confirm-btn');
            const cancelBtn = dialog.querySelector('.cancel-btn');

            const close = (result) => {
                dialog.style.animation = 'fadeIn 0.2s ease reverse';
                setTimeout(() => {
                    dialog.remove();
                    resolve(result);
                }, 200);
            };

            confirmBtn.addEventListener('click', () => close(true));
            cancelBtn.addEventListener('click', () => close(false));
            dialog.addEventListener('click', (e) => {
                if (e.target === dialog) close(false);
            });

            // ESC 键关闭
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    close(false);
                    document.removeEventListener('keydown', escHandler);
                }
            };
            document.addEventListener('keydown', escHandler);
        });
    }
};

// 工具函数
function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

// API 调用
async function fetchStats() {
    try {
        if (!window.Workspace || !Workspace.getHandle()) return;
        const meta = await Workspace.readMetadata();
        const images = meta.images || [];

        const total = images.length;
        const totalSize = images.reduce((s, img) => s + (img.file_size || 0), 0);
        const now = Date.now();
        const monthAgo = now - 30 * 24 * 60 * 60 * 1000;
        const monthCount = images.filter(img => img.created_at && img.created_at > monthAgo).length;

        const tagCounts = {};
        images.forEach(img => (img.tags || []).forEach(t => { tagCounts[t] = (tagCounts[t] || 0) + 1; }));
        const topTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([tag]) => tag);

        document.getElementById('stat-total').textContent = total;
        document.getElementById('stat-size').textContent = formatFileSize(totalSize);
        document.getElementById('stat-month').textContent = monthCount;
        document.getElementById('stat-tags').textContent = topTags.join(', ') || '-';
    } catch (e) {
        console.warn('fetchStats error', e);
    }
}

async function fetchImages() {
    showLoading();
    try {
        if (!window.Workspace || !Workspace.getHandle()) {
            state.images = [];
            state.total = 0;
            state.totalPages = 0;
            showEmpty();
            return;
        }

        const meta = await Workspace.readMetadata();
        let images = meta.images || [];

        // 本地筛选
        const { search, model, aspectRatio, sortBy, sortOrder, favorite } = state.filters;
        if (search) {
            const kw = search.toLowerCase();
            images = images.filter(img => (img.prompt || '').toLowerCase().includes(kw));
        }
        if (model) images = images.filter(img => img.model === model);
        if (aspectRatio) images = images.filter(img => img.aspect_ratio === aspectRatio);
        if (favorite !== null) images = images.filter(img => img.favorite === favorite);

        // 本地排序
        images.sort((a, b) => {
            const va = a[sortBy] || 0;
            const vb = b[sortBy] || 0;
            return sortOrder === 'desc' ? (vb > va ? 1 : -1) : (va > vb ? 1 : -1);
        });

        // 本地分页
        state.total = images.length;
        state.totalPages = Math.max(1, Math.ceil(images.length / state.pageSize));
        if (state.currentPage > state.totalPages) state.currentPage = state.totalPages;
        const start = (state.currentPage - 1) * state.pageSize;
        state.images = images.slice(start, start + state.pageSize);

        renderImages();
        updatePagination();
        await fetchStats();
    } catch (error) {
        console.error('获取图片列表失败:', error);
        state.images = [];
        state.total = 0;
        state.totalPages = 0;
        showEmpty();
    }
}

async function fetchImageDetail(imageId) {
    try {
        if (!window.Workspace || !Workspace.getHandle()) return null;
        const meta = await Workspace.readMetadata();
        return (meta.images || []).find(img => img.id === imageId) || null;
    } catch (error) {
        console.error('获取图片详情失败:', error);
        return null;
    }
}

async function deleteImages(imageIds) {
    try {
        if (!window.Workspace || !Workspace.getHandle()) return null;
        const meta = await Workspace.readMetadata();
        const toDelete = new Set(imageIds);

        // 找出要删除的图片记录，保留文件名以便后续删除文件
        const toDeleteImages = (meta.images || []).filter(img => toDelete.has(img.id));

        // 更新元数据，移除已删除的记录
        meta.images = (meta.images || []).filter(img => !toDelete.has(img.id));
        await Workspace.writeMetadata(meta);

        // 删除实际图片文件
        for (const img of toDeleteImages) {
            if (img.filename) {
                await Workspace.deleteImage(img.filename);
            }
        }

        return { success: true, message: `成功删除 ${toDeleteImages.length} 张图片` };
    } catch (error) {
        console.error('删除图片失败:', error);
        return null;
    }
}

async function updateTags(imageId, tags) {
    try {
        if (!window.Workspace) return null;
        await Workspace.updateImageMetadata(imageId, { tags });
        return { success: true };
    } catch (error) {
        console.error('更新标签失败:', error);
        return null;
    }
}

async function exportImages(imageIds) {
    if (!Workspace.getHandle()) {
        Toast.warning('请先设置工作目录');
        return;
    }
    try {
        showLoading();
        const data = await Workspace.readMetadata();
        const images = (data.images || []).filter(img => imageIds.includes(img.id));

        if (typeof JSZip === 'undefined') {
            // JSZip 未加载时，逐个下载
            for (const img of images) {
                const url = await Workspace.getImageURL(img.filename);
                if (!url) continue;
                const a = document.createElement('a');
                a.href = url;
                a.download = img.filename;
                a.click();
                await new Promise(resolve => setTimeout(resolve, 200));
                URL.revokeObjectURL(url);
            }
            Toast.success(`已下载 ${images.length} 张图片`);
            return;
        }

        const dirHandle = Workspace.getHandle();
        const zip = new JSZip();
        for (const img of images) {
            const fh = await dirHandle.getFileHandle(img.filename);
            const file = await fh.getFile();
            zip.file(img.filename, file);
        }

        const blob = await zip.generateAsync({ type: 'blob' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `images_export_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        Toast.success('图片导出成功');
    } catch (error) {
        console.error('导出图片失败:', error);
        Toast.error('导出失败，请重试');
    } finally {
        hideLoading();
    }
}

async function scanLocalImages() {
    const handle = Workspace.getHandle();
    if (!handle) {
        Toast.warning('请先设置工作目录');
        return;
    }
    try {
        showLoading();
        const data = await Workspace.readMetadata();
        const existingFilenames = new Set((data.images || []).map(img => img.filename));

        const newEntries = [];
        for await (const [name, fileHandle] of handle.entries()) {
            if (fileHandle.kind !== 'file') continue;
            if (!/\.(jpe?g|png|webp|gif)$/i.test(name)) continue;
            if (existingFilenames.has(name)) continue;

            const file = await fileHandle.getFile();
            newEntries.push({
                id: `import_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                filename: name,
                prompt: '',
                model: 'local-import',
                aspect_ratio: '',
                created_at: file.lastModified,
                file_size: file.size,
                tags: [],
                favorite: false,
            });
        }

        if (newEntries.length > 0) {
            data.images = [...newEntries, ...(data.images || [])];
            await Workspace.writeMetadata(data);
            Toast.success(`发现并导入 ${newEntries.length} 张新图片`);
        } else {
            Toast.info('没有发现新图片，元数据已是最新');
        }

        fetchImages();
        fetchStats();
    } catch (error) {
        console.error('扫描本地图片失败:', error);
        Toast.error('扫描失败，请重试');
    } finally {
        hideLoading();
    }
}

async function checkMissingFiles() {
    const handle = Workspace.getHandle();
    if (!handle) {
        Toast.warning('请先设置工作目录');
        return;
    }
    try {
        const modal = document.getElementById('missing-files-modal');
        modal.style.display = 'flex';
        document.getElementById('missing-summary').innerHTML = '<p>正在检查失效图片...</p>';
        document.getElementById('missing-list-container').style.display = 'none';

        const data = await Workspace.readMetadata();
        const images = data.images || [];
        const missingImages = [];

        for (const img of images) {
            const exists = await Workspace.fileExists(img.filename);
            if (!exists) missingImages.push(img);
        }

        const total = images.length;
        const missing = missingImages.length;
        const valid = total - missing;
        const summary = document.getElementById('missing-summary');

        if (missing === 0) {
            summary.innerHTML = `
                <p style="color: #4caf50; font-weight: bold;">✓ 所有图片文件都存在</p>
                <p>总计: ${total} 张，有效: ${valid} 张</p>
            `;
        } else {
            summary.innerHTML = `
                <p style="color: #ff9800; font-weight: bold;">⚠ 发现 ${missing} 张失效图片</p>
                <p>总计: ${total} 张，有效: ${valid} 张，失效: ${missing} 张</p>
                <p style="color: #666; font-size: 14px;">这些图片的文件已从工作目录删除，但元数据仍保留</p>
            `;

            const listContainer = document.getElementById('missing-list-container');
            const list = document.getElementById('missing-files-list');
            list.innerHTML = '';

            missingImages.forEach(img => {
                const row = document.createElement('tr');
                row.style.borderBottom = '1px solid #eee';
                row.innerHTML = `
                    <td style="padding: 8px; font-family: monospace; font-size: 12px;">${escapeHtml(img.filename)}</td>
                    <td style="padding: 8px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(img.prompt || '-')}</td>
                `;
                list.appendChild(row);
            });

            listContainer.style.display = 'block';
            window.missingImageIds = missingImages.map(img => img.id);
        }
    } catch (error) {
        console.error('检查失效图片失败:', error);
        Toast.error('检查失败，请重试');
    }
}

async function uploadImages(files) {
    const handle = Workspace.getHandle();
    if (!handle) {
        Toast.warning('请先设置工作目录，才能上传图片');
        return;
    }

    try {
        showLoading();
        let successCount = 0;
        let failCount = 0;

        for (const file of files) {
            try {
                const arrayBuffer = await file.arrayBuffer();
                const bytes = new Uint8Array(arrayBuffer);

                const fh = await handle.getFileHandle(file.name, { create: true });
                const writable = await fh.createWritable();
                await writable.write(bytes);
                await writable.close();

                const entry = {
                    id: `upload_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
                    filename: file.name,
                    prompt: '',
                    model: 'imported',
                    aspect_ratio: '',
                    created_at: Date.now(),
                    file_size: file.size,
                    tags: ['上传'],
                    favorite: false,
                };
                await Workspace.addImageMetadata(entry);
                successCount++;
            } catch (error) {
                console.error(`上传图片失败 ${file.name}:`, error);
                failCount++;
            }
        }

        if (failCount === 0) {
            Toast.success(`成功上传 ${successCount} 张图片`);
        } else {
            Toast.warning(`上传完成: 成功 ${successCount} 张，失败 ${failCount} 张`);
        }
        fetchImages();
        fetchStats();
        toggleUploadArea(false);
    } catch (error) {
        console.error('上传图片失败:', error);
        Toast.error('上传失败，请重试');
    } finally {
        hideLoading();
    }
}

function toggleUploadArea(show) {
    const uploadArea = document.getElementById('upload-area');
    if (show) {
        uploadArea.classList.add('active');
    } else {
        uploadArea.classList.remove('active');
    }
}

// UI 更新
function updateStats(stats) {
    document.getElementById('stat-total').textContent = stats.total_count || 0;
    document.getElementById('stat-size').textContent = formatFileSize(stats.total_size || 0);
    document.getElementById('stat-month').textContent = stats.month_count || 0;

    const topTags = stats.top_tags || [];
    const tagsText = topTags.slice(0, 3).map(t => t.name).join(', ') || '-';
    document.getElementById('stat-tags').textContent = tagsText;
}

function renderImages() {
    const container = document.getElementById('images-container');
    container.className = state.viewMode === 'grid' ? 'images-grid' : 'images-list';
    container.innerHTML = '';

    if (state.images.length === 0) {
        showEmpty();
        return;
    }

    hideLoading();
    hideEmpty();

    state.images.forEach(image => {
        const element = state.viewMode === 'grid'
            ? createImageCard(image)
            : createImageListItem(image);
        container.appendChild(element);
    });

    // 异步加载 ObjectURL（批量，非阻塞）
    if (window.Workspace && Workspace.getHandle()) {
        container.querySelectorAll('img[data-filename]').forEach(img => {
            const filename = img.dataset.filename;
            if (filename) {
                Workspace.getImageURL(filename).then(url => {
                    if (url) img.src = url;
                }).catch(() => {});
            }
        });
    }
}

function createImageCard(image) {
    const card = document.createElement('div');
    card.className = 'image-card';
    card.dataset.id = image.id;

    const isSelected = state.selectedIds.has(image.id);

    // 收藏按钮
    const favoriteClass = image.favorite ? 'favorited' : '';
    const favoriteIcon = image.favorite ? '❤️' : '🤍';

    card.innerHTML = `
        <input type="checkbox" class="image-card-checkbox" ${isSelected ? 'checked' : ''}>
        <button class="favorite-btn ${favoriteClass}" data-id="${image.id}" title="${image.favorite ? '取消收藏' : '收藏'}">${favoriteIcon}</button>
        <img src="" data-filename="${image.filename}" alt="${image.prompt}" class="image-card-img">
        <div class="image-card-info">
            <div class="image-card-prompt">${escapeHtml(image.prompt)}</div>
            <div class="image-card-meta">
                <span>${image.aspect_ratio}</span>
                <span>${formatFileSize(image.file_size)}</span>
            </div>
            ${image.tags && image.tags.length > 0 ? `
                <div class="image-card-tags">
                    ${image.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                </div>
            ` : ''}
        </div>
    `;

    // 复选框事件
    const checkbox = card.querySelector('.image-card-checkbox');
    checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSelection(image.id);
    });

    // 收藏按钮事件
    const favoriteBtn = card.querySelector('.favorite-btn');
    favoriteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await toggleFavorite(image.id, !image.favorite);
    });

    // 点击卡片显示详情
    card.addEventListener('click', (e) => {
        if (e.target !== checkbox && !e.target.classList.contains('favorite-btn')) {
            showImageDetail(image.id);
        }
    });

    return card;
}

function createImageListItem(image) {
    const item = document.createElement('div');
    item.className = 'image-list-item';
    item.dataset.id = image.id;

    const isSelected = state.selectedIds.has(image.id);

    item.innerHTML = `
        <input type="checkbox" class="image-list-checkbox" ${isSelected ? 'checked' : ''}>
        <img src="" data-filename="${image.filename}" alt="${image.prompt}" class="image-list-img">
        <div class="image-list-info">
            <div class="image-list-prompt">${escapeHtml(image.prompt)}</div>
            <div class="image-list-meta">
                <span>模型: ${image.model}</span>
                <span>比例: ${image.aspect_ratio}</span>
                <span>大小: ${formatFileSize(image.file_size)}</span>
                <span>时间: ${formatDate(image.created_at)}</span>
            </div>
        </div>
    `;

    // 复选框事件
    const checkbox = item.querySelector('.image-list-checkbox');
    checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSelection(image.id);
    });

    // 点击项显示详情
    item.addEventListener('click', (e) => {
        if (e.target !== checkbox) {
            showImageDetail(image.id);
        }
    });

    return item;
}

function toggleSelection(imageId) {
    if (state.selectedIds.has(imageId)) {
        state.selectedIds.delete(imageId);
    } else {
        state.selectedIds.add(imageId);
    }
    updateSelectionUI();
}

function updateSelectionUI() {
    // 更新复选框状态
    document.querySelectorAll('.image-card, .image-list-item').forEach(element => {
        const id = element.dataset.id;
        const checkbox = element.querySelector('input[type="checkbox"]');
        if (checkbox) {
            checkbox.checked = state.selectedIds.has(id);
        }
    });

    // 更新按钮状态
    const hasSelection = state.selectedIds.size > 0;
    document.getElementById('export-btn').disabled = !hasSelection;
    document.getElementById('delete-btn').disabled = !hasSelection;
}

function updatePagination() {
    const pagination = document.getElementById('pagination');
    const paginationTop = document.getElementById('pagination-top');
    const pageInfo = document.getElementById('page-info');
    const pageInfoTop = document.getElementById('page-info-top');
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const prevBtnTop = document.getElementById('prev-page-top');
    const nextBtnTop = document.getElementById('next-page-top');

    if (state.totalPages > 0) {
        pagination.style.display = 'flex';
        paginationTop.style.display = 'flex';

        pageInfo.textContent = `第 ${state.currentPage} 页 / 共 ${state.totalPages} 页`;
        pageInfoTop.textContent = `第 ${state.currentPage} 页 / 共 ${state.totalPages} 页`;

        prevBtn.disabled = state.currentPage === 1;
        nextBtn.disabled = state.currentPage === state.totalPages;
        prevBtnTop.disabled = state.currentPage === 1;
        nextBtnTop.disabled = state.currentPage === state.totalPages;
    } else {
        pagination.style.display = 'none';
        paginationTop.style.display = 'none';
    }
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('images-container').style.display = 'none';
    document.getElementById('empty-state').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
    const container = document.getElementById('images-container');
    container.style.display = 'block';
}

function showEmpty() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('images-container').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
}

function hideEmpty() {
    document.getElementById('empty-state').style.display = 'none';
}

async function showImageDetail(imageId) {
    const image = await fetchImageDetail(imageId);
    if (!image) return;

    state.currentImageId = imageId;
    // 找到当前图片在列表中的索引
    state.currentImageIndex = state.images.findIndex(img => img.id === imageId);

    const modal = document.getElementById('detail-modal');
    const detailImg = document.getElementById('detail-image');
    detailImg.src = '';
    if (window.Workspace && Workspace.getHandle()) {
        Workspace.getImageURL(image.filename).then(url => { if (url) detailImg.src = url; }).catch(() => {});
    }
    document.getElementById('detail-prompt').textContent = image.prompt;
    document.getElementById('detail-model').textContent = image.model;
    document.getElementById('detail-ratio').textContent = image.aspect_ratio;
    document.getElementById('detail-size').textContent = `${image.width || '-'} × ${image.height || '-'}`;
    document.getElementById('detail-filesize').textContent = formatFileSize(image.file_size);
    document.getElementById('detail-time').textContent = formatDate(image.created_at);

    // 显示文件名
    const filePathInput = document.getElementById('detail-file-path');
    filePathInput.value = image.filename || '未知';

    // 更新收藏按钮状态
    const favoriteBtn = document.getElementById('favorite-detail-btn');
    if (image.favorite) {
        favoriteBtn.textContent = '💔 取消收藏';
        favoriteBtn.classList.add('btn-danger');
        favoriteBtn.classList.remove('btn-secondary');
    } else {
        favoriteBtn.textContent = '❤️ 收藏';
        favoriteBtn.classList.add('btn-secondary');
        favoriteBtn.classList.remove('btn-danger');
    }

    // 渲染标签
    const tagsContainer = document.getElementById('detail-tags');
    tagsContainer.innerHTML = '';
    if (image.tags && image.tags.length > 0) {
        image.tags.forEach(tag => {
            const tagElement = document.createElement('span');
            tagElement.className = 'tag-removable';
            tagElement.innerHTML = `
                ${escapeHtml(tag)}
                <span class="tag-remove" data-tag="${escapeHtml(tag)}">×</span>
            `;
            tagsContainer.appendChild(tagElement);
        });
    }

    // 更新导航按钮状态
    updateNavigationButtons();

    modal.style.display = 'flex';
}

function closeImageDetail() {
    document.getElementById('detail-modal').style.display = 'none';
    state.currentImageId = null;
    state.currentImageIndex = -1;
}

// 显示上一张图片
function showPreviousImage() {
    if (state.currentImageIndex > 0) {
        const prevImage = state.images[state.currentImageIndex - 1];
        showImageDetail(prevImage.id);
    }
}

// 显示下一张图片
function showNextImage() {
    if (state.currentImageIndex < state.images.length - 1) {
        const nextImage = state.images[state.currentImageIndex + 1];
        showImageDetail(nextImage.id);
    }
}

// 更新导航按钮状态
function updateNavigationButtons() {
    const prevBtn = document.getElementById('prev-image-btn');
    const nextBtn = document.getElementById('next-image-btn');

    // 禁用/启用上一张按钮
    if (state.currentImageIndex <= 0) {
        prevBtn.disabled = true;
    } else {
        prevBtn.disabled = false;
    }

    // 禁用/启用下一张按钮
    if (state.currentImageIndex >= state.images.length - 1) {
        nextBtn.disabled = true;
    } else {
        nextBtn.disabled = false;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 事件处理
function initEventListeners() {
    // 筛选按钮
    document.getElementById('filter-btn').addEventListener('click', () => {
        state.filters.search = document.getElementById('search-input').value;
        state.filters.model = document.getElementById('model-filter').value;
        state.filters.aspectRatio = document.getElementById('ratio-filter').value;

        const sortValue = document.getElementById('sort-filter').value;
        const [sortBy, sortOrder] = sortValue.split(':');
        state.filters.sortBy = sortBy;
        state.filters.sortOrder = sortOrder;

        // 收藏筛选
        const favoriteValue = document.getElementById('favorite-filter').value;
        if (favoriteValue === 'true') {
            state.filters.favorite = true;
        } else if (favoriteValue === 'false') {
            state.filters.favorite = false;
        } else {
            state.filters.favorite = null;
        }

        state.currentPage = 1;
        fetchImages();
    });

    // 分页大小变化
    document.getElementById('page-size-filter').addEventListener('change', (e) => {
        state.pageSize = parseInt(e.target.value);
        state.currentPage = 1; // 重置到第一页

        // 保存用户偏好
        localStorage.setItem('gallery_page_size', state.pageSize);

        fetchImages();
    });

    // 分页大小变化
    document.getElementById('page-size-filter').addEventListener('change', (e) => {
        state.pageSize = parseInt(e.target.value);
        state.currentPage = 1;

        // 保存用户偏好
        localStorage.setItem('gallery_page_size', state.pageSize);

        fetchImages();
    });

    // 重置按钮
    document.getElementById('reset-btn').addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        document.getElementById('model-filter').value = '';
        document.getElementById('ratio-filter').value = '';
        document.getElementById('sort-filter').value = 'created_at:desc';
        document.getElementById('favorite-filter').value = '';
        document.getElementById('page-size-filter').value = '100';

        state.filters = {
            search: '',
            model: '',
            aspectRatio: '',
            sortBy: 'created_at',
            sortOrder: 'desc',
            favorite: null,
        };

        state.pageSize = 100;
        state.currentPage = 1;
        fetchImages();
    });

    // 搜索框回车
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('filter-btn').click();
        }
    });

    // 视图切换
    document.getElementById('view-grid').addEventListener('click', () => {
        state.viewMode = 'grid';
        document.getElementById('view-grid').classList.add('active');
        document.getElementById('view-list').classList.remove('active');

        // 保存用户偏好
        localStorage.setItem('gallery_view_mode', 'grid');

        renderImages();
    });

    document.getElementById('view-list').addEventListener('click', () => {
        state.viewMode = 'list';
        document.getElementById('view-list').classList.add('active');
        document.getElementById('view-grid').classList.remove('active');

        // 保存用户偏好
        localStorage.setItem('gallery_view_mode', 'list');

        renderImages();
    });

    // 全选
    document.getElementById('select-all').addEventListener('click', () => {
        if (state.selectedIds.size === state.images.length) {
            // 取消全选
            state.selectedIds.clear();
        } else {
            // 全选
            state.images.forEach(img => state.selectedIds.add(img.id));
        }
        updateSelectionUI();
    });

    // 导出
    document.getElementById('export-btn').addEventListener('click', async () => {
        if (state.selectedIds.size === 0) return;
        await exportImages(Array.from(state.selectedIds));
    });

    // 批量删除
    document.getElementById('delete-btn').addEventListener('click', async () => {
        if (state.selectedIds.size === 0) return;

        const confirmed = await ConfirmDialog.show({
            title: '确认删除',
            message: `确定要删除选中的 ${state.selectedIds.size} 张图片吗？此操作不可恢复。`,
            icon: '🗑️',
            confirmText: '删除',
            cancelText: '取消',
            confirmClass: 'btn-danger'
        });

        if (!confirmed) return;

        const result = await deleteImages(Array.from(state.selectedIds));
        if (result && result.success) {
            Toast.success(result.message);
            state.selectedIds.clear();
            fetchImages();
            fetchStats();
        } else {
            Toast.error('删除失败，请重试');
        }
    });

    // 分页（底部）
    document.getElementById('prev-page').addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchImages();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    document.getElementById('next-page').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchImages();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    // 分页（顶部）
    document.getElementById('prev-page-top').addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            fetchImages();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    document.getElementById('next-page-top').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            fetchImages();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    // 滑动翻页功能
    initSwipeNavigation();

    // 弹窗关闭
    document.getElementById('close-detail-modal').addEventListener('click', closeImageDetail);
    document.getElementById('detail-modal').addEventListener('click', (e) => {
        if (e.target.id === 'detail-modal') {
            closeImageDetail();
        }
    });

    // 导航按钮
    document.getElementById('prev-image-btn').addEventListener('click', showPreviousImage);
    document.getElementById('next-image-btn').addEventListener('click', showNextImage);

    // 键盘导航
    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('detail-modal');
        if (modal.style.display === 'flex') {
            if (e.key === 'ArrowLeft') {
                showPreviousImage();
            } else if (e.key === 'ArrowRight') {
                showNextImage();
            } else if (e.key === 'Escape') {
                closeImageDetail();
            }
        }
    });

    // 下载按钮
    document.getElementById('download-btn').addEventListener('click', async () => {
        if (!state.currentImageId) return;
        const image = await fetchImageDetail(state.currentImageId);
        if (!image) return;

        if (window.Workspace && Workspace.getHandle()) {
            const url = await Workspace.getImageURL(image.filename);
            if (url) {
                const a = document.createElement('a');
                a.href = url;
                a.download = image.filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                return;
            }
        }
        Toast.show('无法下载：请先设置工作目录', 'error');
    });

    // 删除单张图片
    document.getElementById('delete-single-btn').addEventListener('click', async () => {
        if (!state.currentImageId) return;

        const confirmed = await ConfirmDialog.show({
            title: '确认删除',
            message: '确定要删除这张图片吗？此操作不可恢复。',
            icon: '🗑️',
            confirmText: '删除',
            cancelText: '取消',
            confirmClass: 'btn-danger'
        });

        if (!confirmed) return;

        const result = await deleteImages([state.currentImageId]);
        if (result && result.success) {
            Toast.success(result.message);

            // 删除后自动切换到下一张图片
            const deletedIndex = state.currentImageIndex;
            const deletedId = state.currentImageId;

            // 从列表中移除已删除的图片
            state.images = state.images.filter(img => img.id !== deletedId);
            state.total--;

            // 重新渲染列表（更新页面显示）
            renderImages();
            updatePagination();

            // 如果还有图片，显示下一张或上一张
            if (state.images.length > 0) {
                // 如果删除的是最后一张，显示前一张
                if (deletedIndex >= state.images.length) {
                    showImageDetail(state.images[state.images.length - 1].id);
                } else {
                    // 否则显示当前位置的图片（原来的下一张）
                    showImageDetail(state.images[deletedIndex].id);
                }
            } else {
                // 如果当前页没有图片了，关闭详情弹窗并重新加载
                closeImageDetail();
                fetchImages();
            }

            // 更新统计信息
            fetchStats();
        } else {
            Toast.error('删除失败，请重试');
        }
    });

    // 添加标签
    document.getElementById('add-tag-btn').addEventListener('click', async () => {
        await addTag();
    });

    document.getElementById('tag-input').addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            await addTag();
        }
    });

    // 删除标签（事件委托）
    document.getElementById('detail-tags').addEventListener('click', async (e) => {
        if (e.target.classList.contains('tag-remove')) {
            const tag = e.target.dataset.tag;
            await removeTag(tag);
        }
    });

    // 复制路径按钮
    document.getElementById('copy-path-btn').addEventListener('click', () => {
        const filePathInput = document.getElementById('detail-file-path');
        filePathInput.select();
        document.execCommand('copy');
        Toast.success('路径已复制到剪贴板');
    });

    // 收藏按钮（详情页）
    document.getElementById('favorite-detail-btn').addEventListener('click', async () => {
        if (!state.currentImageId) return;
        const image = await fetchImageDetail(state.currentImageId);
        if (!image) return;
        await toggleFavorite(state.currentImageId, !image.favorite);
        // 重新加载详情以更新按钮状态
        await showImageDetail(state.currentImageId);
    });

    // 同步本地按钮
    document.getElementById('scan-btn').addEventListener('click', async () => {
        await scanLocalImages();
    });

    // 检查失效图片按钮
    document.getElementById('check-missing-btn').addEventListener('click', async () => {
        await checkMissingFiles();
    });

    // 上传按钮
    document.getElementById('upload-btn').addEventListener('click', () => {
        const uploadArea = document.getElementById('upload-area');
        const isActive = uploadArea.classList.contains('active');
        toggleUploadArea(!isActive);
    });

    // 上传区域点击
    document.getElementById('upload-dropzone').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    // 文件选择
    document.getElementById('file-input').addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            uploadImages(files);
        }
    });

    // 关闭失效图片弹窗
    document.getElementById('close-missing-modal').addEventListener('click', () => {
        document.getElementById('missing-files-modal').style.display = 'none';
    });

    document.getElementById('close-missing-btn').addEventListener('click', () => {
        document.getElementById('missing-files-modal').style.display = 'none';
    });

    // 删除所有失效数据
    document.getElementById('delete-missing-btn').addEventListener('click', async () => {
        if (!window.missingImageIds || window.missingImageIds.length === 0) {
            Toast.warning('没有失效图片需要删除');
            return;
        }

        const confirmed = await ConfirmDialog.show({
            title: '确认删除失效数据',
            message: `确定要删除 ${window.missingImageIds.length} 条失效图片的元数据吗？\n\n注意：这只会删除元数据（提示词、评分等），不会删除任何实际文件。`,
            icon: '🗑️',
            confirmText: '删除元数据',
            cancelText: '取消',
            confirmClass: 'btn-danger'
        });

        if (!confirmed) return;

        try {
            const result = await deleteImages(window.missingImageIds);
            if (result && result.success) {
                Toast.success(`已删除 ${window.missingImageIds.length} 条失效数据`);
                document.getElementById('missing-files-modal').style.display = 'none';
                fetchImages();
                fetchStats();
                window.missingImageIds = [];
            } else {
                Toast.error('删除失败，请重试');
            }
        } catch (error) {
            console.error('删除失效数据失败:', error);
            Toast.error('删除失败，请重试');
        }
    });

    // 拖拽上传
    const dropzone = document.getElementById('upload-dropzone');

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');

        const files = Array.from(e.dataTransfer.files).filter(file =>
            file.type.startsWith('image/')
        );

        if (files.length > 0) {
            uploadImages(files);
        }
    });
}

// 收藏功能
async function toggleFavorite(imageId, favorite) {
    try {
        if (!window.Workspace || !Workspace.getHandle()) return;
        await Workspace.updateImageMetadata(imageId, { favorite });
        Toast.show(favorite ? '已添加到收藏' : '已取消收藏', 'success');
        const image = state.images.find(img => img.id === imageId);
        if (image) image.favorite = favorite;
        const card = document.querySelector(`.image-card[data-id="${imageId}"]`);
        if (card) {
            const favoriteBtn = card.querySelector('.favorite-btn');
            if (favoriteBtn) {
                favoriteBtn.classList.toggle('favorited', favorite);
                favoriteBtn.textContent = favorite ? '❤️' : '🤍';
                favoriteBtn.title = favorite ? '取消收藏' : '收藏';
            }
        }
    } catch (error) {
        console.error('收藏操作失败:', error);
        Toast.show('操作失败，请重试', 'error');
    }
}

// 滑动翻页功能
function initSwipeNavigation() {
    const wrapper = document.getElementById('images-container-wrapper');
    let startX = 0;
    let startY = 0;
    let isDragging = false;

    wrapper.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isDragging = true;
    }, { passive: true });

    wrapper.addEventListener('touchmove', (e) => {
        if (!isDragging) return;

        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const diffX = startX - currentX;
        const diffY = startY - currentY;

        // 只有水平滑动距离大于垂直滑动距离时才触发翻页
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
            e.preventDefault();
        }
    }, { passive: false });

    wrapper.addEventListener('touchend', (e) => {
        if (!isDragging) return;

        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        const diffX = startX - endX;
        const diffY = startY - endY;

        // 只有水平滑动距离大于垂直滑动距离且超过阈值时才翻页
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 100) {
            if (diffX > 0 && state.currentPage < state.totalPages) {
                // 向左滑动，下一页
                state.currentPage++;
                fetchImages();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else if (diffX < 0 && state.currentPage > 1) {
                // 向右滑动，上一页
                state.currentPage--;
                fetchImages();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }

        isDragging = false;
    }, { passive: true });

    // 鼠标拖拽支持（桌面端）
    let mouseStartX = 0;
    let mouseStartY = 0;
    let isMouseDragging = false;

    wrapper.addEventListener('mousedown', (e) => {
        mouseStartX = e.clientX;
        mouseStartY = e.clientY;
        isMouseDragging = true;
    });

    wrapper.addEventListener('mousemove', (e) => {
        if (!isMouseDragging) return;

        const currentX = e.clientX;
        const diffX = mouseStartX - currentX;

        if (Math.abs(diffX) > 10) {
            wrapper.style.cursor = 'grabbing';
        }
    });

    wrapper.addEventListener('mouseup', (e) => {
        if (!isMouseDragging) return;

        const endX = e.clientX;
        const diffX = mouseStartX - endX;

        if (Math.abs(diffX) > 150) {
            if (diffX > 0 && state.currentPage < state.totalPages) {
                // 向左拖动，下一页
                state.currentPage++;
                fetchImages();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else if (diffX < 0 && state.currentPage > 1) {
                // 向右拖动，上一页
                state.currentPage--;
                fetchImages();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }

        isMouseDragging = false;
        wrapper.style.cursor = 'default';
    });

    wrapper.addEventListener('mouseleave', () => {
        isMouseDragging = false;
        wrapper.style.cursor = 'default';
    });
}

async function addTag() {
    if (!state.currentImageId) return;

    const input = document.getElementById('tag-input');
    const tag = input.value.trim();

    if (!tag) return;

    const image = await fetchImageDetail(state.currentImageId);
    if (!image) return;

    const tags = image.tags || [];
    if (tags.includes(tag)) {
        Toast.warning('标签已存在');
        return;
    }

    tags.push(tag);
    const result = await updateTags(state.currentImageId, tags);

    if (result && result.success) {
        input.value = '';
        showImageDetail(state.currentImageId);
        fetchImages();
        Toast.success('标签添加成功');
    } else {
        Toast.error('标签添加失败');
    }
}

async function removeTag(tag) {
    if (!state.currentImageId) return;

    const image = await fetchImageDetail(state.currentImageId);
    if (!image) return;

    const tags = (image.tags || []).filter(t => t !== tag);
    const result = await updateTags(state.currentImageId, tags);

    if (result && result.success) {
        showImageDetail(state.currentImageId);
        fetchImages();
        Toast.success('标签删除成功');
    } else {
        Toast.error('标签删除失败');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 恢复用户偏好的 UI 状态
    document.getElementById('page-size-filter').value = state.pageSize.toString();

    if (state.viewMode === 'grid') {
        document.getElementById('view-grid').classList.add('active');
        document.getElementById('view-list').classList.remove('active');
    } else {
        document.getElementById('view-list').classList.add('active');
        document.getElementById('view-grid').classList.remove('active');
    }

    // 工作区检测与 banner
    const banner = document.getElementById('workspace-banner');
    const bannerMsg = document.getElementById('workspace-banner-msg');
    const bannerBtn = document.getElementById('workspace-banner-btn');

    async function setupWorkspace(skipPerm = false) {
        if (!window.Workspace) return false;
        if (!Workspace.isSupported()) {
            const reason = (Workspace.getUnsupportedReason && Workspace.getUnsupportedReason()) || '浏览器不支持 File System API，请使用 Chrome/Edge';
            if (banner) { banner.style.display = 'flex'; if (bannerMsg) bannerMsg.textContent = '⚠️ ' + reason; if (bannerBtn) bannerBtn.style.display = 'none'; }
            return false;
        }
        const handle = await Workspace.initWorkspace();
        if (!handle) { if (banner) banner.style.display = 'flex'; return false; }
        const perm = skipPerm ? 'prompt' : await handle.queryPermission({ mode: 'readwrite' });
        if (perm === 'granted') { if (banner) banner.style.display = 'none'; return true; }
        if (banner) { banner.style.display = 'flex'; if (bannerBtn) bannerBtn.textContent = '重新授权目录'; }
        return false;
    }

    const ready = await setupWorkspace();

    if (bannerBtn) {
        bannerBtn.addEventListener('click', async () => {
            try {
                await Workspace.requestWorkspace();
                banner.style.display = 'none';
                fetchStats();
                fetchImages();
            } catch (e) {
                if (e.name !== 'AbortError') Toast.show('设置工作目录失败', 'error');
            }
        });
    }

    initEventListeners();
    fetchStats();
    fetchImages();
});
