// 提示词管理 JavaScript

// Workspace 模式标志
let _useWorkspace = false;

// 状态管理
const state = {
  prompts: [],
  categories: [],
  tags: [],
  currentPrompt: null,
  filters: {
    search: '',
    category: '',
    tag: '',
    favorite: false,
  },
};

// DOM 元素
const elements = {
  promptsList: null,
  emptyState: null,
  totalCount: null,
  storageMode: null,
  searchInput: null,
  categoryFilter: null,
  tagFilter: null,
  favoriteFilter: null,
  addBtn: null,
  importBtn: null,
  exportBtn: null,
  promptDialog: null,
  importDialog: null,
};

// 生成简易 UUID
function _genId() {
  return 'xxxx-xxxx-xxxx'.replace(/x/g, () =>
    ((Math.random() * 16) | 0).toString(16)
  );
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  // 获取 DOM 元素
  elements.promptsList = document.getElementById('prompts-list');
  elements.emptyState = document.getElementById('empty-state');
  elements.totalCount = document.getElementById('total-count');
  elements.storageMode = document.getElementById('storage-mode');
  elements.searchInput = document.getElementById('search-input');
  elements.categoryFilter = document.getElementById('category-filter');
  elements.tagFilter = document.getElementById('tag-filter');
  elements.favoriteFilter = document.getElementById('favorite-filter');
  elements.addBtn = document.getElementById('add-btn');
  elements.importBtn = document.getElementById('import-btn');
  elements.exportBtn = document.getElementById('export-btn');
  elements.promptDialog = document.getElementById('prompt-dialog');
  elements.importDialog = document.getElementById('import-dialog');

  // 绑定事件
  bindEvents();

  // 初始化 workspace（异步），完成后加载数据
  _initWorkspaceMode().then(() => loadPrompts());
});

// Workspace 初始化
async function _initWorkspaceMode() {
  const banner = document.getElementById('workspace-banner');
  const bannerBtn = document.getElementById('workspace-banner-btn');

  if (typeof Workspace === 'undefined' || !Workspace.isSupported()) {
    // 不支持 File System Access API，隐藏 banner，服务器模式
    if (banner) banner.style.display = 'none';
    _setStorageIndicator(false);
    return;
  }

  const handle = await Workspace.initWorkspace();
  if (handle && Workspace.getHandle()) {
    // 已有权限的 workspace
    _useWorkspace = true;
    if (banner) banner.style.display = 'none';
    _setStorageIndicator(true);
    return;
  }

  if (handle) {
    // 有 handle 但权限未就绪，显示 banner 提示用户点击授权
    if (banner) {
      banner.style.display = 'flex';
      banner.querySelector('span').textContent = '📁 检测到工作目录，点击授权以使用本地存储。';
      if (bannerBtn) {
        bannerBtn.textContent = '授权访问';
        bannerBtn.onclick = async () => {
          const ok = await Workspace.resumePermission();
          if (ok) {
            _useWorkspace = true;
            banner.style.display = 'none';
            _setStorageIndicator(true);
            loadPrompts();
          } else {
            showToast('授权失败，将使用服务器存储', 'error');
          }
        };
      }
    }
    _setStorageIndicator(false);
    return;
  }

  // 无 handle，显示设置 banner
  if (banner) {
    banner.style.display = 'flex';
    if (bannerBtn) {
      bannerBtn.onclick = async () => {
        try {
          await Workspace.requestWorkspace();
          _useWorkspace = true;
          banner.style.display = 'none';
          _setStorageIndicator(true);
          loadPrompts();
        } catch (e) {
          console.warn('[prompts] requestWorkspace error:', e);
        }
      };
    }
  }
  _setStorageIndicator(false);
}

// 更新存储模式指示器
function _setStorageIndicator(isLocal) {
  if (!elements.storageMode) return;
  elements.storageMode.style.display = 'inline-block';
  if (isLocal) {
    elements.storageMode.textContent = '\uD83D\uDCC2 本地存储';
    elements.storageMode.style.color = '#059669';
  } else {
    elements.storageMode.textContent = '\u2601\uFE0F 服务器存储';
    elements.storageMode.style.color = '#6b7280';
  }
}

