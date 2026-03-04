/**
 * Video 视频工作台 JS
 */
(function () {
  'use strict';

  // ==================== 状态 ====================
  let currentTaskIds = [];
  let isGenerating = false;
  let currentVideoUrl = '';
  let currentPostId = '';
  let referenceImageData = null;
  let videoHistory = [];

  // ==================== DOM ====================
  const $ = (sel) => document.querySelector(sel);
  const promptInput = () => $('#promptInput');
  const aspectSelect = () => $('#aspectRatio');
  const lengthSelect = () => $('#videoLength');
  const resolutionSelect = () => $('#resolution');
  const presetSelect = () => $('#preset');
  const generateBtn = () => $('#generateBtn');
  const stopBtn = () => $('#stopBtn');
  const extendBtn = () => $('#extendBtn');
  const progressBar = () => $('#progressFill');
  const statusText = () => $('#statusText');
  const videoPlayer = () => $('#videoPlayer');
  const placeholderEl = () => $('#videoPlaceholder');
  const playerWrapper = () => $('#playerWrapper');
  const refImageArea = () => $('#refImageArea');
  const refPreview = () => $('#refPreview');
  const autoSaveToggle = () => $('#autoSaveToggle');
  const selectFolderBtn = () => $('#selectFolderBtn');
  const folderPathEl = () => $('#folderPath');

  // ==================== API ====================
  function getAuthHeaders() {
    const token = localStorage.getItem('admin_token') || '';
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  }

  async function apiPost(url, body) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || err.error || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  // ==================== 生成 ====================
  async function startGeneration() {
    if (isGenerating) return;

    const prompt = (promptInput()?.value || '').trim();
    const imageUrl = referenceImageData || '';
    const parentPostId = '';

    if (!prompt && !imageUrl) {
      showToast('请输入提示词或上传参考图', 'warning');
      return;
    }

    isGenerating = true;
    updateUI();
    setProgress(0, '准备生成...');
    showPlayer(false);

    try {
      const body = {
        prompt,
        aspect_ratio: aspectSelect()?.value || '3:2',
        video_length: parseInt(lengthSelect()?.value || '6'),
        resolution_name: resolutionSelect()?.value || '480p',
        preset: presetSelect()?.value || 'normal',
        concurrent: 1,
      };
      if (imageUrl) body.image_url = imageUrl;

      const result = await apiPost('/v1/video/start', body);
      currentTaskIds = result.task_ids || [result.task_id];

      // 启动 SSE 监听
      for (const taskId of currentTaskIds) {
        listenSSE(taskId);
      }
    } catch (e) {
      showToast(e.message || '启动失败', 'error');
      isGenerating = false;
      updateUI();
    }
  }

  function listenSSE(taskId) {
    const token = localStorage.getItem('admin_token') || '';
    let url = `/v1/video/sse?task_id=${taskId}`;
    const evtSource = new EventSource(url);

    evtSource.onmessage = function (event) {
      const raw = event.data;
      if (raw === '[DONE]') {
        evtSource.close();
        onGenerationDone();
        return;
      }
      try {
        const data = JSON.parse(raw);

        // 检查错误
        if (data.error) {
          evtSource.close();
          showToast(data.error, 'error');
          onGenerationDone();
          return;
        }

        // 解析 ChatCompletion chunk
        const choices = data.choices || [];
        const delta = choices[0]?.delta || {};
        const content = delta.content || '';
        const finishReason = choices[0]?.finish_reason;

        if (content) {
          // 检测进度
          const progressMatch = content.match(/进度(\d+)%/);
          if (progressMatch) {
            const pct = parseInt(progressMatch[1]);
            setProgress(pct, `正在生成视频 ${pct}%`);
          }

          // 检测超分辨率
          if (content.includes('超分辨率')) {
            setProgress(100, '正在超分辨率升级...');
          }

          // 检测视频 URL
          const videoMatch = content.match(/src="([^"]+\.mp4[^"]*)"/);
          if (videoMatch) {
            displayVideo(videoMatch[1]);
          } else if (content.startsWith('http') && content.includes('/video')) {
            displayVideo(content.trim());
          }

          // 检测 video HTML
          if (content.includes('<video')) {
            const srcMatch = content.match(/src="([^"]+)"/);
            if (srcMatch) {
              displayVideo(srcMatch[1]);
            }
          }
        }

        if (finishReason === 'stop') {
          evtSource.close();
          onGenerationDone();
        }
      } catch (e) {
        // 忽略解析错误
      }
    };

    evtSource.onerror = function () {
      evtSource.close();
      onGenerationDone();
    };
  }

  function onGenerationDone() {
    isGenerating = false;
    updateUI();
    if (!currentVideoUrl) {
      setProgress(0, '生成完成，但未获取到视频');
    } else {
      setProgress(100, '生成完成');
    }
  }

  async function stopGeneration() {
    if (!currentTaskIds.length) return;
    try {
      await apiPost('/v1/video/stop', { task_ids: currentTaskIds });
    } catch (e) {
      // 忽略
    }
    currentTaskIds = [];
    isGenerating = false;
    updateUI();
    setProgress(0, '已停止');
  }

  // ==================== 视频延长 ====================
  async function extendVideo() {
    if (!currentPostId || isGenerating) return;

    const player = videoPlayer();
    const startTime = player ? player.currentTime : 0;

    isGenerating = true;
    updateUI();
    setProgress(0, '准备延长视频...');

    try {
      const body = {
        prompt: (promptInput()?.value || '').trim(),
        aspect_ratio: aspectSelect()?.value || '16:9',
        video_length: parseInt(lengthSelect()?.value || '6'),
        resolution_name: resolutionSelect()?.value || '480p',
        preset: presetSelect()?.value || 'normal',
        concurrent: 1,
        is_video_extension: true,
        extend_post_id: currentPostId,
        video_extension_start_time: startTime,
        stitch_with_extend: true,
      };

      const result = await apiPost('/v1/video/start', body);
      currentTaskIds = result.task_ids || [result.task_id];

      for (const taskId of currentTaskIds) {
        listenSSE(taskId);
      }
    } catch (e) {
      showToast(e.message || '延长失败', 'error');
      isGenerating = false;
      updateUI();
    }
  }

  // ==================== 显示 ====================
  function displayVideo(url) {
    currentVideoUrl = url;
    // 尝试提取 post ID
    const match = url.match(/\/generated\/([0-9a-f-]{32,36})\//);
    if (match) currentPostId = match[1];

    showPlayer(true);
    const player = videoPlayer();
    if (player) {
      player.src = url;
      player.load();
      player.play().catch(() => {});
    }

    // 添加到历史
    addToHistory(url);

    // 自动保存到工作目录
    autoSaveVideo(url);
  }

  /**
   * 自动保存视频到工作目录或降级为浏览器下载
   */
  async function autoSaveVideo(url) {
    const toggle = autoSaveToggle();
    if (!toggle || !toggle.checked) return;

    const timestamp = Date.now();
    const filename = `video_${timestamp}.mp4`;

    // 优先使用 File System Access API
    if (typeof Workspace !== 'undefined' && Workspace.getHandle()) {
      try {
        await Workspace.saveVideoFromURL(url, filename);
        const entry = {
          id: `vid_${timestamp}_${Math.random().toString(36).substr(2, 6)}`,
          filename,
          prompt: (promptInput()?.value || '').trim(),
          aspect_ratio: aspectSelect()?.value || '3:2',
          resolution: resolutionSelect()?.value || '480p',
          video_length: parseInt(lengthSelect()?.value || '6'),
          preset: presetSelect()?.value || 'normal',
          source_url: url,
          created_at: timestamp,
          tags: [],
          favorite: false,
        };
        await Workspace.addVideoMetadata(entry);
        showToast('视频已保存到工作目录: ' + filename, 'success');
      } catch (e) {
        console.warn('[video] auto save failed:', e);
        showToast('自动保存失败: ' + e.message, 'error');
      }
    } else {
      // 降级为浏览器下载
      try {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('已触发浏览器下载: ' + filename, 'success');
      } catch (e) {
        console.warn('[video] browser download failed:', e);
      }
    }
  }

  function showPlayer(show) {
    const placeholder = placeholderEl();
    const wrapper = playerWrapper();
    if (placeholder) placeholder.style.display = show ? 'none' : 'flex';
    if (wrapper) wrapper.style.display = show ? 'block' : 'none';
  }

  function setProgress(pct, text) {
    const bar = progressBar();
    const txt = statusText();
    if (bar) bar.style.width = `${pct}%`;
    if (txt) txt.textContent = text || '';
  }

  function updateUI() {
    const gen = generateBtn();
    const stop = stopBtn();
    const ext = extendBtn();
    if (gen) gen.disabled = isGenerating;
    if (stop) stop.style.display = isGenerating ? 'inline-flex' : 'none';
    if (ext) ext.style.display = (!isGenerating && currentPostId) ? 'inline-flex' : 'none';
  }

  // ==================== 历史 ====================
  function addToHistory(url) {
    videoHistory.unshift({ url, time: Date.now() });
    if (videoHistory.length > 20) videoHistory.pop();
    renderHistory();
  }

  function renderHistory() {
    const container = $('#videoHistory');
    if (!container) return;
    container.innerHTML = '';
    for (const item of videoHistory) {
      const div = document.createElement('div');
      div.className = 'video-history-item';
      div.innerHTML = `<video src="${item.url}" muted preload="metadata"></video>`;
      div.addEventListener('click', () => displayVideo(item.url));
      container.appendChild(div);
    }
  }

  // ==================== 参考图 ====================
  function setupImageUpload() {
    const area = refImageArea();
    if (!area) return;

    area.addEventListener('click', () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
          referenceImageData = ev.target.result;
          area.classList.add('has-image');
          const preview = refPreview();
          if (preview) {
            preview.src = referenceImageData;
            preview.style.display = 'block';
          }
          area.querySelector('.upload-text')?.remove();
        };
        reader.readAsDataURL(file);
      };
      input.click();
    });

    // 拖拽
    area.addEventListener('dragover', (e) => { e.preventDefault(); area.style.borderColor = 'var(--foreground)'; });
    area.addEventListener('dragleave', () => { area.style.borderColor = ''; });
    area.addEventListener('drop', (e) => {
      e.preventDefault();
      area.style.borderColor = '';
      const file = e.dataTransfer.files[0];
      if (!file || !file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        referenceImageData = ev.target.result;
        area.classList.add('has-image');
        const preview = refPreview();
        if (preview) {
          preview.src = referenceImageData;
          preview.style.display = 'block';
        }
        area.querySelector('.upload-text')?.remove();
      };
      reader.readAsDataURL(file);
    });
  }

  function clearRefImage() {
    referenceImageData = null;
    const area = refImageArea();
    if (area) {
      area.classList.remove('has-image');
      const preview = refPreview();
      if (preview) {
        preview.src = '';
        preview.style.display = 'none';
      }
      if (!area.querySelector('.upload-text')) {
        const span = document.createElement('span');
        span.className = 'upload-text';
        span.textContent = '点击或拖拽上传参考图';
        area.appendChild(span);
      }
    }
  }

  // ==================== Toast ====================
  function showToast(msg, type) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type || 'info'}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // ==================== 初始化 ====================
  function init() {
    generateBtn()?.addEventListener('click', startGeneration);
    stopBtn()?.addEventListener('click', stopGeneration);
    extendBtn()?.addEventListener('click', extendVideo);
    $('#clearRefBtn')?.addEventListener('click', clearRefImage);

    setupImageUpload();
    setupAutoSave();
    updateUI();
    setProgress(0, '准备就绪');
  }

  /**
   * 初始化自动保存：workspace 恢复 + 事件绑定
   */
  function setupAutoSave() {
    const toggle = autoSaveToggle();
    const btn = selectFolderBtn();
    const pathEl = folderPathEl();

    // 不支持 File System API 时禁用目录选择
    if (typeof Workspace === 'undefined' || !Workspace.isSupported()) {
      if (btn) {
        btn.disabled = true;
        btn.title = (typeof Workspace !== 'undefined' && Workspace.getUnsupportedReason())
          || '当前浏览器不支持 File System Access API';
      }
    }

    // 开关联动目录选择按钮
    if (toggle && btn) {
      toggle.addEventListener('change', () => {
        if (toggle.checked && typeof Workspace !== 'undefined' && Workspace.isSupported()) {
          btn.disabled = false;
        } else if (!toggle.checked) {
          btn.disabled = true;
        }
      });
    }

    // 目录选择按钮
    if (btn) {
      btn.addEventListener('click', async () => {
        if (typeof Workspace === 'undefined') return;
        try {
          const handle = await Workspace.requestWorkspace();
          if (pathEl) {
            pathEl.textContent = handle.name;
            btn.style.color = '#059669';
          }
          showToast('已选择保存位置: ' + handle.name, 'success');
        } catch (e) {
          if (e.name !== 'AbortError') {
            showToast('选择目录失败', 'error');
          }
        }
      });
    }

    // 尝试从 IndexedDB 恢复已有目录
    if (typeof Workspace !== 'undefined' && Workspace.isSupported()) {
      Workspace.initWorkspace().then(handle => {
        if (!handle) return;
        handle.queryPermission({ mode: 'readwrite' }).then(perm => {
          if (perm === 'granted') {
            if (pathEl) pathEl.textContent = handle.name;
            if (btn) btn.style.color = '#059669';
            if (toggle) {
              toggle.checked = true;
              if (btn) btn.disabled = false;
            }
          }
        });
      }).catch(() => {});
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
