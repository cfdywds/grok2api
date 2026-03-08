/**
 * 场景导演前端逻辑
 */

const API_BASE = '/api/v1/admin/novel-director';
const GALLERY_API_BASE = '/api/v1/admin/gallery';

const elements = {};

// 状态管理
const state = {
  characters: [],
  projects: [],
  scenes: [],
  currentProject: null,
  currentScene: null,
  editingCharacterId: null,
  editingProjectId: null,
  projectCharacters: [],
  galleryImages: [],
  currentVideoTaskId: null,
  currentVideoEventSource: null,
  draggedSceneId: null,
};

async function getAuthHeaders(extraHeaders = {}) {
  const apiKey = await ensureApiKey();
  return {
    ...extraHeaders,
    ...buildAuthHeaders(apiKey),
  };
}

async function apiFetch(url, options = {}) {
  const method = options.method || 'GET';
  const headers = await getAuthHeaders(options.headers || {});
  const response = await fetch(url, {
    ...options,
    method,
    headers,
  });
  return response;
}

function resolveGalleryImageUrl(image) {
  if (!image) return '';
  if (image.url) return image.url;
  if (image.filename) return `/v1/files/image/${image.filename}`;
  return '';
}

function setCharacterReferenceImage(imageUrl) {
  document.getElementById('charRefImageUrl').value = imageUrl || '';
  const preview = document.getElementById('charRefPreview');
  const uploadText = document.getElementById('charRefImageArea').querySelector('.upload-text');
  if (imageUrl) {
    preview.src = imageUrl;
    preview.style.display = 'block';
    uploadText.style.display = 'none';
  } else {
    preview.src = '';
    preview.style.display = 'none';
    uploadText.style.display = 'block';
  }
}

function getProjectVideoConfig() {
  return {
    aspect_ratio: state.currentProject?.aspect_ratio || '16:9',
    resolution_name: state.currentProject?.resolution || '720p',
    preset: state.currentProject?.style_preset || 'normal',
    video_length: 6,
  };
}

async function refreshCurrentProject() {
  if (!state.currentProject?.id) return;
  const project = state.projects.find((item) => item.id === state.currentProject.id);
  if (project) {
    state.currentProject = project;
    document.getElementById('projectTitle').textContent = project.title;
  }
}


// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  initElements();
  initTabs();
  initModals();
  initEventListeners();
  await loadData();
});

function initElements() {
  elements.tabs = document.querySelectorAll('.tab-btn');
  elements.charactersTab = document.getElementById('charactersTab');
  elements.projectsTab = document.getElementById('projectsTab');
  elements.scenesTab = document.getElementById('scenesTab');
  elements.scenesTabContent = document.getElementById('scenesTabContent');
  elements.charactersList = document.getElementById('charactersList');
  elements.projectsList = document.getElementById('projectsList');
  elements.scenesList = document.getElementById('scenesList');
  elements.characterModal = document.getElementById('characterModal');
  elements.projectModal = document.getElementById('projectModal');
  elements.galleryPickerModal = document.getElementById('galleryPickerModal');
  elements.galleryPickerList = document.getElementById('galleryPickerList');
  elements.sceneEditorForm = document.getElementById('sceneEditorForm');
  elements.noSceneSelected = document.getElementById('noSceneSelected');
}

function initTabs() {
  elements.tabs.forEach((tab) => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });
}

function switchTab(tabName) {
  elements.tabs.forEach((t) => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

  elements.charactersTab.style.display = tabName === 'characters' ? 'block' : 'none';
  elements.projectsTab.style.display = tabName === 'projects' ? 'block' : 'none';
  elements.scenesTabContent.style.display = tabName === 'scenes' ? 'block' : 'none';
  elements.scenesTab.style.display = ['scenes', 'projects'].includes(tabName) ? 'block' : 'none';
}

function initModals() {
  // 角色弹窗
  document.querySelectorAll('#characterModal .modal-close, #cancelCharBtn').forEach((el) => {
    el.addEventListener('click', () => closeModal('character'));
  });

  document.getElementById('saveCharBtn').addEventListener('click', saveCharacter);

  // 项目弹窗
  document.querySelectorAll('#projectModal .modal-close, #cancelProjectBtn').forEach((el) => {
    el.addEventListener('click', () => closeModal('project'));
  });

  document.getElementById('saveProjectBtn').addEventListener('click', saveProject);

  // 画廊选择弹窗
  document.querySelectorAll('[data-close-modal="gallery"], #cancelGalleryPickerBtn').forEach((el) => {
    el.addEventListener('click', () => closeModal('gallery'));
  });

  // 点击背景关闭弹窗
  [elements.characterModal, elements.projectModal, elements.galleryPickerModal].forEach((modal) => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
      }
    });
  });
}

