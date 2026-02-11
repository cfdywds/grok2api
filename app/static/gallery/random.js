// 随机图片查看器

// 状态管理
const state = {
  currentImage: null,
  viewedIds: [],
  minQualityScore: 40,
};

// DOM 元素
const elements = {
  loadingState: null,
  imageContainer: null,
  emptyState: null,
  mainImage: null,
  favoriteBtn: null,
  infoPanel: null,
  infoHeader: null,
  infoContent: null,
  swipeLeft: null,
  swipeRight: null,
  deleteBtn: null,
  downloadBtn: null,
  resetBtn: null,
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  // 获取 DOM 元素
  elements.loadingState = document.getElementById('loading-state');
  elements.imageContainer = document.getElementById('image-container');
  elements.emptyState = document.getElementById('empty-state');
  elements.mainImage = document.getElementById('main-image');
  elements.favoriteBtn = document.getElementById('favorite-btn');
  elements.infoPanel = document.getElementById('info-panel');
  elements.infoHeader = document.getElementById('info-header');
  elements.infoContent = document.getElementById('info-content');
  elements.swipeLeft = document.getElementById('swipe-left');
  elements.swipeRight = document.getElementById('swipe-right');
  elements.deleteBtn = document.getElementById('delete-btn');
  elements.downloadBtn = document.getElementById('download-btn');
  elements.resetBtn = document.getElementById('reset-btn');

  // 绑定事件
  bindEvents();

  // 加载第一张随机图片
  loadRandomImage();
});

// 绑定事件
function bindEvents() {
  // 收藏按钮
  elements.favoriteBtn.addEventListener('click', handleFavoriteClick);

  // 滑动区域
  elements.swipeLeft.addEventListener('click', () => loadRandomImage());
  elements.swipeRight.addEventListener('click', () => loadRandomImage());

  // 信息面板折叠
  elements.infoHeader.addEventListener('click', toggleInfoPanel);

  // 操作按钮
  elements.deleteBtn.addEventListener('click', handleDeleteClick);
  elements.downloadBtn.addEventListener('click', handleDownloadClick);
  elements.resetBtn.addEventListener('click', handleResetClick);

  // 键盘事件
  document.addEventListener('keydown', handleKeyDown);

  // 触摸事件（移动端滑动）
  let touchStartX = 0;
  let touchEndX = 0;

  elements.imageContainer.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });

  elements.imageContainer.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
  });

  function handleSwipe() {
    const diff = touchStartX - touchEndX;
    if (Math.abs(diff) > 50) {
      // 滑动距离超过 50px
      loadRandomImage();
    }
  }
}

// 键盘事件处理
function handleKeyDown(e) {
  if (!state.currentImage) return;

  switch (e.key) {
    case 'ArrowLeft':
    case 'ArrowRight':
      e.preventDefault();
      loadRandomImage();
      break;
    case 'f':
    case 'F':
      e.preventDefault();
      handleFavoriteClick();
      break;
    case 'Delete':
      e.preventDefault();
      handleDeleteClick();
      break;
  }
}

// 加载随机图片
async function loadRandomImage() {
  try {
    showLoading();

    // 构建排除 ID 列表
    const excludeIds = state.viewedIds.join(',');

    // 调用 API
    const response = await fetch(
      `/api/v1/admin/gallery/images/random?exclude_ids=${excludeIds}&min_quality_score=${state.minQualityScore}`
    );

    const result = await response.json();

    if (!result.success || !result.data) {
      showEmpty();
      return;
    }

    // 更新状态
    state.currentImage = result.data;
    state.viewedIds.push(result.data.id);

    // 显示图片
    showImage();
  } catch (error) {
    console.error('加载随机图片失败:', error);
    showToast('加载图片失败', 'error');
    showEmpty();
  }
}

// 显示加载状态
function showLoading() {
  elements.loadingState.style.display = 'flex';
  elements.imageContainer.style.display = 'none';
  elements.emptyState.style.display = 'none';
}

