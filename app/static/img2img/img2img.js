// 图生图 JavaScript

// 全局状态
const state = {
  uploadedFiles: [],
  generatedImages: [],
  isGenerating: false,
  currentModalImage: null
};

// Toast 通知（复用）
const Toast = window.Toast || {
  show(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <div class="toast-content">
        <div class="toast-message">${message}</div>
      </div>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  },
  success(message) { this.show(message, 'success'); },
  error(message) { this.show(message, 'error'); },
  warning(message) { this.show(message, 'warning'); },
  info(message) { this.show(message, 'info'); }
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  updateUI();
});

// 事件监听器
function initEventListeners() {
  const uploadZone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  const generateBtn = document.getElementById('generateBtn');
  const clearResultsBtn = document.getElementById('clearResultsBtn');
  const downloadAllBtn = document.getElementById('downloadAllBtn');
  const modalClose = document.getElementById('modalClose');
  const modalDownload = document.getElementById('modalDownload');
  const imageModal = document.getElementById('imageModal');

  // 上传区域点击
  uploadZone.addEventListener('click', (e) => {
    if (e.target.closest('.preview-remove')) return;
    fileInput.click();
  });

  // 文件选择
  fileInput.addEventListener('change', (e) => {
    handleFiles(Array.from(e.target.files));
    fileInput.value = ''; // 清空以允许重复选择同一文件
  });

  // 拖拽上传
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
  });

  uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
  });

  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    handleFiles(files);
  });

  // 生成按钮
  generateBtn.addEventListener('click', generateImages);

  // 清空结果
  clearResultsBtn.addEventListener('click', () => {
    state.generatedImages = [];
    updateUI();
    Toast.success('已清空生成结果');
  });

  // 下载全部
  downloadAllBtn.addEventListener('click', downloadAllImages);

  // 弹窗关闭
  modalClose.addEventListener('click', closeModal);
  imageModal.addEventListener('click', (e) => {
    if (e.target === imageModal || e.target.classList.contains('modal-backdrop')) {
      closeModal();
    }
  });

  // 弹窗下载
  modalDownload.addEventListener('click', () => {
    if (state.currentModalImage) {
      downloadImage(state.currentModalImage.data, state.currentModalImage.filename);
    }
  });

  // ESC 键关闭弹窗
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && imageModal.style.display !== 'none') {
      closeModal();
    }
  });
}

// 处理文件上传
function handleFiles(files) {
  if (files.length === 0) return;

  // 检查文件数量
  const totalFiles = state.uploadedFiles.length + files.length;
  if (totalFiles > 16) {
    Toast.error('最多只能上传 16 张图片');
    return;
  }

  // 检查文件大小和格式
  const maxSize = 50 * 1024 * 1024; // 50MB
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

  for (const file of files) {
    if (!allowedTypes.includes(file.type)) {
      Toast.error(`不支持的文件格式: ${file.name}`);
      continue;
    }

    if (file.size > maxSize) {
      Toast.error(`文件过大: ${file.name} (最大 50MB)`);
      continue;
    }

    // 读取文件
    const reader = new FileReader();
    reader.onload = (e) => {
      state.uploadedFiles.push({
        file: file,
        data: e.target.result,
        name: file.name
      });
      updateUI();
    };
    reader.readAsDataURL(file);
  }
}

// 移除上传的文件
function removeFile(index) {
  state.uploadedFiles.splice(index, 1);
  updateUI();
}