function openModal(type) {
  if (type === 'character') {
    elements.characterModal.classList.add('show');
  } else if (type === 'project') {
    elements.projectModal.classList.add('show');
  } else if (type === 'gallery') {
    elements.galleryPickerModal.classList.add('show');
  }
}

function closeModal(type) {
  if (type === 'character') {
    elements.characterModal.classList.remove('show');
    clearCharacterForm();
  } else if (type === 'project') {
    elements.projectModal.classList.remove('show');
    clearProjectForm();
  } else if (type === 'gallery') {
    elements.galleryPickerModal.classList.remove('show');
  }
}

function clearCharacterForm() {
  document.getElementById('charName').value = '';
  document.getElementById('charAppearance').value = '';
  document.getElementById('charPersonality').value = '';
  document.getElementById('charTraits').value = '';
  setCharacterReferenceImage('');
  state.editingCharacterId = null;
  document.getElementById('characterModalTitle').textContent = '新建角色';
}

function clearProjectForm() {
  document.getElementById('projectNameInput').value = '';
  document.getElementById('projectDescInput').value = '';
  document.getElementById('projectStyleInput').value = 'normal';
  document.getElementById('projectRatioInput').value = '16:9';
  document.getElementById('projectResolutionInput').value = '720p';
  state.editingProjectId = null;
  document.getElementById('projectModalTitle').textContent = '新建项目';
}

function initEventListeners() {
  // 新建角色按钮
  document.getElementById('addCharacterBtn').addEventListener('click', () => {
    clearCharacterForm();
    openModal('character');
  });

  // 新建项目按钮
  document.getElementById('addProjectBtn').addEventListener('click', () => {
    clearProjectForm();
    openModal('project');
  });

  // 返回项目列表
  document.getElementById('backToProjectsBtn').addEventListener('click', () => {
    switchTab('projects');
  });

  // 添加场景
  document.getElementById('addSceneBtn').addEventListener('click', createScene);

  // 保存场景
  document.getElementById('saveSceneBtn').addEventListener('click', saveCurrentScene);

  // 生成视频
  document.getElementById('generateVideoBtn').addEventListener('click', generateVideo);

  // 场景表单变化时更新 Prompt 预览
  ['sceneNarrative', 'sceneSetting', 'sceneMood', 'sceneCamera'].forEach((id) => {
    document.getElementById(id).addEventListener('input', updatePromptPreview);
  });

  // 角色参考图上传
  document.getElementById('charRefImageArea').addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = handleRefImageUpload;
    input.click();
  });

  // AI 生成参考图
  document.getElementById('generateRefBtn').addEventListener('click', generateCharacterRef);
  document.getElementById('selectFromGalleryBtn').addEventListener('click', openGalleryPicker);
}

async function loadData() {
  await Promise.all([loadCharacters(), loadProjects()]);
}

async function loadCharacters() {
  try {
    const res = await apiFetch(`${API_BASE}/characters`);
    if (!res.ok) throw new Error('Failed to load characters');
    state.characters = await res.json();
    renderCharacters();
  } catch (e) {
    console.error('Load characters error:', e);
  }
}

async function loadProjects() {
  try {
    const res = await apiFetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to load projects');
    state.projects = await res.json();
    renderProjects();
    await refreshCurrentProject();
  } catch (e) {
    console.error('Load projects error:', e);
  }
}