// 显示图片
function showImage() {
  const img = state.currentImage;

  // 设置图片
  elements.mainImage.src = `/data/tmp/image/${img.filename}`;
  elements.mainImage.alt = img.prompt;

  // 更新收藏按钮
  updateFavoriteButton(img.favorite || false);

  // 更新信息面板
  updateInfoPanel(img);

  // 显示容器
  elements.loadingState.style.display = 'none';
  elements.imageContainer.style.display = 'flex';
  elements.emptyState.style.display = 'none';
}

// 显示空状态
function showEmpty() {
  elements.loadingState.style.display = 'none';
  elements.imageContainer.style.display = 'none';
  elements.emptyState.style.display = 'flex';
}

// 更新收藏按钮
function updateFavoriteButton(favorited) {
  if (favorited) {
    elements.favoriteBtn.classList.add('favorited');
    elements.favoriteBtn.title = '取消收藏';
  } else {
    elements.favoriteBtn.classList.remove('favorited');
    elements.favoriteBtn.title = '收藏';
  }
}

// 更新信息面板
function updateInfoPanel(img) {
  // 提示词
  document.getElementById('info-prompt').textContent = img.prompt || '-';

  // 质量评分
  const qualityScore = img.quality_score || 0;
  const qualityFill = document.getElementById('quality-fill');
  const qualityText = document.getElementById('quality-text');

  qualityFill.style.width = `${qualityScore}%`;
  qualityText.textContent = qualityScore.toFixed(1);

  // 尺寸
  const sizeText = img.width && img.height
    ? `${img.width} × ${img.height} (${img.aspect_ratio || '-'})`
    : '-';
  document.getElementById('info-size').textContent = sizeText;

  // 创建时间
  const timeText = img.created_at
    ? new Date(img.created_at).toLocaleString('zh-CN')
    : '-';
  document.getElementById('info-time').textContent = timeText;
}

// 切换信息面板
function toggleInfoPanel() {
  elements.infoPanel.classList.toggle('collapsed');
}

// 处理收藏点击
async function handleFavoriteClick() {
  if (!state.currentImage) return;

  const newFavoriteState = !state.currentImage.favorite;

  try {
    const response = await fetch(
      `/api/v1/admin/gallery/images/${state.currentImage.id}/favorite`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ favorite: newFavoriteState }),
      }
    );

    const result = await response.json();

    if (result.success) {
      state.currentImage.favorite = newFavoriteState;
      updateFavoriteButton(newFavoriteState);
      showToast(newFavoriteState ? '已收藏' : '已取消收藏', 'success');
    } else {
      showToast('操作失败', 'error');
    }
  } catch (error) {
    console.error('切换收藏状态失败:', error);
    showToast('操作失败', 'error');
  }
}

// 处理删除点击
async function handleDeleteClick() {
  if (!state.currentImage) return;

  if (!confirm('确定要删除这张图片吗？此操作不可恢复。')) {
    return;
  }

  try {
    const response = await fetch('/api/v1/admin/gallery/images/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_ids: [state.currentImage.id] }),
    });

    const result = await response.json();

    if (result.success) {
      showToast('删除成功', 'success');
      // 加载下一张
      loadRandomImage();
    } else {
      showToast('删除失败', 'error');
    }
  } catch (error) {
    console.error('删除图片失败:', error);
    showToast('删除失败', 'error');
  }
}

// 处理下载点击
function handleDownloadClick() {
  if (!state.currentImage) return;

  const link = document.createElement('a');
  link.href = `/data/tmp/image/${state.currentImage.filename}`;
  link.download = state.currentImage.filename;
  link.click();

  showToast('开始下载', 'info');
}

// 处理重置点击
function handleResetClick() {
  state.viewedIds = [];
  loadRandomImage();
}

// 显示 Toast 通知
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  // 图标
  const iconSvg = {
    success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
    warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
  };

  toast.innerHTML = `
    ${iconSvg[type] || iconSvg.info}
    <div class="toast-message">${message}</div>
  `;

  container.appendChild(toast);

  // 3 秒后自动移除
  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease-out reverse';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