// 绑定事件
function bindEvents() {
  // 添加按钮
  elements.addBtn.addEventListener('click', () => openDialog());
  document.getElementById('add-first-btn').addEventListener('click', () => openDialog());

  // 导入导出
  elements.importBtn.addEventListener('click', openImportDialog);
  elements.exportBtn.addEventListener('click', exportPrompts);

  // 筛选
  elements.searchInput.addEventListener('input', debounce(handleFilterChange, 300));
  elements.categoryFilter.addEventListener('change', handleFilterChange);
  elements.tagFilter.addEventListener('change', handleFilterChange);
  elements.favoriteFilter.addEventListener('change', handleFilterChange);

  // 对话框
  document.getElementById('dialog-close').addEventListener('click', closeDialog);
  document.getElementById('dialog-cancel').addEventListener('click', closeDialog);
  document.getElementById('dialog-save').addEventListener('click', savePrompt);
  document.querySelector('#prompt-dialog .dialog-overlay').addEventListener('click', closeDialog);

  // 导入对话框
  document.getElementById('import-dialog-close').addEventListener('click', closeImportDialog);
  document.getElementById('import-dialog-cancel').addEventListener('click', closeImportDialog);
  document.getElementById('import-dialog-confirm').addEventListener('click', importPrompts);
  document.querySelector('#import-dialog .dialog-overlay').addEventListener('click', closeImportDialog);
}

// 加载提示词列表
async function loadPrompts() {
  try {
    if (_useWorkspace) {
      const data = await Workspace.readPrompts();
      let prompts = data.prompts || [];

      // 客户端筛选
      if (state.filters.search) {
        const q = state.filters.search.toLowerCase();
        prompts = prompts.filter(p =>
          (p.title || '').toLowerCase().includes(q) ||
          (p.content || '').toLowerCase().includes(q)
        );
      }
      if (state.filters.category) {
        prompts = prompts.filter(p => p.category === state.filters.category);
      }
      if (state.filters.tag) {
        prompts = prompts.filter(p => (p.tags || []).includes(state.filters.tag));
      }
      if (state.filters.favorite) {
        prompts = prompts.filter(p => p.favorite);
      }

      state.prompts = prompts;

      // 从全量数据中提取分类和标签
      const allPrompts = data.prompts || [];
      state.categories = [...new Set(allPrompts.map(p => p.category).filter(Boolean))];
      state.tags = [...new Set(allPrompts.flatMap(p => p.tags || []).filter(Boolean))];
    } else {
      const params = new URLSearchParams();
      if (state.filters.search) params.append('search', state.filters.search);
      if (state.filters.category) params.append('category', state.filters.category);
      if (state.filters.tag) params.append('tag', state.filters.tag);
      if (state.filters.favorite) params.append('favorite', 'true');

      const response = await fetch(`/api/v1/admin/prompts/list?${params}`);
      const data = await response.json();

      state.prompts = data.prompts || [];
      state.categories = data.categories || [];
      state.tags = data.tags || [];
    }

    updateUI();
  } catch (error) {
    console.error('加载提示词失败:', error);
    showToast('加载提示词失败', 'error');
  }
}

// 更新 UI
function updateUI() {
  // 更新统计
  elements.totalCount.textContent = `总计: ${state.prompts.length}`;

  // 更新筛选器
  updateFilters();

  // 更新列表
  if (state.prompts.length === 0) {
    elements.promptsList.style.display = 'none';
    elements.emptyState.style.display = 'flex';
  } else {
    elements.promptsList.style.display = 'grid';
    elements.emptyState.style.display = 'none';
    renderPrompts();
  }
}