// 更新 UI
function updateUI() {
  const uploadPlaceholder = document.getElementById('uploadPlaceholder');
  const imagePreviewGrid = document.getElementById('imagePreviewGrid');
  const generateBtn = document.getElementById('generateBtn');
  const emptyState = document.getElementById('emptyState');
  const resultGrid = document.getElementById('resultGrid');
  const clearResultsBtn = document.getElementById('clearResultsBtn');
  const downloadAllBtn = document.getElementById('downloadAllBtn');

  // 更新上传区域
  if (state.uploadedFiles.length > 0) {
    uploadPlaceholder.style.display = 'none';
    imagePreviewGrid.classList.add('has-images');
    imagePreviewGrid.innerHTML = state.uploadedFiles.map((file, index) => `
      <div class="preview-item">
        <img src="${file.data}" alt="${file.name}">
        <button class="preview-remove" onclick="removeFile(${index})">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    `).join('');
  } else {
    uploadPlaceholder.style.display = 'flex';
    imagePreviewGrid.classList.remove('has-images');
    imagePreviewGrid.innerHTML = '';
  }

  // 更新生成按钮 - 只要有图片就可以点击，提示词可以在点击时检查
  generateBtn.disabled = state.uploadedFiles.length === 0 || state.isGenerating;

  // 更新结果区域
  if (state.generatedImages.length > 0) {
    emptyState.style.display = 'none';
    resultGrid.style.display = 'grid';
    resultGrid.innerHTML = state.generatedImages.map((img, index) => `
      <div class="result-item" onclick="openModal(${index})">
        <img src="${img.data}" alt="生成结果 ${index + 1}">
        <div class="result-item-actions">
          <button class="result-action-btn" onclick="event.stopPropagation(); downloadImage('${img.data}', '${img.filename}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载
          </button>
        </div>
      </div>
    `).join('');
    clearResultsBtn.style.display = 'block';
    downloadAllBtn.style.display = 'block';
  } else {
    emptyState.style.display = 'flex';
    resultGrid.style.display = 'none';
    clearResultsBtn.style.display = 'none';
    downloadAllBtn.style.display = 'none';
  }
}

// 生成图片
async function generateImages() {
  if (state.isGenerating) return;

  const prompt = document.getElementById('promptInput').value.trim();
  const count = parseInt(document.getElementById('countSelect').value);
  const format = document.getElementById('formatSelect').value;
  const stream = document.getElementById('streamToggle').checked;

  if (!prompt) {
    Toast.error('请输入编辑提示词');
    return;
  }

  if (state.uploadedFiles.length === 0) {
    Toast.error('请先上传参考图片');
    return;
  }

  state.isGenerating = true;
  updateUI();

  // 显示加载状态
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const resultGrid = document.getElementById('resultGrid');

  emptyState.style.display = 'none';
  resultGrid.style.display = 'none';
  loadingState.style.display = 'flex';

  const generateBtn = document.getElementById('generateBtn');
  generateBtn.classList.add('loading');
  generateBtn.querySelector('span').textContent = '生成中...';

  try {
    if (stream) {
      await generateImagesStream(prompt, count, format);
    } else {
      await generateImagesNonStream(prompt, count, format);
    }
  } catch (error) {
    console.error('生成失败:', error);
    Toast.error(`生成失败: ${error.message}`);
  } finally {
    state.isGenerating = false;
    loadingState.style.display = 'none';
    generateBtn.classList.remove('loading');
    generateBtn.querySelector('span').textContent = '开始生成';
    updateUI();
  }
}

// 非流式生成
async function generateImagesNonStream(prompt, count, format) {
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('model', 'grok-imagine-1.0-edit');
  formData.append('n', count);
  formData.append('response_format', format);
  formData.append('stream', 'false');

  // 添加图片文件
  for (const file of state.uploadedFiles) {
    formData.append('image', file.file);
  }

  const response = await fetch('/api/v1/admin/img2img', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || '生成失败');
  }

  const result = await response.json();

  // 处理结果
  if (result.data && result.data.length > 0) {
    for (let i = 0; i < result.data.length; i++) {
      const item = result.data[i];
      const imageData = item.b64_json || item.base64 || item.url;

      if (imageData && imageData !== 'error') {
        const dataUrl = imageData.startsWith('data:') ? imageData : `data:image/png;base64,${imageData}`;
        state.generatedImages.push({
          data: dataUrl,
          filename: `img2img_${Date.now()}_${i + 1}.png`
        });
      }
    }

    Toast.success(`成功生成 ${state.generatedImages.length} 张图片`);
  } else {
    Toast.warning('未生成任何图片');
  }
}

