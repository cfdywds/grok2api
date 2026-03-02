// 随机图片查看器

// 状态管理
const state = {
  currentImage: null,
  currentObjectURL: null,
  viewedIds: [],
  allImages: [],
};

// DOM 元素
const elements = {
  loadingState: null,
  imageContainer: null,
  emptyState: null,
  mainImage: null,
  favoriteBtn: null,
  favoriteBtnMobile: null,
  infoPanel: null,
  infoToggleBtn: null,
  infoToggleBtnMobile: null,
  prevBtn: null,
  nextBtn: null,
  deleteBtn: null,
  deleteBtnMobile: null,
  downloadBtn: null,
  downloadBtnMobile: null,
  resetBtn: null,
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  // 获取 DOM 元素
  elements.loadingState = document.getElementById('loading-state');
  elements.imageContainer = document.getElementById('image-container');
  elements.emptyState = document.getElementById('empty-state');
  elements.mainImage = document.getElementById('main-image');
  elements.favoriteBtn = document.getElementById('favorite-btn');
  elements.favoriteBtnMobile = document.getElementById('favorite-btn-mobile');
  elements.infoPanel = document.getElementById('info-panel');
  elements.infoToggleBtn = document.getElementById('info-toggle-btn');
  elements.infoToggleBtnMobile = document.getElementById('info-toggle-btn-mobile');
  elements.prevBtn = document.getElementById('prev-btn');
  elements.nextBtn = document.getElementById('next-btn');
  elements.deleteBtn = document.getElementById('delete-btn');
  elements.deleteBtnMobile = document.getElementById('delete-btn-mobile');
  elements.downloadBtn = document.getElementById('download-btn');
  elements.downloadBtnMobile = document.getElementById('download-btn-mobile');
  elements.resetBtn = document.getElementById('reset-btn');

  // 工作目录初始化
  const banner = document.getElementById('workspace-banner');
  const bannerMsg = document.getElementById('workspace-banner-msg');
  const bannerBtn = document.getElementById('workspace-banner-btn');

  if (!Workspace.isSupported()) {
    if (banner) {
      const reason = (Workspace.getUnsupportedReason && Workspace.getUnsupportedReason()) || '当前浏览器不支持 File System Access API，请使用 Chrome 或 Edge';
      bannerMsg.textContent = '⚠️ ' + reason;
      banner.style.display = 'flex';
    }
  } else {
    const handle = await Workspace.initWorkspace();
    if (!handle) {
      if (banner) banner.style.display = 'flex';
    } else {
      const perm = await handle.queryPermission({ mode: 'readwrite' });
      if (perm !== 'granted') {
        if (banner) {
          bannerMsg.textContent = '📁 工作目录权限已失效，请重新授权。';
          bannerBtn.textContent = '重新授权';
          banner.style.display = 'flex';
        }
      }
    }
  }

  if (bannerBtn) {
    bannerBtn.addEventListener('click', async () => {
      const ok = await Workspace.resumePermission().catch(() => false)
        || await Workspace.requestWorkspace().then(() => true).catch(() => false);
      if (ok && banner) banner.style.display = 'none';
      await loadImagePool();
      loadRandomImage();
    });
  }

  // 绑定事件
  bindEvents();

  // 加载图片池并显示第一张
  await loadImagePool();
  loadRandomImage();
});

