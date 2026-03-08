// 视频管理 JavaScript

const API_BASE = '/api/v1/admin/video-gallery';

// Toast
const Toast = {
    show(message, type = 'info', title = '', duration = 3000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
        const titles = { success: title || '成功', error: title || '错误', warning: title || '警告', info: title || '提示' };
        toast.innerHTML = `
            <div class="toast-icon">${icons[type]}</div>
            <div class="toast-content">
                <div class="toast-title">${titles[type]}</div>
                <div class="toast-message">${message}</div>
            </div>
            <div class="toast-close">×</div>`;
        container.appendChild(toast);
        toast.querySelector('.toast-close').addEventListener('click', () => this.remove(toast));
        if (duration > 0) setTimeout(() => this.remove(toast), duration);
        return toast;
    },
    remove(toast) {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    },
    success(msg) { return this.show(msg, 'success'); },
    error(msg) { return this.show(msg, 'error'); },
    warning(msg) { return this.show(msg, 'warning'); },
    info(msg) { return this.show(msg, 'info'); },
};

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(timestamp) {
    return new Date(timestamp).toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
}

function getAuthHeaders() {
    const token = localStorage.getItem('admin_token') || '';
    return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
}

// 全局状态
const state = {
    videos: [],
    selectedIds: new Set(),
    currentPage: 1,
    pageSize: 50,
    totalPages: 0,
    total: 0,
    currentVideoId: null,
    currentVideoData: null,
};

// ==================== API ====================

async function fetchStats() {
    try {
        const res = await fetch(`${API_BASE}/stats`, { headers: getAuthHeaders() });
        if (!res.ok) return;
        const stats = await res.json();
        document.getElementById('stat-total').textContent = stats.total_count || 0;
        document.getElementById('stat-size').textContent = formatFileSize(stats.total_size || 0);
        document.getElementById('stat-month').textContent = stats.month_count || 0;
        const topTags = (stats.top_tags || []).slice(0, 5).map(t => t.name).join(', ');
        document.getElementById('stat-tags').textContent = topTags || '-';
    } catch (e) {
        console.warn('fetchStats error', e);
    }
}

