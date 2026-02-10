// 图片管理 JavaScript

// 从 localStorage 读取用户偏好
function loadUserPreferences() {
    const savedPageSize = localStorage.getItem('gallery_page_size');
    const savedViewMode = localStorage.getItem('gallery_view_mode');

    return {
        pageSize: savedPageSize ? parseInt(savedPageSize) : 50,
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
        minQualityScore: null,
        maxQualityScore: null,
        hasQualityIssues: null,
    },
    currentImageId: null,
    currentImageIndex: -1, // 当前图片在列表中的索引
    analysisState: {
        mode: 'all',        // 'all' 或 'skip'
        maxWorkers: 8       // 4-16
    },
};

// API 基础路径
const API_BASE = '/api/v1/admin/gallery';

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
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        updateStats(data);
    } catch (error) {
        console.error('获取统计信息失败:', error);
    }
}

async function fetchImages() {
    showLoading();
    try {
        const params = new URLSearchParams({
            page: state.currentPage,
            page_size: state.pageSize,
            sort_by: state.filters.sortBy,
            sort_order: state.filters.sortOrder,
        });

        if (state.filters.search) params.append('search', state.filters.search);
        if (state.filters.model) params.append('model', state.filters.model);
        if (state.filters.aspectRatio) params.append('aspect_ratio', state.filters.aspectRatio);
        if (state.filters.minQualityScore !== null) params.append('min_quality_score', state.filters.minQualityScore);
        if (state.filters.maxQualityScore !== null) params.append('max_quality_score', state.filters.maxQualityScore);
        if (state.filters.hasQualityIssues !== null) params.append('has_quality_issues', state.filters.hasQualityIssues);

        const response = await fetch(`${API_BASE}/images?${params}`);
        const data = await response.json();

        state.images = data.images;
        state.total = data.total;
        state.totalPages = data.total_pages;

        renderImages();
        updatePagination();
    } catch (error) {
        console.error('获取图片列表失败:', error);
        showEmpty();
    }
}

async function fetchImageDetail(imageId) {
    try {
        const response = await fetch(`${API_BASE}/images/${imageId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('获取图片详情失败:', error);
        return null;
    }
}

async function deleteImages(imageIds) {
    try {
        const response = await fetch(`${API_BASE}/images/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_ids: imageIds }),
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('删除图片失败:', error);
        return null;
    }
}

async function updateTags(imageId, tags) {
    try {
        const response = await fetch(`${API_BASE}/images/${imageId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags }),
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('更新标签失败:', error);
        return null;
    }
}

async function exportImages(imageIds) {
    try {
        const response = await fetch(`${API_BASE}/images/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_ids: imageIds }),
        });

        if (!response.ok) throw new Error('导出失败');

        const blob = await response.blob();
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
    }
}

async function scanLocalImages() {
    try {
        showLoading();
        const response = await fetch(`${API_BASE}/scan`, {
            method: 'POST',
        });
        const data = await response.json();

        if (data.success) {
            Toast.success(data.message);
            fetchImages();
            fetchStats();
        } else {
            Toast.error('扫描失败，请重试');
        }
    } catch (error) {
        console.error('扫描本地图片失败:', error);
        Toast.error('扫描失败，请重试');
    } finally {
        hideLoading();
    }
}