function renderCharacters() {
  if (state.characters.length === 0) {
    elements.charactersList.innerHTML = `
      <div class="empty-state">
        <p>暂无角色，点击「新建角色」开始创建</p>
      </div>
    `;
    return;
  }

  elements.charactersList.innerHTML = state.characters
    .map(
      (char) => `
    <div class="character-card" data-id="${char.id}">
      ${
        char.reference_image_url
          ? `<img src="${char.reference_image_url}" class="character-avatar" alt="${char.name}">`
          : `<div class="character-avatar"></div>`
      }
      <div class="character-name">${escapeHtml(char.name)}</div>
      <div class="character-personality">${escapeHtml(char.personality || '暂无性格描述')}</div>
      <div class="character-traits">
        ${(char.traits || []).map((t) => `<span class="trait-tag">${escapeHtml(t)}</span>`).join('')}
      </div>
      <div class="character-actions">
        <button class="geist-button secondary text-sm" onclick="editCharacter('${char.id}')">编辑</button>
        <button class="geist-button danger text-sm" onclick="deleteCharacter('${char.id}')">删除</button>
      </div>
    </div>
  `
    )
    .join('');
}

function renderProjects() {
  if (state.projects.length === 0) {
    elements.projectsList.innerHTML = `
      <div class="empty-state">
        <p>暂无项目，点击「新建项目」开始创作</p>
      </div>
    `;
    return;
  }

  elements.projectsList.innerHTML = state.projects
    .map(
      (project) => `
    <div class="project-card" data-id="${project.id}" onclick="openProject('${project.id}')">
      <div class="project-title">${escapeHtml(project.title)}</div>
      <div class="project-desc">${escapeHtml(project.description || '暂无简介')}</div>
      <div class="project-meta">
        <span>${project.scenes?.length || 0} 场景</span>
        <span>${project.characters?.length || 0} 角色</span>
        <span>${project.style_preset}</span>
      </div>
      <div class="project-actions" onclick="event.stopPropagation()">
        <button class="geist-button secondary text-sm" onclick="editProject('${project.id}')">编辑</button>
        <button class="geist-button danger text-sm" onclick="deleteProject('${project.id}')">删除</button>
      </div>
    </div>
  `
    )
    .join('');
}

async function saveCharacter() {
  const name = document.getElementById('charName').value.trim();
  if (!name) {
    toast.error('请输入角色名');
    return;
  }

  const data = {
    name,
    appearance: document.getElementById('charAppearance').value.trim(),
    personality: document.getElementById('charPersonality').value.trim(),
    traits: document
      .getElementById('charTraits')
      .value.split(',')
      .map((t) => t.trim())
      .filter(Boolean),
    reference_image_url: document.getElementById('charRefImageUrl').value.trim() || null,
  };

  try {
    const url = state.editingCharacterId
      ? `${API_BASE}/characters/${state.editingCharacterId}`
      : `${API_BASE}/characters`;
    const method = state.editingCharacterId ? 'PUT' : 'POST';

    const res = await apiFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error('Failed to save character');

    toast.success(state.editingCharacterId ? '角色已更新' : '角色已创建');
    closeModal('character');
    await loadCharacters();
  } catch (e) {
    toast.error('保存失败: ' + e.message);
  }
}

window.editCharacter = async function (id) {
  const char = state.characters.find((c) => c.id === id);
  if (!char) return;

  state.editingCharacterId = id;
  document.getElementById('characterModalTitle').textContent = '编辑角色';
  document.getElementById('charName').value = char.name;
  document.getElementById('charAppearance').value = char.appearance || '';
  document.getElementById('charPersonality').value = char.personality || '';
  document.getElementById('charTraits').value = (char.traits || []).join(', ');
  document.getElementById('charRefImageUrl').value = char.reference_image_url || '';

  setCharacterReferenceImage(char.reference_image_url || '');

  openModal('character');
};