// 绑定事件
function bindEvents() {
  // 收藏按钮
  elements.favoriteBtn.addEventListener('click', handleFavoriteClick);
  elements.favoriteBtnMobile.addEventListener('click', handleFavoriteClick);

  // 导航按钮
  elements.prevBtn.addEventListener('click', () => loadRandomImage('left'));
  elements.nextBtn.addEventListener('click', () => loadRandomImage('right'));

  // 信息面板切换
  elements.infoToggleBtn.addEventListener('click', toggleInfoPanel);
  elements.infoToggleBtnMobile.addEventListener('click', toggleInfoPanel);

  // 操作按钮
  elements.deleteBtn.addEventListener('click', handleDeleteClick);
  elements.deleteBtnMobile.addEventListener('click', handleDeleteClick);
  elements.downloadBtn.addEventListener('click', handleDownloadClick);
  elements.downloadBtnMobile.addEventListener('click', handleDownloadClick);
  elements.resetBtn.addEventListener('click', handleResetClick);

  // 点击图片切换到下一张
  elements.mainImage.addEventListener('click', () => loadRandomImage('right'));

  // 键盘事件
  document.addEventListener('keydown', handleKeyDown);

  // 触摸事件（移动端滑动）
  let touchStartX = 0;
  let touchEndX = 0;
  let touchStartY = 0;
  let touchEndY = 0;

  elements.imageContainer.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  });

  elements.imageContainer.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    touchEndY = e.changedTouches[0].screenY;
    handleSwipe();
  });

  function handleSwipe() {
    const diffX = touchStartX - touchEndX;
    const diffY = Math.abs(touchStartY - touchEndY);

    // 只有水平滑动距离大于垂直滑动距离时才触发
    if (Math.abs(diffX) > 50 && Math.abs(diffX) > diffY) {
      // 向左滑动显示下一张，向右滑动也显示下一张（随机）
      const direction = diffX > 0 ? 'left' : 'right';
      loadRandomImage(direction);
    }
  }
}

// 键盘事件处理
function handleKeyDown(e) {
  if (!state.currentImage) return;

  // 如果确认对话框打开，不处理键盘事件
  const confirmDialog = document.getElementById('confirm-dialog');
  if (confirmDialog && confirmDialog.style.display !== 'none') {
    return;
  }

  switch (e.key) {
    case 'ArrowLeft':
      e.preventDefault();
      loadRandomImage('left');
      break;
    case 'ArrowRight':
    case ' ': // 空格键
      e.preventDefault();
      loadRandomImage('right');
      break;
    case 'f':
    case 'F':
      e.preventDefault();
      handleFavoriteClick();
      break;
    case 'j':
    case 'J':
      e.preventDefault();
      handleDownloadClick();
      break;
    case 'i':
    case 'I':
      e.preventDefault();
      toggleInfoPanel();
      break;
    case 'd':
    case 'D':
    case 'Delete':
      e.preventDefault();
      handleDeleteClick();
      break;
  }
}

// 加载图片池（从本地 metadata）
async function loadImagePool() {
  try {
    const data = await Workspace.readMetadata();
    state.allImages = (data.images || []).filter(img => img.filename);
  } catch (e) {
    state.allImages = [];
  }
}

