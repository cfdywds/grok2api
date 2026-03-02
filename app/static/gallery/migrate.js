// 历史数据迁移脚本

const API_BASE = '/api/v1/admin/gallery';
const PAGE_SIZE = 100;

const state = {
    total: 0,
    migrated: 0,
    failed: 0,
    stopped: false,
    running: false,
    workspaceHandle: null,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const els = {
    statTotal: document.getElementById('stat-total'),
    statMigrated: document.getElementById('stat-migrated'),
    statFailed: document.getElementById('stat-failed'),
    serverStatus: document.getElementById('server-status'),
    selectWorkspaceBtn: document.getElementById('select-workspace-btn'),
    workspaceStatus: document.getElementById('workspace-status'),
    progressBar: document.getElementById('progress-bar'),
    progressText: document.getElementById('progress-text'),
    progressPct: document.getElementById('progress-pct'),
    log: document.getElementById('log'),
    startBtn: document.getElementById('start-btn'),
    stopBtn: document.getElementById('stop-btn'),
    refreshBtn: document.getElementById('refresh-btn'),
};

// ── Logging ───────────────────────────────────────────────────────────────────

function log(msg, type = '') {
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = `[${new Date().toLocaleTimeString('zh-CN')}] ${msg}`;
    els.log.appendChild(line);
    els.log.scrollTop = els.log.scrollHeight;
}

// ── Server info ───────────────────────────────────────────────────────────────

async function loadServerInfo() {
    els.serverStatus.textContent = '正在连接服务端...';
    try {
        const res = await fetch(`${API_BASE}/migrate`);
        const data = await res.json();
        if (!data.success) throw new Error(data.detail || '请求失败');

        const { total, has_image_dir } = data.data;
        state.total = total;
        els.statTotal.textContent = total;
        els.progressText.textContent = `0 / ${total}`;

        if (!has_image_dir) {
            els.serverStatus.textContent = '⚠️ 服务端图片目录不存在，可能已清空';
        } else if (total === 0) {
            els.serverStatus.textContent = '服务端暂无图片数据';
        } else {
            els.serverStatus.textContent = `✅ 服务端共有 ${total} 张图片，图片目录存在`;
        }

        updateStartBtn();
    } catch (e) {
        els.serverStatus.textContent = `❌ 无法获取服务端信息：${e.message}`;
        log(`获取服务端信息失败: ${e.message}`, 'err');
    }
}

// ── Workspace ─────────────────────────────────────────────────────────────────

async function initWorkspace() {
    if (!Workspace.isSupported()) {
        const reason = Workspace.getUnsupportedReason ? Workspace.getUnsupportedReason() : '当前浏览器不支持 File System Access API，请使用 Chrome 或 Edge';
        els.workspaceStatus.textContent = '❌ ' + reason;
        return;
    }

    // 尝试恢复已存储的 handle
    const handle = await Workspace.initWorkspace();
    if (handle) {
        const perm = await handle.queryPermission({ mode: 'readwrite' });
        if (perm === 'granted') {
            state.workspaceHandle = handle;
            els.workspaceStatus.textContent = `✅ ${handle.name}`;
            els.workspaceStatus.className = 'ok';
            updateStartBtn();
            return;
        }
    }
    els.workspaceStatus.textContent = '未设置';
}

els.selectWorkspaceBtn.addEventListener('click', async () => {
    try {
        const handle = await Workspace.requestWorkspace();
        state.workspaceHandle = handle;
        els.workspaceStatus.textContent = `✅ ${handle.name}`;
        els.workspaceStatus.className = 'ok';
        updateStartBtn();
        log(`工作目录已设置: ${handle.name}`, 'ok');
    } catch (e) {
        if (e.name !== 'AbortError') {
            log(`设置工作目录失败: ${e.message}`, 'err');
        }
    }
});

function updateStartBtn() {
    els.startBtn.disabled = !(state.workspaceHandle && state.total > 0 && !state.running);
}

els.refreshBtn.addEventListener('click', loadServerInfo);

// ── Migration ─────────────────────────────────────────────────────────────────

els.startBtn.addEventListener('click', startMigration);
els.stopBtn.addEventListener('click', () => {
    state.stopped = true;
    log('正在停止迁移...', 'warn');
    els.stopBtn.disabled = true;
});

async function startMigration() {
    if (!state.workspaceHandle || state.running) return;

    state.stopped = false;
    state.running = true;
    state.migrated = 0;
    state.failed = 0;

    els.startBtn.style.display = 'none';
    els.stopBtn.style.display = 'inline-flex';
    els.stopBtn.disabled = false;
    els.refreshBtn.disabled = true;
    els.selectWorkspaceBtn.disabled = true;

    log(`开始迁移，共 ${state.total} 张图片...`);

    // 读取现有 metadata（追加模式）
    const existingData = await Workspace.readMetadata();
    const existingIds = new Set((existingData.images || []).map(img => img.id));
    const newImages = existingData.images || [];

    let page = 1;
    let totalFetched = 0;

    try {
        while (!state.stopped) {
            // 拉取一页元数据
            const listRes = await fetch(
                `${API_BASE}/images?page=${page}&page_size=${PAGE_SIZE}`
            );
            const listData = await listRes.json();

            if (!listData.images || listData.images.length === 0) break;

            for (const img of listData.images) {
                if (state.stopped) break;

                // 已存在则跳过
                if (existingIds.has(img.id)) {
                    log(`跳过（已存在）: ${img.filename}`, 'warn');
                    totalFetched++;
                    updateProgress(totalFetched);
                    continue;
                }

                try {
                    // 下载图片文件
                    const fileRes = await fetch(`${API_BASE}/images/${img.id}/file`);
                    if (!fileRes.ok) throw new Error(`HTTP ${fileRes.status}`);

                    const buffer = await fileRes.arrayBuffer();
                    const bytes = new Uint8Array(buffer);

                    // 保存到工作目录
                    const fh = await state.workspaceHandle.getFileHandle(img.filename, { create: true });
                    const writable = await fh.createWritable();
                    await writable.write(bytes);
                    await writable.close();

                    // 构建新格式的元数据条目
                    newImages.push({
                        id: img.id,
                        filename: img.filename,
                        prompt: img.prompt || '',
                        model: img.model || 'grok-imagine-1.0',
                        aspect_ratio: img.aspect_ratio || '',
                        created_at: img.created_at,
                        file_size: img.file_size || bytes.length,
                        width: img.width,
                        height: img.height,
                        tags: img.tags || [],
                        favorite: img.favorite || false,
                    });
                    existingIds.add(img.id);

                    state.migrated++;
                    els.statMigrated.textContent = state.migrated;
                    log(`✓ ${img.filename} (${formatBytes(bytes.length)})`, 'ok');
                } catch (e) {
                    state.failed++;
                    els.statFailed.textContent = state.failed;
                    log(`✗ ${img.filename}: ${e.message}`, 'err');
                }

                totalFetched++;
                updateProgress(totalFetched);

                // 每迁移 20 张保存一次 metadata（防止意外中断丢失）
                if (state.migrated % 20 === 0 && state.migrated > 0) {
                    await saveMetadata(newImages);
                }
            }

            if (listData.page >= listData.total_pages) break;
            page++;
        }

        // 最终写入 metadata
        await saveMetadata(newImages);

        if (state.stopped) {
            log(`迁移已停止。已迁移 ${state.migrated} 张，失败 ${state.failed} 张`, 'warn');
        } else {
            log(`🎉 迁移完成！成功 ${state.migrated} 张，失败 ${state.failed} 张`, 'ok');
        }

    } catch (e) {
        log(`迁移过程出错: ${e.message}`, 'err');
        // 保存已迁移的部分
        if (state.migrated > 0) {
            await saveMetadata(newImages);
            log(`已保存 ${state.migrated} 张图片的元数据`, 'warn');
        }
    } finally {
        state.running = false;
        els.startBtn.style.display = 'inline-flex';
        els.stopBtn.style.display = 'none';
        els.refreshBtn.disabled = false;
        els.selectWorkspaceBtn.disabled = false;
        updateStartBtn();
    }
}

async function saveMetadata(images) {
    await Workspace.writeMetadata({ version: '1.0', images });
}

function updateProgress(done) {
    const total = state.total || 1;
    const pct = Math.min(100, Math.round((done / total) * 100));
    els.progressBar.style.width = `${pct}%`;
    els.progressText.textContent = `${done} / ${state.total}`;
    els.progressPct.textContent = `${pct}%`;
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([initWorkspace(), loadServerInfo()]);
});