window.deleteCharacter = async function (id) {
  if (!confirm('确定删除该角色？相关场景中的角色引用也会被移除。')) return;

  try {
    const res = await apiFetch(`${API_BASE}/characters/${id}`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error('Failed to delete character');

    toast.success('角色已删除');
    await loadCharacters();
  } catch (e) {
    toast.error('删除失败: ' + e.message);
  }
};

async function saveProject() {
  const title = document.getElementById('projectNameInput').value.trim();
  if (!title) {
    toast.error('请输入项目名称');
    return;
  }

  const data = {
    title,
    description: document.getElementById('projectDescInput').value.trim(),
    style_preset: document.getElementById('projectStyleInput').value,
    aspect_ratio: document.getElementById('projectRatioInput').value,
    resolution: document.getElementById('projectResolutionInput').value,
  };

  try {
    const url = state.editingProjectId
      ? `${API_BASE}/projects/${state.editingProjectId}`
      : `${API_BASE}/projects`;
    const method = state.editingProjectId ? 'PUT' : 'POST';

    const res = await apiFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error('Failed to save project');

    toast.success(state.editingProjectId ? '项目已更新' : '项目已创建');
    closeModal('project');
    await loadProjects();
  } catch (e) {
    toast.error('保存失败: ' + e.message);
  }
}

window.editProject = async function (id) {
  const project = state.projects.find((p) => p.id === id);
  if (!project) return;

  state.editingProjectId = id;
  document.getElementById('projectModalTitle').textContent = '编辑项目';
  document.getElementById('projectNameInput').value = project.title;
  document.getElementById('projectDescInput').value = project.description || '';
  document.getElementById('projectStyleInput').value = project.style_preset || 'normal';
  document.getElementById('projectRatioInput').value = project.aspect_ratio || '16:9';
  document.getElementById('projectResolutionInput').value = project.resolution || '720p';

  openModal('project');
};

window.deleteProject = async function (id) {
  if (!confirm('确定删除该项目？所有关联场景也会被删除。')) return;

  try {
    const res = await apiFetch(`${API_BASE}/projects/${id}`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error('Failed to delete project');

    toast.success('项目已删除');
    await loadProjects();
  } catch (e) {
    toast.error('删除失败: ' + e.message);
  }
};

window.openProject = async function (id) {
  state.currentProject = state.projects.find((p) => p.id === id);
  if (!state.currentProject) return;

  document.getElementById('projectTitle').textContent = state.currentProject.title;
  switchTab('scenes');
  await loadScenes(id);
};

async function loadScenes(projectId) {
  try {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}`);
    if (!res.ok) throw new Error('Failed to load scenes');

    const data = await res.json();
    state.scenes = data.scenes || [];
    state.projectCharacters = data.characters || [];
    renderScenes();
    renderCharacterSelect();
  } catch (e) {
    console.error('Load scenes error:', e);
  }
}

function renderScenes() {
  if (state.scenes.length === 0) {
    elements.scenesList.innerHTML = `
      <div class="empty-state">
        <p>暂无场景</p>
      </div>
    `;
    return;
  }

  elements.scenesList.innerHTML = state.scenes
    .map(
      (scene) => `
    <div class="scene-item ${state.currentScene?.id === scene.id ? 'active' : ''}" data-id="${scene.id}" draggable="true" onclick="selectScene('${scene.id}')">
      <div class="scene-item-header">
        <span class="scene-order">#${scene.order + 1}</span>
        <span class="scene-status ${scene.status}">${getStatusText(scene.status)}</span>
      </div>
      <div class="scene-narrative">${escapeHtml(scene.narrative || '未填写叙事')}</div>
      <div class="scene-item-actions">
        <button class="geist-button secondary text-sm" onclick="moveScene('${scene.id}', -1, event)">上移</button>
        <button class="geist-button secondary text-sm" onclick="moveScene('${scene.id}', 1, event)">下移</button>
        <button class="geist-button danger text-sm" onclick="deleteScene('${scene.id}', event)">删除</button>
      </div>
    </div>
  `
    )
    .join('');

  bindSceneDragEvents();
}

function getStatusText(status) {
  const map = { draft: '草稿', generating: '生成中', done: '已完成', ready: '就绪' };
  return map[status] || status;
}

function bindSceneDragEvents() {
  const sceneItems = elements.scenesList.querySelectorAll('.scene-item');
  sceneItems.forEach((item) => {
    item.addEventListener('dragstart', () => {
      state.draggedSceneId = item.dataset.id;
      item.classList.add('dragging');
    });
    item.addEventListener('dragend', () => {
      state.draggedSceneId = null;
      item.classList.remove('dragging');
      elements.scenesList.querySelectorAll('.scene-item').forEach((node) => node.classList.remove('drag-over'));
    });
    item.addEventListener('dragover', (event) => {
      event.preventDefault();
      if (state.draggedSceneId && state.draggedSceneId !== item.dataset.id) {
        item.classList.add('drag-over');
      }
    });
    item.addEventListener('dragleave', () => {
      item.classList.remove('drag-over');
    });
    item.addEventListener('drop', async (event) => {
      event.preventDefault();
      item.classList.remove('drag-over');
      if (!state.draggedSceneId || state.draggedSceneId === item.dataset.id) return;
      await reorderScenes(state.draggedSceneId, item.dataset.id);
    });
  });
}

async function persistSceneOrder(sceneIds) {
  const res = await apiFetch(`${API_BASE}/scenes/reorder`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      project_id: state.currentProject.id,
      scene_ids: sceneIds,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to reorder scenes');
  }
}

async function reorderScenes(sourceId, targetId) {
  const sourceIndex = state.scenes.findIndex((scene) => scene.id === sourceId);
  const targetIndex = state.scenes.findIndex((scene) => scene.id === targetId);
  if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return;

  const reordered = [...state.scenes];
  const [moved] = reordered.splice(sourceIndex, 1);
  reordered.splice(targetIndex, 0, moved);
  state.scenes = reordered.map((scene, index) => ({ ...scene, order: index }));
  renderScenes();

  try {
    await persistSceneOrder(state.scenes.map((scene) => scene.id));
    toast.success('场景顺序已更新');
  } catch (e) {
    toast.error('排序失败: ' + e.message);
    await loadScenes(state.currentProject.id);
  }
}

window.moveScene = async function (sceneId, direction, event) {
  event?.stopPropagation();
  const currentIndex = state.scenes.findIndex((scene) => scene.id === sceneId);
  const targetIndex = currentIndex + direction;
  if (currentIndex === -1 || targetIndex < 0 || targetIndex >= state.scenes.length) return;
  await reorderScenes(sceneId, state.scenes[targetIndex].id);
};

function renderCharacterSelect() {
  const container = document.getElementById('sceneCharacters');

  if (state.characters.length === 0) {
    container.innerHTML = '<p class="text-[var(--accents-4)] text-sm">请先创建角色</p>';
    return;
  }

  container.innerHTML = state.characters
    .map(
      (char) => `
    <label class="character-checkbox" data-id="${char.id}">
      <input type="checkbox" value="${char.id}" onchange="updatePromptPreview()">
      ${
        char.reference_image_url
          ? `<img src="${char.reference_image_url}" class="character-checkbox-avatar" alt="${char.name}">`
          : `<div class="character-checkbox-avatar"></div>`
      }
      <span class="character-checkbox-name">${escapeHtml(char.name)}</span>
    </label>
  `
    )
    .join('');
}

window.selectScene = function (id) {
  const scene = state.scenes.find((s) => s.id === id);
  if (!scene) return;

  state.currentScene = scene;
  elements.noSceneSelected.style.display = 'none';
  elements.sceneEditorForm.style.display = 'block';

  // 填充表单
  document.getElementById('sceneNarrative').value = scene.narrative || '';
  document.getElementById('sceneSetting').value = scene.setting || '';
  document.getElementById('sceneMood').value = scene.mood || '';
  document.getElementById('sceneCamera').value = scene.camera || '';

  // 选中角色
  document.querySelectorAll('#sceneCharacters input[type="checkbox"]').forEach((cb) => {
    cb.checked = (scene.characters || []).includes(cb.value);
    cb.closest('.character-checkbox').classList.toggle('selected', cb.checked);
  });

  // 显示视频预览按钮
  const previewBtn = document.getElementById('previewVideoBtn');
  if (scene.generated_video_url) {
    previewBtn.style.display = 'inline-block';
    previewBtn.onclick = () => {
      window.open(scene.generated_video_url, '_blank');
    };
  } else {
    previewBtn.style.display = 'none';
  }

  renderScenes();
  updatePromptPreview();
};

window.deleteScene = async function (id, event) {
  event?.stopPropagation();
  if (!confirm('确定删除该场景？')) return;

  try {
    const res = await apiFetch(`${API_BASE}/scenes/${id}`, {
      method: 'DELETE',
    });

    if (!res.ok) throw new Error('Failed to delete scene');

    toast.success('场景已删除');

    if (state.currentScene?.id === id) {
      state.currentScene = null;
      elements.noSceneSelected.style.display = 'block';
      elements.sceneEditorForm.style.display = 'none';
    }

    await loadScenes(state.currentProject.id);
  } catch (e) {
    toast.error('删除失败: ' + e.message);
  }
};

async function createScene() {
  try {
    const res = await apiFetch(`${API_BASE}/scenes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_id: state.currentProject.id,
        narrative: '',
        characters: [],
        setting: '',
        mood: '',
        camera: '',
      }),
    });

    if (!res.ok) throw new Error('Failed to create scene');

    const scene = await res.json();
    toast.success('场景已创建');
    await loadScenes(state.currentProject.id);
    selectScene(scene.id);
  } catch (e) {
    toast.error('创建失败: ' + e.message);
  }
}