// 加载随机图片
async function loadRandomImage(direction = null) {
  try {
    // 退出动画
    if (state.currentImage && direction) {
      elements.mainImage.classList.add(direction === 'left' ? 'slide-left' : 'slide-right');
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    showLoading();

    // 从图片池筛选未浏览的图片
    const candidates = state.allImages.filter(img => !state.viewedIds.includes(img.id));

    if (candidates.length === 0) {
      showEmpty();
      return;
    }

    // 随机选取一张
    const img = candidates[Math.floor(Math.random() * candidates.length)];
    state.currentImage = img;
    state.viewedIds.push(img.id);

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
async function showImage() {
  const img = state.currentImage;

  // 释放上一张的 ObjectURL
  if (state.currentObjectURL) {
    URL.revokeObjectURL(state.currentObjectURL);
    state.currentObjectURL = null;
  }

  // 移除旧的动画类
  elements.mainImage.classList.remove('slide-left', 'slide-right', 'fade-in');

  // 从工作目录获取 ObjectURL
  const objectURL = await Workspace.getImageURL(img.filename);
  if (!objectURL) {
    showToast('图片文件不存在于工作目录', 'error');
    showEmpty();
    return;
  }
  state.currentObjectURL = objectURL;
  elements.mainImage.src = objectURL;
  elements.mainImage.alt = img.prompt || '';

  // 进入动画
  setTimeout(() => {
    elements.mainImage.classList.add('fade-in');
  }, 50);

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
  const updateBtn = (btn) => {
    if (favorited) {
      btn.classList.add('favorited');
      btn.title = '取消收藏';
    } else {
      btn.classList.remove('favorited');
      btn.title = '收藏';
    }
  };

  updateBtn(elements.favoriteBtn);
  updateBtn(elements.favoriteBtnMobile);
}

// 更新信息面板
function updateInfoPanel(img) {
  // 提示词
  document.getElementById('info-prompt').textContent = img.prompt || '-';

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
  // 在移动端，使用 Toast 显示信息而不是面板
  if (window.innerWidth <= 768) {
    if (!state.currentImage) return;

    const img = state.currentImage;
    const sizeText = img.width && img.height
      ? `${img.width} × ${img.height}`
      : '-';

    const message = `尺寸: ${sizeText}`;
    showToast(message, 'info');
  } else {
    elements.infoPanel.classList.toggle('collapsed');
  }
}

// 处理收藏点击
async function handleFavoriteClick() {
  if (!state.currentImage) return;

  const newFavoriteState = !state.currentImage.favorite;

  try {
    await Workspace.updateImageMetadata(state.currentImage.id, { favorite: newFavoriteState });
    state.currentImage.favorite = newFavoriteState;
    // 同步图片池中的状态
    const poolImg = state.allImages.find(img => img.id === state.currentImage.id);
    if (poolImg) poolImg.favorite = newFavoriteState;
    updateFavoriteButton(newFavoriteState);
    showToast(newFavoriteState ? '已收藏' : '已取消收藏', 'success');
  } catch (error) {
    console.error('切换收藏状态失败:', error);
    showToast('操作失败', 'error');
  }
}

// 处理删除点击
async function handleDeleteClick() {
  if (!state.currentImage) return;

  const confirmed = await showConfirm(
    '确认删除',
    '确定要删除这张图片吗？此操作不可恢复。'
  );

  if (!confirmed) return;

  try {
    const { id, filename } = state.currentImage;
    await Workspace.removeImageMetadata(id);
    await Workspace.deleteImage(filename);

    // 释放 ObjectURL
    if (state.currentObjectURL) {
      URL.revokeObjectURL(state.currentObjectURL);
      state.currentObjectURL = null;
    }

    // 从图片池移除
    state.allImages = state.allImages.filter(img => img.id !== id);

    showToast('删除成功', 'success');
    loadRandomImage('right');
  } catch (error) {
    console.error('删除图片失败:', error);
    showToast('删除失败', 'error');
  }
}

// 处理下载点击
async function handleDownloadClick() {
  if (!state.currentImage) return;

  const objectURL = state.currentObjectURL
    || await Workspace.getImageURL(state.currentImage.filename);

  if (!objectURL) {
    showToast('图片文件不存在', 'error');
    return;
  }

  const link = document.createElement('a');
  link.href = objectURL;
  link.download = state.currentImage.filename;
  link.click();

  showToast('开始下载', 'info');
}

// 处理重置点击
function handleResetClick() {
  state.viewedIds = [];
  loadRandomImage();
}
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

// 显示确认对话框
function showConfirm(title, message) {
  return new Promise((resolve) => {
    const dialog = document.getElementById('confirm-dialog');
    const titleEl = document.getElementById('confirm-title');
    const messageEl = document.getElementById('confirm-message');
    const cancelBtn = document.getElementById('confirm-cancel');
    const okBtn = document.getElementById('confirm-ok');

    // 设置内容
    titleEl.textContent = title;
    messageEl.textContent = message;

    // 显示对话框
    dialog.style.display = 'flex';

    // 处理按钮点击
    const handleCancel = () => {
      dialog.style.display = 'none';
      cleanup();
      resolve(false);
    };

    const handleOk = () => {
      dialog.style.display = 'none';
      cleanup();
      resolve(true);
    };

    const handleOverlayClick = (e) => {
      if (e.target.classList.contains('confirm-overlay')) {
        handleCancel();
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleCancel();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        handleOk();
      }
    };

    // 绑定事件
    cancelBtn.addEventListener('click', handleCancel);
    okBtn.addEventListener('click', handleOk);
    dialog.addEventListener('click', handleOverlayClick);
    document.addEventListener('keydown', handleKeyDown);

    // 清理函数
    function cleanup() {
      cancelBtn.removeEventListener('click', handleCancel);
      okBtn.removeEventListener('click', handleOk);
      dialog.removeEventListener('click', handleOverlayClick);
      document.removeEventListener('keydown', handleKeyDown);
    }
  });
}