async function checkMissingFiles() {
    try {
        // 显示弹窗
        const modal = document.getElementById('missing-files-modal');
        modal.style.display = 'flex';

        // 显示加载状态
        document.getElementById('missing-summary').innerHTML = '<p>正在检查失效图片...</p>';
        document.getElementById('missing-list-container').style.display = 'none';

        const response = await fetch(`${API_BASE}/check-missing`);
        const data = await response.json();

        if (data.success) {
            const result = data.data;
            const summary = document.getElementById('missing-summary');

            if (result.missing === 0) {
                summary.innerHTML = `
                    <p style="color: #4caf50; font-weight: bold;">✓ 所有图片文件都存在</p>
                    <p>总计: ${result.total} 张，有效: ${result.valid} 张</p>
                `;
            } else {
                summary.innerHTML = `
                    <p style="color: #ff9800; font-weight: bold;">⚠ 发现 ${result.missing} 张失效图片</p>
                    <p>总计: ${result.total} 张，有效: ${result.valid} 张，失效: ${result.missing} 张</p>
                    <p style="color: #666; font-size: 14px;">这些图片的文件已被删除，但元数据还保留着（包括提示词、评分等）</p>
                `;

                // 显示失效图片列表
                const listContainer = document.getElementById('missing-list-container');
                const list = document.getElementById('missing-files-list');
                list.innerHTML = '';

                result.missing_images.forEach(img => {
                    const row = document.createElement('tr');
                    row.style.borderBottom = '1px solid #eee';
                    row.innerHTML = `
                        <td style="padding: 8px; font-family: monospace; font-size: 12px;">${escapeHtml(img.filename)}</td>
                        <td style="padding: 8px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(img.prompt || '-')}</td>
                        <td style="padding: 8px; text-align: center;">${img.quality_score !== null ? img.quality_score.toFixed(0) : '-'}</td>
                    `;
                    list.appendChild(row);
                });

                listContainer.style.display = 'block';

                // 保存失效图片ID列表，供删除使用
                window.missingImageIds = result.missing_images.map(img => img.id);
            }

            Toast.success(data.message);
        } else {
            Toast.error('检查失败，请重试');
        }
    } catch (error) {
        console.error('检查失效图片失败:', error);
        Toast.error('检查失败，请重试');
    }
}

async function scanLocalImages() {
    try {
        showLoading();
        const response = await fetch(`${API_BASE}/scan`, {
            method: 'POST',
        });
        const data = await response.json();

        if (data.success) {
            Toast.success(data.message);
            fetchImages();
            fetchStats();
        } else {
            Toast.error('扫描失败，请重试');
        }
    } catch (error) {
        console.error('扫描本地图片失败:', error);
        Toast.error('扫描失败，请重试');
    } finally {
        hideLoading();
    }
}

async function analyzeQuality(imageIds = null) {
    try {
        // 显示停止按钮，隐藏分析按钮
        document.getElementById('analyze-btn').style.display = 'none';
        document.getElementById('stop-analysis-btn').style.display = 'inline-block';

        showLoading();
        const response = await fetch(`${API_BASE}/analyze-quality`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_ids: imageIds,
                update_metadata: true,
                batch_size: 50,
                skip_analyzed: state.analysisState.mode === 'skip',
                max_workers: state.analysisState.maxWorkers
            }),
        });
        const data = await response.json();

        if (data.success) {
            const mode = state.analysisState.mode === 'skip' ? '增量' : '全量';
            const result = data.data;

            if (result.stopped) {
                Toast.warning(`${mode}分析已停止：已完成 ${result.analyzed}/${result.total} 张`);
            } else {
                let message = `${mode}分析完成：成功 ${result.analyzed}, 失败 ${result.failed}, 低质量 ${result.low_quality_count}`;
                if (result.skipped > 0) {
                    message += `, 跳过 ${result.skipped}`;
                }
                Toast.success(message);
            }

            fetchImages();
            fetchStats();
        } else {
            Toast.error('分析失败，请重试');
        }
    } catch (error) {
        console.error('分析图片质量失败:', error);
        Toast.error('分析失败，请重试');
    } finally {
        hideLoading();
        // 恢复按钮状态
        document.getElementById('analyze-btn').style.display = 'inline-block';
        document.getElementById('stop-analysis-btn').style.display = 'none';
    }
}

async function stopAnalysis() {
    try {
        const response = await fetch(`${API_BASE}/stop-analysis`, {
            method: 'POST',
        });
        const data = await response.json();

        if (data.success) {
            Toast.info('正在停止分析...');
        } else {
            Toast.error('停止失败，请重试');
        }
    } catch (error) {
        console.error('停止分析失败:', error);
        Toast.error('停止失败，请重试');
    }
}