// 更新筛选器
function updateFilters() {
  // 更新分类筛选器
  const currentCategory = elements.categoryFilter.value;
  elements.categoryFilter.innerHTML = '<option value="">全部分类</option>';
  state.categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category;
    option.textContent = category;
    if (category === currentCategory) option.selected = true;
    elements.categoryFilter.appendChild(option);
  });

  // 更新标签筛选器
  const currentTag = elements.tagFilter.value;
  elements.tagFilter.innerHTML = '<option value="">全部标签</option>';
  state.tags.forEach(tag => {
    const option = document.createElement('option');
    option.value = tag;
    option.textContent = tag;
    if (tag === currentTag) option.selected = true;
    elements.tagFilter.appendChild(option);
  });

  // 更新分类数据列表
  const categoryList = document.getElementById('category-list');
  categoryList.innerHTML = '';
  state.categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category;
    categoryList.appendChild(option);
  });
}

// 渲染提示词列表
function renderPrompts() {
  elements.promptsList.innerHTML = '';

  state.prompts.forEach(prompt => {
    const card = createPromptCard(prompt);
    elements.promptsList.appendChild(card);
  });
}

// 创建提示词卡片
function createPromptCard(prompt) {
  const card = document.createElement('div');
  card.className = 'prompt-card';
  card.dataset.id = prompt.id;

  // 标题和收藏按钮
  const header = document.createElement('div');
  header.className = 'prompt-header';

  const title = document.createElement('h3');
  title.className = 'prompt-title';
  title.textContent = prompt.title;

  const favoriteBtn = document.createElement('button');
  favoriteBtn.className = `favorite-btn ${prompt.favorite ? 'favorited' : ''}`;
  favoriteBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="${prompt.favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
    </svg>
  `;
  favoriteBtn.addEventListener('click', () => toggleFavorite(prompt.id));

  header.appendChild(title);
  header.appendChild(favoriteBtn);

  // 内容
  const content = document.createElement('div');
  content.className = 'prompt-content';
  content.textContent = prompt.content;

  // 元数据（分类和标签）
  const meta = document.createElement('div');
  meta.className = 'prompt-meta';

  const categoryBadge = document.createElement('span');
  categoryBadge.className = 'category-badge';
  categoryBadge.textContent = prompt.category;
  meta.appendChild(categoryBadge);

  (prompt.tags || []).forEach(tag => {
    const tagBadge = document.createElement('span');
    tagBadge.className = 'tag-badge';
    tagBadge.textContent = tag;
    meta.appendChild(tagBadge);
  });

  // 底部（使用次数和操作按钮）
  const footer = document.createElement('div');
  footer.className = 'prompt-footer';

  const useCount = document.createElement('span');
  useCount.className = 'use-count';
  useCount.textContent = `使用 ${prompt.use_count || 0} 次`;

  const actions = document.createElement('div');
  actions.className = 'prompt-actions';

  // 复制按钮
  const copyBtn = document.createElement('button');
  copyBtn.className = 'action-btn';
  copyBtn.title = '复制';
  copyBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
  `;
  copyBtn.addEventListener('click', () => copyPrompt(prompt));

  // 编辑按钮
  const editBtn = document.createElement('button');
  editBtn.className = 'action-btn';
  editBtn.title = '编辑';
  editBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
    </svg>
  `;
  editBtn.addEventListener('click', () => openDialog(prompt));

  // 删除按钮
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'action-btn';
  deleteBtn.title = '删除';
  deleteBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="3 6 5 6 21 6"></polyline>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
    </svg>
  `;
  deleteBtn.addEventListener('click', () => deletePrompt(prompt.id));

  actions.appendChild(copyBtn);
  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);

  footer.appendChild(useCount);
  footer.appendChild(actions);

  // 组装卡片
  card.appendChild(header);
  card.appendChild(content);
  card.appendChild(meta);
  card.appendChild(footer);

  return card;
}

