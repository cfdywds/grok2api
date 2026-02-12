// 二维码模块加载状态
let qrcodeModuleLoaded = false;

// 加载二维码弹窗组件
function loadQRCodeModal() {
  fetch('/static/common/qrcode-modal.html')
    .then(response => response.text())
    .then(html => {
      const container = document.getElementById('qrcode-modal-container');
      if (container) {
        container.innerHTML = html;
        // 手动执行脚本
        const scripts = container.querySelectorAll('script');
        scripts.forEach(script => {
          const newScript = document.createElement('script');
          if (script.src) {
            newScript.src = script.src;
          } else {
            newScript.textContent = script.textContent;
          }
          document.body.appendChild(newScript);
        });
        // 等待脚本执行完成
        setTimeout(() => {
          qrcodeModuleLoaded = true;
        }, 100);
      }
    })
    .catch(error => {
      console.error('加载二维码弹窗失败:', error);
    });
}

// 处理二维码按钮点击
function handleQRCodeClick() {
  if (qrcodeModuleLoaded && typeof showQRCodeModal === 'function') {
    showQRCodeModal();
  } else {
    // 如果还没加载完成，等待加载
    const checkInterval = setInterval(() => {
      if (qrcodeModuleLoaded && typeof showQRCodeModal === 'function') {
        clearInterval(checkInterval);
        showQRCodeModal();
      }
    }, 100);

    // 5秒超时
    setTimeout(() => {
      clearInterval(checkInterval);
      if (!qrcodeModuleLoaded) {
        if (typeof Dialog !== 'undefined' && Dialog.alert) {
          Dialog.alert({
            title: '加载失败',
            message: '二维码功能加载失败，请刷新页面重试',
            type: 'error'
          });
        }
      }
    }, 5000);
  }
}

// 将函数暴露到全局作用域
window.handleQRCodeClick = handleQRCodeClick;

async function loadAdminHeader() {
  const container = document.getElementById('app-header');
  if (!container) return;
  try {
    const res = await fetch('/static/common/header.html?v=5');
    if (!res.ok) return;
    container.innerHTML = await res.text();
    const path = window.location.pathname;
    const links = container.querySelectorAll('a[data-nav]');
    links.forEach((link) => {
      const target = link.getAttribute('data-nav') || '';
      if (target && path.startsWith(target)) {
        link.classList.add('active');
        const group = link.closest('.nav-group');
        if (group) {
          const trigger = group.querySelector('.nav-group-trigger');
          if (trigger) {
            trigger.classList.add('active');
          }
        }
      }
    });
    if (typeof updateStorageModeButton === 'function') {
      updateStorageModeButton();
    }
    // 加载二维码弹窗
    loadQRCodeModal();
  } catch (e) {
    // Fail silently to avoid breaking page load
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadAdminHeader);
} else {
  loadAdminHeader();
}
