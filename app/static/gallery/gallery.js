// 图片管理 JavaScript

// 全局状态
const state = {
    images: [],
    selectedIds: new Set(),
    currentPage: 1,
    pageSize: 50,
    totalPages: 0,
    total: 0,
    viewMode: 'grid', // 'grid' or 'list'
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
};

// API 基础路径
const API_BASE = '/api/v1/admin/gallery';

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
    } catch (error) {
        console.error('导出图片失败:', error);
        alert('导出失败，请重试');
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
            alert(data.message);
            fetchImages();
            fetchStats();
        } else {
            alert('扫描失败，请重试');
        }
    } catch (error) {
        console.error('扫描本地图片失败:', error);
        alert('扫描失败，请重试');
    } finally {
        hideLoading();
    }
}

async function analyzeQuality(imageIds = null) {
    try {
        showLoading();
        const response = await fetch(`${API_BASE}/analyze-quality`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_ids: imageIds,
                update_metadata: true,
                batch_size: 50,
            }),
        });
        const data = await response.json();

        if (data.success) {
            alert(data.message);
            fetchImages();
            fetchStats();
        } else {
            alert('分析失败，请重试');
        }
    } catch (error) {
        console.error('分析图片质量失败:', error);
        alert('分析失败，请重试');
    } finally {
        hideLoading();
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

        alert(`上传完成: 成功 ${successCount}, 失败 ${failCount}`);
        fetchImages();
        fetchStats();
        toggleUploadArea(false);
    } catch (error) {
        console.error('上传图片失败:', error);
        alert('上传失败，请重试');
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

    const pageText = `第 ${state.currentPage} 页 / 共 ${state.totalPages} 页`;
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

    // 重置按钮
    document.getElementById('reset-btn').addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        document.getElementById('model-filter').value = '';
        document.getElementById('ratio-filter').value = '';
        document.getElementById('sort-filter').value = 'created_at:desc';
        document.getElementById('quality-filter').value = '';

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
        renderImages();
    });

    document.getElementById('view-list').addEventListener('click', () => {
        state.viewMode = 'list';
        document.getElementById('view-list').classList.add('active');
        document.getElementById('view-grid').classList.remove('active');
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

        if (!confirm(`确定要删除选中的 ${state.selectedIds.size} 张图片吗？`)) {
            return;
        }

        const result = await deleteImages(Array.from(state.selectedIds));
        if (result && result.success) {
            alert(result.message);
            state.selectedIds.clear();
            fetchImages();
            fetchStats();
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
    document.querySelector('.modal-close').addEventListener('click', closeImageDetail);
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

        if (!confirm('确定要删除这张图片吗？')) {
            return;
        }

        const result = await deleteImages([state.currentImageId]);
        if (result && result.success) {
            alert(result.message);
            closeImageDetail();
            fetchImages();
            fetchStats();
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

    // 同步本地按钮
    document.getElementById('scan-btn').addEventListener('click', async () => {
        if (confirm('确定要扫描本地图片文件夹吗？这将为所有没有元数据的图片创建记录。')) {
            await scanLocalImages();
        }
    });

    // 质量分析按钮
    document.getElementById('analyze-btn').addEventListener('click', async () => {
        const selectedCount = state.selectedIds.size;
        let message = '';

        if (selectedCount > 0) {
            message = `确定要分析选中的 ${selectedCount} 张图片吗？`;
        } else {
            message = `确定要分析所有图片吗？这可能需要一些时间。`;
        }

        if (confirm(message)) {
            const imageIds = selectedCount > 0 ? Array.from(state.selectedIds) : null;
            await analyzeQuality(imageIds);
        }
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
        alert('标签已存在');
        return;
    }

    tags.push(tag);
    const result = await updateTags(state.currentImageId, tags);

    if (result && result.success) {
        input.value = '';
        showImageDetail(state.currentImageId);
        fetchImages();
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
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    fetchStats();
    fetchImages();
});