// 打开对话框
function openDialog(prompt = null) {
  state.currentPrompt = prompt;

  const dialogTitle = document.getElementById('dialog-title');
  const titleInput = document.getElementById('prompt-title');
  const contentInput = document.getElementById('prompt-content');
  const categoryInput = document.getElementById('prompt-category');
  const tagsInput = document.getElementById('prompt-tags');

  if (prompt) {
    dialogTitle.textContent = '编辑提示词';
    titleInput.value = prompt.title;
    contentInput.value = prompt.content;
    categoryInput.value = prompt.category;
    tagsInput.value = (prompt.tags || []).join(', ');
  } else {
    dialogTitle.textContent = '添加提示词';
    titleInput.value = '';
    contentInput.value = '';
    categoryInput.value = '默认';
    tagsInput.value = '';
  }

  elements.promptDialog.style.display = 'flex';
}

// 关闭对话框
function closeDialog() {
  elements.promptDialog.style.display = 'none';
  state.currentPrompt = null;
}

// 保存提示词
async function savePrompt() {
  const title = document.getElementById('prompt-title').value.trim();
  const content = document.getElementById('prompt-content').value.trim();
  const category = document.getElementById('prompt-category').value.trim() || '默认';
  const tagsInput = document.getElementById('prompt-tags').value.trim();
  const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];

  if (!title) {
    showToast('请输入标题', 'error');
    return;
  }

  if (!content) {
    showToast('请输入内容', 'error');
    return;
  }

  try {
    if (_useWorkspace) {
      const now = new Date().toISOString();
      if (state.currentPrompt) {
        await Workspace.updatePrompt(state.currentPrompt.id, {
          title, content, category, tags, updated_at: now,
        });
      } else {
        const entry = {
          id: _genId(),
          title,
          content,
          category,
          tags,
          favorite: false,
          use_count: 0,
          created_at: now,
          updated_at: now,
        };
        await Workspace.addPrompt(entry);
      }
      showToast(state.currentPrompt ? '更新成功' : '添加成功', 'success');
      closeDialog();
      loadPrompts();
    } else {
      let response;
      if (state.currentPrompt) {
        response = await fetch(`/api/v1/admin/prompts/${state.currentPrompt.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, content, category, tags }),
        });
      } else {
        response = await fetch('/api/v1/admin/prompts/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, content, category, tags }),
        });
      }

      if (response.ok) {
        showToast(state.currentPrompt ? '更新成功' : '添加成功', 'success');
        closeDialog();
        loadPrompts();
      } else {
        throw new Error('保存失败');
      }
    }
  } catch (error) {
    console.error('保存提示词失败:', error);
    showToast('保存失败', 'error');
  }
}

// 切换收藏
async function toggleFavorite(promptId) {
  try {
    const prompt = state.prompts.find(p => p.id === promptId);
    if (!prompt) return;

    if (_useWorkspace) {
      await Workspace.updatePrompt(promptId, { favorite: !prompt.favorite });
      showToast(prompt.favorite ? '已取消收藏' : '已收藏', 'success');
      loadPrompts();
    } else {
      const response = await fetch(`/api/v1/admin/prompts/${promptId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ favorite: !prompt.favorite }),
      });

      if (response.ok) {
        showToast(prompt.favorite ? '已取消收藏' : '已收藏', 'success');
        loadPrompts();
      }
    }
  } catch (error) {
    console.error('切换收藏失败:', error);
    showToast('操作失败', 'error');
  }
}

// 复制提示词
async function copyPrompt(prompt) {
  try {
    await navigator.clipboard.writeText(prompt.content);
    showToast('已复制到剪贴板', 'success');

    // 增加使用次数
    if (_useWorkspace) {
      await Workspace.updatePrompt(prompt.id, {
        use_count: (prompt.use_count || 0) + 1,
      });
    } else {
      await fetch(`/api/v1/admin/prompts/${prompt.id}/use`, { method: 'POST' });
    }
    loadPrompts();
  } catch (error) {
    console.error('复制失败:', error);
    showToast('复制失败', 'error');
  }
}