// 流式生成
async function generateImagesStream(prompt, count, format) {
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('model', 'grok-imagine-1.0-edit');
  formData.append('n', count);
  formData.append('response_format', format);
  formData.append('stream', 'true');

  // 添加图片文件
  for (const file of state.uploadedFiles) {
    formData.append('image', file.file);
  }

  const response = await fetch('/api/v1/admin/img2img', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error?.message || '生成失败');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let imageCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim() || !line.startsWith('data: ')) continue;

      const data = line.slice(6);
      if (data === '[DONE]') continue;

      try {
        const event = JSON.parse(data);

        // 处理完成事件（包含实际图片数据）
        if (event.type === 'image_generation.completed') {
          const imageData = event.b64_json || event.base64 || event.url;

          if (imageData && imageData !== 'error') {
            const dataUrl = imageData.startsWith('data:') ? imageData : `data:image/png;base64,${imageData}`;
            state.generatedImages.push({
              data: dataUrl,
              filename: `img2img_${Date.now()}_${++imageCount}.png`
            });

            // 实时更新 UI
            updateUI();

            // 显示结果区域
            document.getElementById('loadingState').style.display = 'none';
            document.getElementById('resultGrid').style.display = 'grid';
          }
        }
        // 处理进度事件（仅显示进度，不包含图片数据）
        else if (event.type === 'image_generation.partial_image') {
          // 可以在这里添加进度显示逻辑
          console.log(`图片 ${event.index} 生成进度: ${event.progress}%`);
        }
      } catch (e) {
        console.error('解析事件失败:', e);
      }
    }
  }

  if (imageCount > 0) {
    Toast.success(`成功生成 ${imageCount} 张图片`);
  } else {
    Toast.warning('未生成任何图片');
  }
}

// 下载图片
function downloadImage(dataUrl, filename) {
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  Toast.success('图片已下载');
}