async function saveCurrentScene() {
  if (!state.currentScene) return;

  const selectedChars = Array.from(
    document.querySelectorAll('#sceneCharacters input[type="checkbox"]:checked')
  ).map((cb) => cb.value);

  const data = {
    narrative: document.getElementById('sceneNarrative').value.trim(),
    setting: document.getElementById('sceneSetting').value.trim(),
    mood: document.getElementById('sceneMood').value,
    camera: document.getElementById('sceneCamera').value,
    characters: selectedChars,
  };

  try {
    const res = await apiFetch(`${API_BASE}/scenes/${state.currentScene.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error('Failed to save scene');

    toast.success('场景已保存');
    await loadScenes(state.currentProject.id);
  } catch (e) {
    toast.error('保存失败: ' + e.message);
  }
}

async function updatePromptPreview() {
  if (!state.currentScene) return;

  const selectedChars = Array.from(
    document.querySelectorAll('#sceneCharacters input[type="checkbox"]:checked')
  ).map((cb) => cb.value);

  const data = {
    narrative: document.getElementById('sceneNarrative').value.trim(),
    setting: document.getElementById('sceneSetting').value.trim(),
    mood: document.getElementById('sceneMood').value,
    camera: document.getElementById('sceneCamera').value,
    characters: selectedChars,
  };

  // 本地简单预览（不完全准确，仅用于实时反馈）
  const parts = [];
  if (data.narrative) parts.push(data.narrative);
  if (data.setting) parts.push(data.setting);

  const charDescriptions = state.characters
    .filter((c) => selectedChars.includes(c.id))
    .filter((c) => c.appearance)
    .map((c) => c.appearance);
  if (charDescriptions.length) parts.push(charDescriptions.join(', '));

  const moodMap = {
    紧张: 'tense, dramatic',
    温馨: 'warm, cozy',
    悲伤: 'melancholic, somber',
    欢快: 'cheerful, lively',
    神秘: 'mysterious, enigmatic',
    浪漫: 'romantic, dreamy',
    恐怖: 'horror, eerie',
    史诗: 'epic, grand',
    平静: 'peaceful, serene',
    激动: 'exciting, thrilling',
  };
  if (data.mood) parts.push((moodMap[data.mood] || data.mood) + ' atmosphere');

  const cameraMap = {
    特写: 'close-up shot',
    中景: 'medium shot',
    全景: 'wide shot',
    远景: 'extreme wide shot',
    俯视: 'high angle shot',
    仰视: 'low angle shot',
    跟拍: 'tracking shot',
    摇镜: 'panning shot',
  };
  if (data.camera) parts.push(cameraMap[data.camera] || data.camera);

  parts.push('cinematic, high quality');

  const preview = parts.length > 1 ? parts.join('. ') + '.' : '填写场景信息后自动生成...';
  document.getElementById('promptPreview').textContent = preview;
}

async function generateVideo() {
  if (!state.currentScene) return;

  const saveBtn = document.getElementById('saveSceneBtn');
  const genBtn = document.getElementById('generateVideoBtn');

  saveBtn.disabled = true;
  genBtn.disabled = true;
  genBtn.textContent = '准备生成...';

  try {
    await saveCurrentScene();
    await updateSceneGenerationState({ status: 'generating' });

    const promptRes = await apiFetch(`${API_BASE}/scenes/${state.currentScene.id}/build-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        style_preset: state.currentProject?.style_preset || 'normal',
        include_narrative: true,
      }),
    });

    if (!promptRes.ok) {
      const err = await promptRes.json().catch(() => ({}));
      throw new Error(err.detail || 'Prompt build failed');
    }

    const promptData = await promptRes.json();
    const videoBody = {
      prompt: promptData.prompt,
      image_url: promptData.reference_image_url || undefined,
      ...getProjectVideoConfig(),
      concurrent: 1,
    };

    const startRes = await apiFetch('/v1/video/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(videoBody),
    });

    if (!startRes.ok) {
      const err = await startRes.json().catch(() => ({}));
      throw new Error(err.detail || err.error?.message || 'Generation failed');
    }

    const startData = await startRes.json();
    const taskId = startData.task_id || startData.task_ids?.[0];
    if (!taskId) {
      throw new Error('未获取到视频任务 ID');
    }

    listenSceneVideoSSE(taskId, promptData.prompt);
  } catch (e) {
    await updateSceneGenerationState({ status: 'draft' }).catch(() => {});
    toast.error('生成失败: ' + e.message);
    restoreGenerateButton();
  }
}

