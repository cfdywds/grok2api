// 通用确认对话框
const Dialog = {
  confirm(options) {
    return new Promise((resolve) => {
      const {
        title = '确认操作',
        message = '确定要执行此操作吗？',
        confirmText = '确定',
        cancelText = '取消',
        type = 'warning' // warning, danger, info
      } = options;

      const dialog = document.createElement('div');
      dialog.className = 'common-dialog-overlay';

      const iconMap = {
        warning: '⚠️',
        danger: '🗑️',
        info: 'ℹ️'
      };

      dialog.innerHTML = `
        <div class="common-dialog-content">
          <div class="common-dialog-icon ${type}">${iconMap[type] || iconMap.warning}</div>
          <div class="common-dialog-title">${title}</div>
          <div class="common-dialog-message">${message}</div>
          <div class="common-dialog-actions">
            <button class="common-dialog-btn cancel-btn">${cancelText}</button>
            <button class="common-dialog-btn confirm-btn ${type}">${confirmText}</button>
          </div>
        </div>
      `;

      document.body.appendChild(dialog);

      const confirmBtn = dialog.querySelector('.confirm-btn');
      const cancelBtn = dialog.querySelector('.cancel-btn');

      const close = (result) => {
        dialog.style.animation = 'fadeOut 0.2s ease';
        setTimeout(() => {
          dialog.remove();
          resolve(result);
        }, 200);
      };

      confirmBtn.addEventListener('click', () => close(true));
      cancelBtn.addEventListener('click', () => close(false));
      dialog.addEventListener('click', (e) => {
        if (e.target === dialog) close(false);
      });

      // ESC 键关闭
      const escHandler = (e) => {
        if (e.key === 'Escape') {
          close(false);
          document.removeEventListener('keydown', escHandler);
        }
      };
      document.addEventListener('keydown', escHandler);
    });
  },

  alert(options) {
    return new Promise((resolve) => {
      const {
        title = '提示',
        message = '',
        confirmText = '确定',
        type = 'info'
      } = typeof options === 'string' ? { message: options } : options;

      const dialog = document.createElement('div');
      dialog.className = 'common-dialog-overlay';

      const iconMap = {
        success: '✓',
        error: '✕',
        warning: '⚠️',
        info: 'ℹ️'
      };

      dialog.innerHTML = `
        <div class="common-dialog-content">
          <div class="common-dialog-icon ${type}">${iconMap[type] || iconMap.info}</div>
          <div class="common-dialog-title">${title}</div>
          <div class="common-dialog-message">${message}</div>
          <div class="common-dialog-actions">
            <button class="common-dialog-btn confirm-btn ${type}">${confirmText}</button>
          </div>
        </div>
      `;

      document.body.appendChild(dialog);

      const confirmBtn = dialog.querySelector('.confirm-btn');

      const close = () => {
        dialog.style.animation = 'fadeOut 0.2s ease';
        setTimeout(() => {
          dialog.remove();
          resolve();
        }, 200);
      };

      confirmBtn.addEventListener('click', close);
      dialog.addEventListener('click', (e) => {
        if (e.target === dialog) close();
      });

      // ESC 键关闭
      const escHandler = (e) => {
        if (e.key === 'Escape') {
          close();
          document.removeEventListener('keydown', escHandler);
        }
      };
      document.addEventListener('keydown', escHandler);
    });
  }
};

// 暴露到全局
window.Dialog = Dialog;