async function uploadImages(files) {
    try {
        showLoading();
        let successCount = 0;
        let failCount = 0;

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('filename', file.name);
            formData.append('tags', '上传');

            try {
                const response = await fetch(`${API_BASE}/upload`, {
                    method: 'POST',
                    body: formData,
                });
                const data = await response.json();

                if (data.success) {
                    successCount++;
                } else {
                    failCount++;
                }
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
}

function createImageCard(image) {
    const card = document.createElement('div');
    card.className = 'image-card';
    card.dataset.id = image.id;

    const isSelected = state.selectedIds.has(image.id);

    // 质量评分显示
    let qualityBadge = '';
    if (image.quality_score !== null && image.quality_score !== undefined) {
        const score = image.quality_score;
        let qualityClass = 'quality-low';
        if (score >= 80) qualityClass = 'quality-high';
        else if (score >= 60) qualityClass = 'quality-medium';

        qualityBadge = `<div class="quality-badge ${qualityClass}">${score.toFixed(0)}</div>`;
    }

    card.innerHTML = `
        <input type="checkbox" class="image-card-checkbox" ${isSelected ? 'checked' : ''}>
        ${qualityBadge}
        <img src="/v1/files/image/${image.filename}" alt="${image.prompt}" class="image-card-img">
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

    // 点击卡片显示详情
    card.addEventListener('click', (e) => {
        if (e.target !== checkbox) {
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
        <img src="/v1/files/image/${image.filename}" alt="${image.prompt}" class="image-list-img">
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
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const prevBtnTop = document.getElementById('prev-page-top');
    const nextBtnTop = document.getElementById('next-page-top');
    const pageInfo = document.getElementById('page-info');
    const pageInfoTop = document.getElementById('page-info-top');

    if (state.totalPages <= 1) {
        pagination.style.display = 'none';
        paginationTop.style.display = 'none';
        return;
    }

    pagination.style.display = 'flex';
    paginationTop.style.display = 'flex';

    // 计算当前显示的图片范围
    const startIndex = (state.currentPage - 1) * state.pageSize + 1;
    const endIndex = Math.min(state.currentPage * state.pageSize, state.total);

    const pageText = `显示 ${startIndex}-${endIndex} / 共 ${state.total} 张 (第 ${state.currentPage}/${state.totalPages} 页)`;
    pageInfo.textContent = pageText;
    pageInfoTop.textContent = pageText;

    const prevDisabled = state.currentPage <= 1;
    const nextDisabled = state.currentPage >= state.totalPages;

    prevBtn.disabled = prevDisabled;
    nextBtn.disabled = nextDisabled;
    prevBtnTop.disabled = prevDisabled;
    nextBtnTop.disabled = nextDisabled;
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('images-container').style.display = 'none';
    document.getElementById('empty-state').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('images-container').style.display = state.viewMode === 'grid' ? 'grid' : 'flex';
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
    document.getElementById('detail-image').src = `/v1/files/image/${image.filename}`;
    document.getElementById('detail-prompt').textContent = image.prompt;
    document.getElementById('detail-model').textContent = image.model;
    document.getElementById('detail-ratio').textContent = image.aspect_ratio;
    document.getElementById('detail-size').textContent = `${image.width} × ${image.height}`;
    document.getElementById('detail-filesize').textContent = formatFileSize(image.file_size);
    document.getElementById('detail-time').textContent = formatDate(image.created_at);

    // 显示文件路径
    const filePathInput = document.getElementById('detail-file-path');
    filePathInput.value = image.file_path || image.relative_path || '未知';

    // 显示质量信息
    const qualityInfo = document.getElementById('quality-info');
    if (image.quality_score !== null && image.quality_score !== undefined) {
        qualityInfo.style.display = 'block';

        const score = image.quality_score;
        const fill = document.getElementById('detail-quality-fill');
        const scoreText = document.getElementById('detail-quality-score');

        // 设置进度条
        fill.style.width = `${score}%`;
        if (score >= 80) fill.style.backgroundColor = '#4caf50';
        else if (score >= 60) fill.style.backgroundColor = '#ff9800';
        else fill.style.backgroundColor = '#f44336';

        scoreText.textContent = `${score.toFixed(0)}分`;

        // 显示详细分数
        document.getElementById('detail-blur').textContent = `模糊度: ${(image.blur_score || 0).toFixed(1)}`;
        document.getElementById('detail-brightness').textContent = `亮度: ${(image.brightness_score || 0).toFixed(1)}`;

        // 显示质量问题
        const issuesContainer = document.getElementById('detail-quality-issues');
        if (image.quality_issues && image.quality_issues.length > 0) {
            issuesContainer.innerHTML = image.quality_issues.map(issue =>
                `<span class="quality-issue-tag">${escapeHtml(issue)}</span>`
            ).join('');
        } else {
            issuesContainer.innerHTML = '<span class="quality-ok">✓ 无质量问题</span>';
        }
    } else {
        qualityInfo.style.display = 'none';
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

        // 质量筛选
        const qualityValue = document.getElementById('quality-filter').value;
        if (qualityValue === 'low40') {
            // 低于40分
            state.filters.minQualityScore = null;
            state.filters.maxQualityScore = 40;
            state.filters.hasQualityIssues = null;
        } else if (qualityValue === 'low') {
            // 低于60分
            state.filters.minQualityScore = null;
            state.filters.maxQualityScore = 60;
            state.filters.hasQualityIssues = null;
        } else if (qualityValue === 'issues') {
            state.filters.minQualityScore = null;
            state.filters.maxQualityScore = null;
            state.filters.hasQualityIssues = true;
        } else if (qualityValue) {
            // 大于等于指定分数
            state.filters.minQualityScore = parseFloat(qualityValue);
            state.filters.maxQualityScore = null;
            state.filters.hasQualityIssues = null;
        } else {
            state.filters.minQualityScore = null;
            state.filters.maxQualityScore = null;
            state.filters.hasQualityIssues = null;
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

    // 重置按钮
    document.getElementById('reset-btn').addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        document.getElementById('model-filter').value = '';
        document.getElementById('ratio-filter').value = '';
        document.getElementById('sort-filter').value = 'created_at:desc';
        document.getElementById('quality-filter').value = '';
        document.getElementById('page-size-filter').value = '50';

        state.filters = {
            search: '',
            model: '',
            aspectRatio: '',
            sortBy: 'created_at',
            sortOrder: 'desc',
            minQualityScore: null,
            maxQualityScore: null,
            hasQualityIssues: null,
        };

        state.pageSize = 50;
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

        const a = document.createElement('a');
        a.href = `/v1/files/image/${image.filename}`;
        a.download = image.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
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

    // 重新分析单张图片
    document.getElementById('reanalyze-btn').addEventListener('click', async () => {
        if (!state.currentImageId) return;

        const btn = document.getElementById('reanalyze-btn');
        const originalText = btn.innerHTML;

        try {
            // 禁用按钮并显示加载状态
            btn.disabled = true;
            btn.innerHTML = '⏳ 分析中...';
            btn.style.opacity = '0.6';

            // 显示加载提示
            Toast.info('开始分析图片质量...', '', 2000);

            const response = await fetch(`${API_BASE}/analyze-quality`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_ids: [state.currentImageId],
                    update_metadata: true,
                    batch_size: 1,
                    skip_analyzed: false,
                    max_workers: 1,
                    fast_mode: true
                }),
            });
            const data = await response.json();

            if (data.success) {
                const result = data.data;
                if (result.analyzed > 0) {
                    Toast.success(`分析完成！质量分数已更新`, '', 3000);
                    // 重新加载图片详情
                    await showImageDetail(state.currentImageId);
                    // 刷新列表
                    fetchImages();
                } else if (result.failed > 0) {
                    Toast.error('分析失败，请重试');
                } else {
                    Toast.warning('未能分析图片');
                }
            } else {
                Toast.error('分析失败，请重试');
            }
        } catch (error) {
            console.error('重新分析图片失败:', error);
            Toast.error(`分析失败: ${error.message}`);
        } finally {
            // 恢复按钮状态
            btn.disabled = false;
            btn.innerHTML = originalText;
            btn.style.opacity = '1';
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

    // 同步本地按钮
    document.getElementById('scan-btn').addEventListener('click', async () => {
        await scanLocalImages();
    });

    // 检查失效图片按钮
    document.getElementById('check-missing-btn').addEventListener('click', async () => {
        await checkMissingFiles();
    });

    // 质量分析按钮
    document.getElementById('analyze-btn').addEventListener('click', async () => {
        const selectedCount = state.selectedIds.size;
        const imageIds = selectedCount > 0 ? Array.from(state.selectedIds) : null;
        await analyzeQuality(imageIds);
    });

    // 停止分析按钮
    document.getElementById('stop-analysis-btn').addEventListener('click', async () => {
        await stopAnalysis();
    });

    // 分析选项按钮
    document.getElementById('analyze-options-btn').addEventListener('click', () => {
        document.getElementById('analysis-options-modal').style.display = 'flex';
        updateEstimatedTime();
    });

    // 关闭选项弹窗
    document.getElementById('close-analysis-options').addEventListener('click', () => {
        document.getElementById('analysis-options-modal').style.display = 'none';
    });

    document.getElementById('cancel-analysis-options-btn').addEventListener('click', () => {
        document.getElementById('analysis-options-modal').style.display = 'none';
    });

    // 并发数滑块
    document.getElementById('worker-count-slider').addEventListener('input', (e) => {
        const value = e.target.value;
        document.getElementById('worker-count-display').textContent = value;
        updateEstimatedTime();
    });

    // 分析模式切换
    document.querySelectorAll('input[name="analysis-mode"]').forEach(radio => {
        radio.addEventListener('change', updateEstimatedTime);
    });

    // 开始分析
    document.getElementById('start-analysis-btn').addEventListener('click', async () => {
        // 保存选项
        state.analysisState.mode = document.querySelector('input[name="analysis-mode"]:checked').value;
        state.analysisState.maxWorkers = parseInt(document.getElementById('worker-count-slider').value);

        // 关闭弹窗
        document.getElementById('analysis-options-modal').style.display = 'none';

        // 执行分析
        const selectedCount = state.selectedIds.size;
        const imageIds = selectedCount > 0 ? Array.from(state.selectedIds) : null;
        await analyzeQuality(imageIds);
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

// 预估时间计算
function updateEstimatedTime() {
    const mode = document.querySelector('input[name="analysis-mode"]:checked').value;
    const workers = parseInt(document.getElementById('worker-count-slider').value);

    // 基准速度：0.24 秒/张
    const baseTime = 0.24;

    // 加速比（基于实测数据）
    const speedupFactors = {
        4: 1.17,
        8: 1.62,
        12: 1.68,
        16: 1.70
    };
    const speedup = speedupFactors[workers] || 1.62;
    const timePerImage = baseTime / speedup;

    // 计算图片数量
    let imageCount;
    if (mode === 'skip') {
        // 假设 10% 的图片未分析（可以从 API 获取精确值）
        imageCount = Math.ceil(state.total * 0.1);
    } else {
        imageCount = state.total;
    }

    // 计算总时间
    const totalSeconds = imageCount * timePerImage;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);

    // 显示结果
    const display = document.getElementById('estimated-time');
    display.textContent = `约 ${minutes} 分 ${seconds} 秒（${imageCount} 张图片）`;
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 恢复用户偏好的 UI 状态
    document.getElementById('page-size-filter').value = state.pageSize.toString();

    if (state.viewMode === 'grid') {
        document.getElementById('view-grid').classList.add('active');
        document.getElementById('view-list').classList.remove('active');
    } else {
        document.getElementById('view-list').classList.add('active');
        document.getElementById('view-grid').classList.remove('active');
    }

    initEventListeners();
    fetchStats();
    fetchImages();
});