async function handleRefImageUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    toast.info('上传中...');

    const res = await apiFetch(`${GALLERY_API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error('Upload failed');

    const data = await res.json();
    const imageUrl = data.url || (data.filename ? `/v1/files/image/${data.filename}` : '');

    setCharacterReferenceImage(imageUrl);
    toast.success(data.duplicate ? '图片已复用现有画廊资源' : '图片已上传');
  } catch (e) {
    toast.error('上传失败: ' + e.message);
  }
}

async function generateCharacterRef() {
  const appearance = document.getElementById('charAppearance').value.trim();
  if (!appearance) {
    toast.error('请先填写外貌描述');
    return;
  }

  const btn = document.getElementById('generateRefBtn');
  btn.disabled = true;
  btn.textContent = '生成中...';

  try {
    // 先保存角色（如果有 ID）或临时创建
    let charId = state.editingCharacterId;

    if (!charId) {
      // 临时创建角色以生成参考图
      const name = document.getElementById('charName').value.trim() || '临时角色';
      const res = await apiFetch(`${API_BASE}/characters`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name, appearance }),
      });
      const char = await res.json();
      charId = char.id;
      state.editingCharacterId = charId;
    }

    // 调用生成参考图
    const res = await apiFetch(`${API_BASE}/characters/${charId}/generate-ref`, {
      method: 'POST',
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Generation failed');
    }

    const data = await res.json();

    document.getElementById('charRefImageUrl').value = data.image_url;
    document.getElementById('charRefPreview').src = data.image_url;
    document.getElementById('charRefPreview').style.display = 'block';
    document.getElementById('charRefImageArea').querySelector('.upload-text').style.display = 'none';

    toast.success('参考图已生成');
    await loadCharacters();
  } catch (e) {
    toast.error('生成失败: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'AI 生成参考图';
  }
}

async function openGalleryPicker() {
  openModal('gallery');
  elements.galleryPickerList.innerHTML = `
    <div class="empty-state">
      <p>正在加载画廊图片...</p>
    </div>
  `;

  try {
    const res = await apiFetch(`${GALLERY_API_BASE}/images?page=1&page_size=24&sort_by=created_at&sort_order=desc`);
    if (!res.ok) throw new Error('Failed to load gallery images');
    const data = await res.json();
    state.galleryImages = data.images || [];
    renderGalleryPicker();
  } catch (e) {
    elements.galleryPickerList.innerHTML = `
      <div class="empty-state">
        <p>加载画廊失败：${escapeHtml(e.message || '未知错误')}</p>
      </div>
    `;
  }
}

function renderGalleryPicker() {
  if (!state.galleryImages.length) {
    elements.galleryPickerList.innerHTML = `
      <div class="empty-state">
        <p>画廊暂无可选图片</p>
      </div>
    `;
    return;
  }

  elements.galleryPickerList.innerHTML = state.galleryImages
    .map((image) => {
      const imageUrl = resolveGalleryImageUrl(image);
      return `
        <button class="gallery-picker-item" type="button" onclick="selectGalleryImage('${image.id}')">
          <img src="${imageUrl}" alt="${escapeHtml(image.prompt || image.filename || image.id)}">
          <span>${escapeHtml(image.prompt || image.filename || '未命名图片')}</span>
        </button>
      `;
    })
    .join('');
}

window.selectGalleryImage = function (imageId) {
  const image = state.galleryImages.find((item) => item.id === imageId);
  if (!image) return;

  setCharacterReferenceImage(resolveGalleryImageUrl(image));
  closeModal('gallery');
  toast.success('已从画廊选择参考图');
};

function cleanupVideoTask() {
  if (state.currentVideoEventSource) {
    state.currentVideoEventSource.close();
    state.currentVideoEventSource = null;
  }
  state.currentVideoTaskId = null;
}

function restoreGenerateButton() {
  const saveBtn = document.getElementById('saveSceneBtn');
  const genBtn = document.getElementById('generateVideoBtn');
  saveBtn.disabled = false;
  genBtn.disabled = false;
  genBtn.textContent = '生成视频';
}

async function updateSceneGenerationState(payload) {
  if (!state.currentScene?.id) return;
  await apiFetch(`${API_BASE}/scenes/${state.currentScene.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

function listenSceneVideoSSE(taskId, promptUsed) {
  cleanupVideoTask();
  state.currentVideoTaskId = taskId;

  const evtSource = new EventSource(`/v1/video/sse?task_id=${encodeURIComponent(taskId)}`);
  state.currentVideoEventSource = evtSource;

  evtSource.onmessage = async function (event) {
    const raw = event.data;
    if (raw === '[DONE]') {
      cleanupVideoTask();
      restoreGenerateButton();
      await loadScenes(state.currentProject.id);
      if (state.currentScene?.id) {
        selectScene(state.currentScene.id);
      }
      return;
    }

    try {
      const data = JSON.parse(raw);
      if (data.error) {
        throw new Error(data.error);
      }

      const choice = data.choices?.[0] || {};
      const delta = choice.delta || {};
      const content = delta.content || '';

      if (content.includes('超分辨率')) {
        document.getElementById('generateVideoBtn').textContent = '超分处理中...';
      } else if (content) {
        const progressMatch = content.match(/进度(\d+)%/);
        if (progressMatch) {
          document.getElementById('generateVideoBtn').textContent = `生成中 ${progressMatch[1]}%`;
        }
      }

      let videoUrl = '';
      const htmlMatch = content.match(/src="([^"]+)"/);
      if (htmlMatch) {
        videoUrl = htmlMatch[1];
      } else if (content.startsWith('http') && content.includes('/video')) {
        videoUrl = content.trim();
      }

      if (videoUrl) {
        await updateSceneGenerationState({
          status: 'done',
          prompt_used: promptUsed,
          generated_video_url: videoUrl,
        });
        toast.success('视频生成成功！');
      }

      if (choice.finish_reason === 'stop') {
        cleanupVideoTask();
        restoreGenerateButton();
        await loadScenes(state.currentProject.id);
        if (state.currentScene?.id) {
          selectScene(state.currentScene.id);
        }
      }
    } catch (e) {
      cleanupVideoTask();
      restoreGenerateButton();
      updateSceneGenerationState({ status: 'draft' }).catch(() => {});
      toast.error('生成失败: ' + (e.message || '未知错误'));
    }
  };

  evtSource.onerror = function () {
    cleanupVideoTask();
    restoreGenerateButton();
    updateSceneGenerationState({ status: 'draft' }).catch(() => {});
    toast.error('视频生成连接中断');
  };
}