async function fetchVideos() {
    showLoading();
    try {
        const params = new URLSearchParams();
        params.set('page', state.currentPage);
        params.set('page_size', state.pageSize);

        const search = document.getElementById('search-input').value.trim();
        const resolution = document.getElementById('resolution-filter').value;
        const ratio = document.getElementById('ratio-filter').value;
        const length = document.getElementById('length-filter').value;
        const favorite = document.getElementById('favorite-filter').value;
        const sortVal = document.getElementById('sort-filter').value;
        const [sortBy, sortOrder] = sortVal.split(':');

        if (search) params.set('search', search);
        if (resolution) params.set('resolution', resolution);
        if (ratio) params.set('aspect_ratio', ratio);
        if (length) params.set('video_length', length);
        if (favorite) params.set('favorite', favorite);
        params.set('sort_by', sortBy);
        params.set('sort_order', sortOrder);

        const res = await fetch(`${API_BASE}/videos?${params}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        state.videos = data.videos || [];
        state.total = data.total || 0;
        state.totalPages = data.total_pages || 0;

        renderVideos();
        updatePagination();
        fetchStats();
    } catch (e) {
        console.error('fetchVideos error:', e);
        state.videos = [];
        state.total = 0;
        showEmpty();
    }
}

async function scanLocalVideos() {
    try {
        document.getElementById('scan-btn').disabled = true;
        const res = await fetch(`${API_BASE}/scan`, { method: 'POST', headers: getAuthHeaders() });
        const data = await res.json();
        if (data.success) {
            Toast.success(data.message);
            fetchVideos();
        } else {
            Toast.error(data.message || '扫描失败');
        }
    } catch (e) {
        Toast.error('扫描请求失败');
    } finally {
        document.getElementById('scan-btn').disabled = false;
    }
}

async function deleteVideos(videoIds) {
    try {
        const res = await fetch(`${API_BASE}/videos/delete`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ video_ids: videoIds }),
        });
        const data = await res.json();
        if (data.success) {
            Toast.success(data.message);
            state.selectedIds.clear();
            updateDeleteButton();
            fetchVideos();
        } else {
            Toast.error('删除失败');
        }
    } catch (e) {
        Toast.error('删除请求失败');
    }
}

async function checkMissingFiles() {
    const modal = document.getElementById('missing-files-modal');
    const summary = document.getElementById('missing-summary');
    const listContainer = document.getElementById('missing-list-container');
    modal.style.display = 'flex';
    summary.innerHTML = '<p>正在检查...</p>';
    listContainer.style.display = 'none';

    try {
        const res = await fetch(`${API_BASE}/check-missing`, { headers: getAuthHeaders() });
        const data = await res.json();
        const result = data.data || {};
        summary.innerHTML = `<p>总计 ${result.total} 个视频，有效 ${result.valid} 个，失效 ${result.missing} 个</p>`;

        if (result.missing > 0) {
            const list = document.getElementById('missing-files-list');
            list.innerHTML = (result.missing_videos || []).map(v =>
                `<tr><td style="padding:6px 8px">${v.filename}</td><td style="padding:6px 8px">${(v.prompt || '').substring(0, 60)}</td></tr>`
            ).join('');
            listContainer.style.display = 'block';
        }
    } catch (e) {
        summary.innerHTML = '<p>检查失败</p>';
    }
}

async function cleanupMissing() {
    try {
        const res = await fetch(`${API_BASE}/cleanup`, { method: 'POST', headers: getAuthHeaders() });
        const data = await res.json();
        if (data.success) {
            Toast.success(data.message);
            document.getElementById('missing-files-modal').style.display = 'none';
            fetchVideos();
        }
    } catch (e) {
        Toast.error('清理失败');
    }
}

async function toggleFavorite(videoId, favorite) {
    try {
        const res = await fetch(`${API_BASE}/videos/${videoId}/favorite`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ favorite }),
        });
        const data = await res.json();
        if (data.success) {
            Toast.success(favorite ? '已收藏' : '已取消收藏');
            fetchVideos();
        }
    } catch (e) {
        Toast.error('操作失败');
    }
}

async function updateTags(videoId, tags) {
    try {
        await fetch(`${API_BASE}/videos/${videoId}/tags`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ tags }),
        });
    } catch (e) {
        Toast.error('更新标签失败');
    }
}

// ==================== 渲染 ====================

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('videos-container').innerHTML = '';
    document.getElementById('empty-state').style.display = 'none';
}

function showEmpty() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
    document.getElementById('pagination').style.display = 'none';
    document.getElementById('pagination-top').style.display = 'none';
}

function renderVideos() {
    document.getElementById('loading').style.display = 'none';
    const container = document.getElementById('videos-container');

    if (state.videos.length === 0) {
        showEmpty();
        return;
    }

    document.getElementById('empty-state').style.display = 'none';

    container.innerHTML = state.videos.map(v => {
        const isSelected = state.selectedIds.has(v.id);
        const isFav = v.favorite;
        const videoUrl = `/v1/files/video/${v.filename}`;

        return `
        <div class="video-card ${isSelected ? 'selected' : ''}" data-id="${v.id}">
            <input type="checkbox" class="video-card-checkbox" ${isSelected ? 'checked' : ''}
                onclick="event.stopPropagation(); toggleSelect('${v.id}')">
            <button class="video-card-favorite ${isFav ? 'active' : ''}"
                onclick="event.stopPropagation(); toggleFavorite('${v.id}', ${!isFav})">
                ${isFav ? '❤️' : '🤍'}
            </button>
            <div class="video-thumbnail" onclick="showDetail('${v.id}')">
                <video src="${videoUrl}" preload="metadata" muted></video>
                <span class="video-badge">${v.video_length || 6}s · ${v.resolution || '480p'}</span>
            </div>
            <div class="video-card-info" onclick="showDetail('${v.id}')">
                <div class="video-card-prompt">${v.prompt || '(无提示词)'}</div>
                <div class="video-card-meta">
                    <span>${v.aspect_ratio || '3:2'}</span>
                    <span>${formatFileSize(v.file_size)}</span>
                    <span>${formatDate(v.created_at)}</span>
                </div>
            </div>
        </div>`;
    }).join('');
}

function updatePagination() {
    const show = state.totalPages > 1;
    document.getElementById('pagination').style.display = show ? 'flex' : 'none';
    document.getElementById('pagination-top').style.display = show ? 'flex' : 'none';
    if (!show) return;

    document.getElementById('page-total-label').textContent = `/ ${state.totalPages} 页`;

    [['pagination', 'prev-page', 'next-page', 'page-numbers'],
     ['pagination-top', 'prev-page-top', 'next-page-top', 'page-numbers-top']].forEach(([, prevId, nextId, numbersId]) => {
        const prevBtn = document.getElementById(prevId);
        const nextBtn = document.getElementById(nextId);
        if (prevBtn) prevBtn.disabled = state.currentPage <= 1;
        if (nextBtn) nextBtn.disabled = state.currentPage >= state.totalPages;

        const numbersEl = document.getElementById(numbersId);
        if (!numbersEl) return;
        numbersEl.innerHTML = '';

        let start = Math.max(1, state.currentPage - 2);
        let end = Math.min(state.totalPages, start + 4);
        if (end - start < 4) start = Math.max(1, end - 4);

        for (let i = start; i <= end; i++) {
            const btn = document.createElement('button');
            btn.textContent = i;
            btn.className = i === state.currentPage ? 'active' : '';
            btn.onclick = () => goToPage(i);
            numbersEl.appendChild(btn);
        }
    });
}

function goToPage(page) {
    if (page < 1 || page > state.totalPages) return;
    state.currentPage = page;
    fetchVideos();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function toggleSelect(id) {
    if (state.selectedIds.has(id)) {
        state.selectedIds.delete(id);
    } else {
        state.selectedIds.add(id);
    }
    const card = document.querySelector(`.video-card[data-id="${id}"]`);
    if (card) {
        card.classList.toggle('selected', state.selectedIds.has(id));
        card.querySelector('.video-card-checkbox').checked = state.selectedIds.has(id);
    }
    updateDeleteButton();
}

function updateDeleteButton() {
    const btn = document.getElementById('delete-btn');
    btn.disabled = state.selectedIds.size === 0;
    btn.textContent = state.selectedIds.size > 0 ? `删除 (${state.selectedIds.size})` : '删除';
}

// ==================== 详情弹窗 ====================

function showDetail(videoId) {
    const video = state.videos.find(v => v.id === videoId);
    if (!video) return;

    state.currentVideoId = videoId;
    state.currentVideoData = video;

    const videoUrl = `/v1/files/video/${video.filename}`;
    document.getElementById('detail-video').src = videoUrl;
    document.getElementById('detail-prompt').textContent = video.prompt || '(无提示词)';
    document.getElementById('detail-model').textContent = video.model || '-';
    document.getElementById('detail-ratio').textContent = video.aspect_ratio || '-';
    document.getElementById('detail-length').textContent = `${video.video_length || 6} 秒`;
    document.getElementById('detail-resolution').textContent = video.resolution || '-';
    document.getElementById('detail-filesize').textContent = formatFileSize(video.file_size);
    document.getElementById('detail-time').textContent = formatDate(video.created_at);

    renderDetailTags(video.tags || []);

    const favBtn = document.getElementById('favorite-detail-btn');
    favBtn.textContent = video.favorite ? '💔 取消收藏' : '❤️ 收藏';
    favBtn.onclick = () => {
        toggleFavorite(videoId, !video.favorite);
        document.getElementById('detail-modal').style.display = 'none';
    };

    document.getElementById('detail-modal').style.display = 'flex';
}

function renderDetailTags(tags) {
    const container = document.getElementById('detail-tags');
    container.innerHTML = tags.map(tag =>
        `<span class="tag">${tag}<span class="tag-remove" onclick="removeTag('${tag}')">×</span></span>`
    ).join('') || '<span style="color:var(--text-muted);font-size:0.85rem">无标签</span>';
}

async function addTag() {
    const input = document.getElementById('tag-input');
    const tag = input.value.trim();
    if (!tag || !state.currentVideoData) return;

    const tags = [...(state.currentVideoData.tags || [])];
    if (tags.includes(tag)) { Toast.warning('标签已存在'); return; }
    tags.push(tag);

    await updateTags(state.currentVideoId, tags);
    state.currentVideoData.tags = tags;
    renderDetailTags(tags);
    input.value = '';
    Toast.success('标签已添加');
}

async function removeTag(tag) {
    if (!state.currentVideoData) return;
    const tags = (state.currentVideoData.tags || []).filter(t => t !== tag);
    await updateTags(state.currentVideoId, tags);
    state.currentVideoData.tags = tags;
    renderDetailTags(tags);
    Toast.success('标签已移除');
}

// ==================== 事件绑定 ====================

document.addEventListener('DOMContentLoaded', () => {
    fetchVideos();

    document.getElementById('filter-btn').addEventListener('click', () => { state.currentPage = 1; fetchVideos(); });
    document.getElementById('reset-btn').addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        document.getElementById('resolution-filter').value = '';
        document.getElementById('ratio-filter').value = '';
        document.getElementById('length-filter').value = '';
        document.getElementById('sort-filter').value = 'created_at:desc';
        document.getElementById('favorite-filter').value = '';
        state.currentPage = 1;
        fetchVideos();
    });

    document.getElementById('scan-btn').addEventListener('click', scanLocalVideos);
    document.getElementById('check-missing-btn').addEventListener('click', checkMissingFiles);

    document.getElementById('select-all').addEventListener('click', () => {
        const allSelected = state.videos.every(v => state.selectedIds.has(v.id));
        if (allSelected) {
            state.videos.forEach(v => state.selectedIds.delete(v.id));
        } else {
            state.videos.forEach(v => state.selectedIds.add(v.id));
        }
        renderVideos();
        updateDeleteButton();
    });

    document.getElementById('delete-btn').addEventListener('click', () => {
        if (state.selectedIds.size === 0) return;
        if (typeof AppDialog !== 'undefined') {
            AppDialog.confirm(
                `确定删除 ${state.selectedIds.size} 个视频？此操作不可撤销。`,
                () => deleteVideos([...state.selectedIds]),
                '确认删除'
            );
        } else if (confirm(`确定删除 ${state.selectedIds.size} 个视频？`)) {
            deleteVideos([...state.selectedIds]);
        }
    });

    // 详情弹窗关闭
    document.getElementById('close-detail-modal').addEventListener('click', () => {
        document.getElementById('detail-modal').style.display = 'none';
        document.getElementById('detail-video').pause();
        document.getElementById('detail-video').src = '';
    });
    document.getElementById('detail-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            document.getElementById('detail-modal').style.display = 'none';
            document.getElementById('detail-video').pause();
            document.getElementById('detail-video').src = '';
        }
    });

    document.getElementById('delete-single-btn').addEventListener('click', () => {
        if (!state.currentVideoId) return;
        const id = state.currentVideoId;
        if (typeof AppDialog !== 'undefined') {
            AppDialog.confirm('确定删除这个视频？', () => {
                document.getElementById('detail-modal').style.display = 'none';
                deleteVideos([id]);
            }, '确认删除');
        } else if (confirm('确定删除这个视频？')) {
            document.getElementById('detail-modal').style.display = 'none';
            deleteVideos([id]);
        }
    });

    document.getElementById('add-tag-btn').addEventListener('click', addTag);
    document.getElementById('tag-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') addTag();
    });

    // 失效弹窗
    document.getElementById('close-missing-modal').addEventListener('click', () => {
        document.getElementById('missing-files-modal').style.display = 'none';
    });
    const closeMissingBtn = document.getElementById('close-missing-btn');
    if (closeMissingBtn) closeMissingBtn.addEventListener('click', () => {
        document.getElementById('missing-files-modal').style.display = 'none';
    });
    const cleanupBtn = document.getElementById('cleanup-missing-btn');
    if (cleanupBtn) cleanupBtn.addEventListener('click', cleanupMissing);

    // 分页
    document.getElementById('prev-page').addEventListener('click', () => goToPage(state.currentPage - 1));
    document.getElementById('next-page').addEventListener('click', () => goToPage(state.currentPage + 1));
    document.getElementById('prev-page-top').addEventListener('click', () => goToPage(state.currentPage - 1));
    document.getElementById('next-page-top').addEventListener('click', () => goToPage(state.currentPage + 1));
    document.getElementById('page-jump-btn').addEventListener('click', () => {
        const page = parseInt(document.getElementById('page-jump-input').value);
        if (page >= 1 && page <= state.totalPages) goToPage(page);
    });

    // 搜索回车
    document.getElementById('search-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { state.currentPage = 1; fetchVideos(); }
    });
});