// 删除提示词
async function deletePrompt(promptId) {
  const confirmed = await Dialog.confirm({
    title: '确认删除',
    message: '确定要删除这个提示词吗？',
    confirmText: '删除',
    cancelText: '取消',
    type: 'danger'
  });

  if (!confirmed) return;

  try {
    if (_useWorkspace) {
      await Workspace.removePrompt(promptId);
      showToast('删除成功', 'success');
      loadPrompts();
    } else {
      const response = await fetch('/api/v1/admin/prompts/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify([promptId]),
      });

      if (response.ok) {
        showToast('删除成功', 'success');
        loadPrompts();
      }
    }
  } catch (error) {
    console.error('删除失败:', error);
    showToast('删除失败', 'error');
  }
}

// 处理筛选变化
function handleFilterChange() {
  state.filters.search = elements.searchInput.value.trim();
  state.filters.category = elements.categoryFilter.value;
  state.filters.tag = elements.tagFilter.value;
  state.filters.favorite = elements.favoriteFilter.checked;

  loadPrompts();
}

// 打开导入对话框
function openImportDialog() {
  elements.importDialog.style.display = 'flex';
}

// 关闭导入对话框
function closeImportDialog() {
  elements.importDialog.style.display = 'none';
  document.getElementById('import-file').value = '';
}

// 导入提示词
async function importPrompts() {
  const fileInput = document.getElementById('import-file');
  const merge = document.getElementById('import-merge').checked;

  if (!fileInput.files.length) {
    showToast('请选择文件', 'error');
    return;
  }

  try {
    const file = fileInput.files[0];
    const text = await file.text();
    const importData = JSON.parse(text);

    if (_useWorkspace) {
      // 从导入数据中提取 prompts 数组
      const incoming = Array.isArray(importData)
        ? importData
        : (importData.prompts || []);

      if (merge) {
        // 合并模式：保留现有，追加不重复的
        const existing = await Workspace.readPrompts();
        const existingIds = new Set((existing.prompts || []).map(p => p.id));
        const now = new Date().toISOString();
        const newEntries = incoming
          .filter(p => !existingIds.has(p.id))
          .map(p => ({
            id: p.id || _genId(),
            title: p.title || '',
            content: p.content || '',
            category: p.category || '默认',
            tags: p.tags || [],
            favorite: p.favorite || false,
            use_count: p.use_count || 0,
            created_at: p.created_at || now,
            updated_at: p.updated_at || now,
          }));
        existing.prompts = [...newEntries, ...existing.prompts];
        await Workspace.writePrompts(existing);
        showToast(`已导入 ${newEntries.length} 条提示词（合并模式）`, 'success');
      } else {
        // 覆盖模式
        const now = new Date().toISOString();
        const entries = incoming.map(p => ({
          id: p.id || _genId(),
          title: p.title || '',
          content: p.content || '',
          category: p.category || '默认',
          tags: p.tags || [],
          favorite: p.favorite || false,
          use_count: p.use_count || 0,
          created_at: p.created_at || now,
          updated_at: p.updated_at || now,
        }));
        await Workspace.writePrompts({ version: '1.0', prompts: entries });
        showToast(`已导入 ${entries.length} 条提示词（覆盖模式）`, 'success');
      }
      closeImportDialog();
      loadPrompts();
    } else {
      const response = await fetch(`/api/v1/admin/prompts/import?merge=${merge}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(importData),
      });

      const result = await response.json();
      if (result.success) {
        showToast(result.message, 'success');
        closeImportDialog();
        loadPrompts();
      }
    }
  } catch (error) {
    console.error('导入失败:', error);
    showToast('导入失败，请检查文件格式', 'error');
  }
}

// 导出提示词
async function exportPrompts() {
  try {
    let data;
    if (_useWorkspace) {
      data = await Workspace.readPrompts();
    } else {
      const response = await fetch('/api/v1/admin/prompts/export/all');
      data = await response.json();
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `prompts_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);

    showToast('导出成功', 'success');
  } catch (error) {
    console.error('导出失败:', error);
    showToast('导出失败', 'error');
  }
}

// 防抖函数
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