// 下载全部图片
async function downloadAllImages() {
  if (state.generatedImages.length === 0) return;

  Toast.info('正在准备下载...');

  // 如果只有一张图片，直接下载
  if (state.generatedImages.length === 1) {
    downloadImage(state.generatedImages[0].data, state.generatedImages[0].filename);
    return;
  }

  // 多张图片打包成 ZIP
  try {
    // 动态加载 JSZip
    if (!window.JSZip) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js';
      document.head.appendChild(script);
      await new Promise((resolve, reject) => {
        script.onload = resolve;
        script.onerror = reject;
      });
    }

    const zip = new JSZip();
    const imgFolder = zip.folder('img2img_results');

    for (let i = 0; i < state.generatedImages.length; i++) {
      const img = state.generatedImages[i];
      const base64Data = img.data.split(',')[1];
      imgFolder.file(img.filename, base64Data, { base64: true });
    }

    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `img2img_results_${Date.now()}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    Toast.success('所有图片已打包下载');
  } catch (error) {
    console.error('打包下载失败:', error);
    Toast.error('打包下载失败，请逐个下载');
  }
}

// 打开图片预览弹窗
function openModal(index) {
  const img = state.generatedImages[index];
  if (!img) return;

  state.currentModalImage = img;
  const modal = document.getElementById('imageModal');
  const modalImage = document.getElementById('modalImage');

  modalImage.src = img.data;
  modal.style.display = 'flex';
}

// 关闭弹窗
function closeModal() {
  const modal = document.getElementById('imageModal');
  modal.style.display = 'none';
  state.currentModalImage = null;
}

// 暴露给全局
window.removeFile = removeFile;
window.openModal = openModal;
window.downloadImage = downloadImage;

// Prompt optimization functionality
(() => {
  const optimizePromptBtn = document.getElementById('optimizePromptBtn');
  const promptInput = document.getElementById('promptInput');
  const promptModal = document.getElementById('promptModal');
  const closePromptModal = document.getElementById('closePromptModal');
  const cancelOptimization = document.getElementById('cancelOptimization');
  const useOptimizedPrompt = document.getElementById('useOptimizedPrompt');
  const originalPromptText = document.getElementById('originalPromptText');
  const optimizedPromptText = document.getElementById('optimizedPromptText');
  const promptExplanation = document.getElementById('promptExplanation');
  const improvementsList = document.getElementById('improvementsList');

  // 新增：内联显示元素
  const optimizedPromptDisplay = document.getElementById('optimizedPromptDisplay');
  const optimizedPromptContent = document.getElementById('optimizedPromptContent');
  const useOptimizedPromptInline = document.getElementById('useOptimizedPromptInline');

  let currentOptimizedPrompt = '';

  function showPromptModal() {
    if (promptModal) {
      promptModal.classList.add('active');
    }
  }

  function hidePromptModal() {
    if (promptModal) {
      promptModal.classList.remove('active');
    }
  }

  // 新增：显示内联优化结果
  function showOptimizedPromptInline(optimizedPrompt) {
    if (optimizedPromptDisplay && optimizedPromptContent) {
      optimizedPromptContent.textContent = optimizedPrompt;
      optimizedPromptDisplay.style.display = 'block';
    }
  }

  // 新增：隐藏内联优化结果
  function hideOptimizedPromptInline() {
    if (optimizedPromptDisplay) {
      optimizedPromptDisplay.style.display = 'none';
    }
  }

  function displayOptimizationResult(result) {
    // 显示在模态框中
    if (originalPromptText) {
      originalPromptText.textContent = result.original_prompt;
    }
    if (optimizedPromptText) {
      optimizedPromptText.textContent = result.optimized_prompt;
    }
    if (promptExplanation) {
      promptExplanation.textContent = result.explanation;
    }
    if (improvementsList) {
      improvementsList.innerHTML = '';
      (result.improvements || []).forEach(improvement => {
        const li = document.createElement('li');
        li.textContent = improvement;
        improvementsList.appendChild(li);
      });
    }
    currentOptimizedPrompt = result.optimized_prompt;

    // 新增：同时显示在输入框下方
    showOptimizedPromptInline(result.optimized_prompt);
  }

  async function optimizePrompt() {
    console.log('[优化] 开始优化流程');
    const prompt = promptInput ? promptInput.value.trim() : '';
    console.log('[优化] 提示词:', prompt);

    if (!prompt) {
      console.warn('[优化] 提示词为空');
      Toast.warning('请先输入提示词');
      return;
    }

    // Disable button and show loading state
    if (optimizePromptBtn) {
      console.log('[优化] 禁用按钮，显示加载状态');
      optimizePromptBtn.disabled = true;
      const originalText = optimizePromptBtn.innerHTML;
      optimizePromptBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
        </svg>
        <span>优化中...</span>
      `;

      try {
        console.log('[优化] 准备发送 API 请求...');
        const requestBody = {
          prompt: prompt,
          context: 'img2img',
          language: 'auto'
        };
        console.log('[优化] 请求体:', requestBody);

        const response = await fetch('/api/v1/prompt/optimize', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        });

        console.log('[优化] API 响应状态:', response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error('[优化] API 错误响应:', errorText);
          throw new Error(`API 请求失败 (${response.status}): ${errorText}`);
        }

        console.log('[优化] 解析响应 JSON...');
        const result = await response.json();
        console.log('[优化] 优化结果:', result);

        console.log('[优化] 显示优化结果...');
        displayOptimizationResult(result);
        showPromptModal();
        console.log('[优化] 优化流程完成');

      } catch (error) {
        console.error('[优化] 错误:', error);
        console.error('[优化] 错误堆栈:', error.stack);
        Toast.error('优化失败: ' + error.message);
      } finally {
        if (optimizePromptBtn) {
          console.log('[优化] 恢复按钮状态');
          optimizePromptBtn.disabled = false;
          optimizePromptBtn.innerHTML = originalText;
        }
      }
    } else {
      console.error('[优化] 找不到优化按钮元素');
    }
  }

  function useOptimization() {
    if (currentOptimizedPrompt && promptInput) {
      promptInput.value = currentOptimizedPrompt;
      hidePromptModal();
      hideOptimizedPromptInline();
      Toast.success('已应用优化后的提示词');
    }
  }

  // Event listeners
  if (optimizePromptBtn) {
    optimizePromptBtn.addEventListener('click', optimizePrompt);
  }

  if (closePromptModal) {
    closePromptModal.addEventListener('click', hidePromptModal);
  }

  if (cancelOptimization) {
    cancelOptimization.addEventListener('click', hidePromptModal);
  }

  if (useOptimizedPrompt) {
    useOptimizedPrompt.addEventListener('click', useOptimization);
  }

  // 新增：内联"使用"按钮事件
  if (useOptimizedPromptInline) {
    useOptimizedPromptInline.addEventListener('click', useOptimization);
  }

  // Close modal when clicking outside
  if (promptModal) {
    promptModal.addEventListener('click', (e) => {
      if (e.target === promptModal) {
        hidePromptModal();
      }
    });
  }

  // Close modal with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && promptModal && promptModal.classList.contains('active')) {
      hidePromptModal();
    }
  });

  // 新增：当输入框内容改变时，隐藏优化结果
  if (promptInput) {
    promptInput.addEventListener('input', () => {
      if (optimizedPromptDisplay && optimizedPromptDisplay.style.display !== 'none') {
        // 如果当前显示的优化结果与输入框内容不同，则隐藏
        if (promptInput.value.trim() !== currentOptimizedPrompt) {
          hideOptimizedPromptInline();
        }
      }
    });
  }
})();
