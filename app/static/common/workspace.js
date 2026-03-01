/**
 * 工作目录管理模块
 * 使用 File System Access API + IndexedDB 持久化本地工作目录
 * 提供图片存储、元数据读写等统一接口
 */

const _WS = (() => {
  const DB_NAME = 'grok2api-workspace';
  const STORE_NAME = 'handles';
  const HANDLE_KEY = 'workdir';
  const METADATA_FILE = 'image_metadata.json';

  let _dirHandle = null;

  // ── IndexedDB helpers ────────────────────────────────────────────────────

  function _openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = (e) => {
        e.target.result.createObjectStore(STORE_NAME);
      };
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  async function _saveHandleToIDB(handle) {
    const db = await _openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).put(handle, HANDLE_KEY);
      tx.oncomplete = resolve;
      tx.onerror = (e) => reject(e.target.error);
    });
  }

  async function _loadHandleFromIDB() {
    const db = await _openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const req = tx.objectStore(STORE_NAME).get(HANDLE_KEY);
      req.onsuccess = (e) => resolve(e.target.result || null);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  async function _clearHandleFromIDB() {
    const db = await _openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).delete(HANDLE_KEY);
      tx.oncomplete = resolve;
      tx.onerror = (e) => reject(e.target.error);
    });
  }

  // ── 公开 API ─────────────────────────────────────────────────────────────

  /**
   * 初始化：从 IndexedDB 恢复目录 handle，验证权限
   * @returns {FileSystemDirectoryHandle|null}
   */
  async function initWorkspace() {
    if (_dirHandle) return _dirHandle;
    try {
      const handle = await _loadHandleFromIDB();
      if (!handle) return null;

      // 验证权限
      const perm = await handle.queryPermission({ mode: 'readwrite' });
      if (perm === 'granted') {
        _dirHandle = handle;
        return _dirHandle;
      }
      // 权限未就绪（需用户手势请求）
      return handle; // 返回但 _dirHandle 未设置，由调用方决定是否请求
    } catch (e) {
      console.warn('[workspace] initWorkspace error:', e);
      return null;
    }
  }

  /**
   * 请求用户选择工作目录（需用户手势触发）
   * @returns {FileSystemDirectoryHandle}
   */
  async function requestWorkspace() {
    const handle = await window.showDirectoryPicker({ mode: 'readwrite', id: 'grok2api-workspace' });
    await _saveHandleToIDB(handle);
    _dirHandle = handle;
    return handle;
  }

  /**
   * 恢复已存储 handle 的权限（需用户手势触发）
   * @returns {boolean} 是否成功获得权限
   */
  async function resumePermission() {
    try {
      const handle = await _loadHandleFromIDB();
      if (!handle) return false;
      const perm = await handle.requestPermission({ mode: 'readwrite' });
      if (perm === 'granted') {
        _dirHandle = handle;
        return true;
      }
      return false;
    } catch (e) {
      console.warn('[workspace] resumePermission error:', e);
      return false;
    }
  }

  /**
   * 清除工作目录配置
   */
  async function clearWorkspace() {
    _dirHandle = null;
    await _clearHandleFromIDB();
  }

  /**
   * 获取当前目录 handle（可能为 null）
   */
  function getHandle() {
    return _dirHandle;
  }

  /**
   * 是否支持 File System Access API
   */
  function isSupported() {
    return typeof window.showDirectoryPicker === 'function';
  }

  /**
   * 不支持时的原因说明（便于前端展示更准确的提示）
   * @returns {string|null} 原因字符串，支持时返回 null
   */
  function getUnsupportedReason() {
    if (typeof window.showDirectoryPicker === 'function') return null;
    if (!window.isSecureContext) {
      return '需要通过 http://localhost 或 https:// 访问，当前使用 IP 地址访问导致 File System Access API 不可用';
    }
    return '当前浏览器不支持 File System Access API，请使用 Chrome 或 Edge';
  }

  // ── 元数据 I/O ────────────────────────────────────────────────────────────

  /**
   * 读取 image_metadata.json，返回解析后的对象
   * @returns {{ version: string, images: Array }}
   */
  async function readMetadata() {
    if (!_dirHandle) return { version: '1.0', images: [] };
    try {
      const fh = await _dirHandle.getFileHandle(METADATA_FILE);
      const file = await fh.getFile();
      return JSON.parse(await file.text());
    } catch (e) {
      return { version: '1.0', images: [] };
    }
  }

  /**
   * 写入 image_metadata.json
   * @param {{ version: string, images: Array }} data
   */
  async function writeMetadata(data) {
    if (!_dirHandle) throw new Error('workspace not set');
    const fh = await _dirHandle.getFileHandle(METADATA_FILE, { create: true });
    const writable = await fh.createWritable();
    await writable.write(JSON.stringify(data, null, 2));
    await writable.close();
  }

  /**
   * 追加一条图片元数据（prepend，保持最新在前）
   * @param {object} entry
   */
  async function addImageMetadata(entry) {
    const data = await readMetadata();
    data.images.unshift(entry);
    await writeMetadata(data);
  }

  /**
   * 更新指定 id 的图片元数据字段
   * @param {string} id
   * @param {object} patch 要更新的字段
   */
  async function updateImageMetadata(id, patch) {
    const data = await readMetadata();
    const idx = data.images.findIndex(img => img.id === id);
    if (idx >= 0) {
      data.images[idx] = { ...data.images[idx], ...patch };
      await writeMetadata(data);
    }
  }

  /**
   * 删除指定 id 的图片元数据（不删除文件）
   * @param {string} id
   */
  async function removeImageMetadata(id) {
    const data = await readMetadata();
    data.images = data.images.filter(img => img.id !== id);
    await writeMetadata(data);
  }

  // ── 图片文件 I/O ──────────────────────────────────────────────────────────

  /**
   * 将 base64 图片保存到工作目录
   * @param {string} base64 - 可包含 data:image/...;base64, 前缀
   * @param {string} filename
   */
  async function saveImage(base64, filename) {
    if (!_dirHandle) throw new Error('workspace not set');
    const raw = base64.includes(',') ? base64.split(',')[1] : base64;
    const binary = atob(raw);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const fh = await _dirHandle.getFileHandle(filename, { create: true });
    const writable = await fh.createWritable();
    await writable.write(bytes);
    await writable.close();
  }

  /**
   * 获取工作目录中指定文件的 ObjectURL
   * @param {string} filename
   * @returns {string} ObjectURL（使用后需 URL.revokeObjectURL 释放）
   */
  async function getImageURL(filename) {
    if (!_dirHandle) return null;
    try {
      const fh = await _dirHandle.getFileHandle(filename);
      const file = await fh.getFile();
      return URL.createObjectURL(file);
    } catch (e) {
      console.warn('[workspace] getImageURL failed:', filename, e);
      return null;
    }
  }

  /**
   * 检查文件是否存在于工作目录
   * @param {string} filename
   * @returns {boolean}
   */
  async function fileExists(filename) {
    if (!_dirHandle) return false;
    try {
      await _dirHandle.getFileHandle(filename);
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * 从工作目录删除图片文件
   * @param {string} filename
   */
  async function deleteImage(filename) {
    if (!_dirHandle) return;
    try {
      await _dirHandle.removeEntry(filename);
    } catch (e) {
      console.warn('[workspace] deleteImage failed:', filename, e);
    }
  }

  // ── 提示词 I/O ────────────────────────────────────────────────────────────

  const PROMPTS_FILE = 'prompts.json';

  /**
   * 读取 prompts.json，返回解析后的对象
   * @returns {{ version: string, prompts: Array }}
   */
  async function readPrompts() {
    if (!_dirHandle) return { version: '1.0', prompts: [] };
    try {
      const fh = await _dirHandle.getFileHandle(PROMPTS_FILE);
      const file = await fh.getFile();
      return JSON.parse(await file.text());
    } catch (e) {
      return { version: '1.0', prompts: [] };
    }
  }

  /**
   * 写入 prompts.json
   * @param {{ version: string, prompts: Array }} data
   */
  async function writePrompts(data) {
    if (!_dirHandle) throw new Error('workspace not set');
    const fh = await _dirHandle.getFileHandle(PROMPTS_FILE, { create: true });
    const writable = await fh.createWritable();
    await writable.write(JSON.stringify(data, null, 2));
    await writable.close();
  }

  /**
   * 追加一条提示词（prepend，保持最新在前）
   * @param {object} entry
   */
  async function addPrompt(entry) {
    const data = await readPrompts();
    data.prompts.unshift(entry);
    await writePrompts(data);
  }

  /**
   * 更新指定 id 的提示词字段
   * @param {string} id
   * @param {object} patch 要更新的字段
   */
  async function updatePrompt(id, patch) {
    const data = await readPrompts();
    const idx = data.prompts.findIndex(p => p.id === id);
    if (idx >= 0) {
      data.prompts[idx] = { ...data.prompts[idx], ...patch };
      await writePrompts(data);
    }
  }

  /**
   * 删除指定 id 的提示词
   * @param {string} id
   */
  async function removePrompt(id) {
    const data = await readPrompts();
    data.prompts = data.prompts.filter(p => p.id !== id);
    await writePrompts(data);
  }

  return {
    initWorkspace,
    requestWorkspace,
    resumePermission,
    clearWorkspace,
    getHandle,
    isSupported,
    getUnsupportedReason,
    readMetadata,
    writeMetadata,
    addImageMetadata,
    updateImageMetadata,
    removeImageMetadata,
    saveImage,
    getImageURL,
    fileExists,
    deleteImage,
    readPrompts,
    writePrompts,
    addPrompt,
    updatePrompt,
    removePrompt,
  };
})();

// 导出到全局
window.Workspace = _WS;
