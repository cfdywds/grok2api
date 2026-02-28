async function loadAdminHeader() {
  const container = document.getElementById('app-header') || document.getElementById('header-container');
  if (!container) return;
  try {
    const res = await fetch('/static/common/header.html?v=6');
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
        // Highlight mobile link too
        if (link.classList.contains('nav-mobile-link')) {
          link.classList.add('active');
        }
      }
    });
    if (typeof updateStorageModeButton === 'function') {
      updateStorageModeButton();
    }
    initMobileMenu(container);
  } catch (e) {
    // Fail silently to avoid breaking page load
  }
}

function initMobileMenu(container) {
  const hamburger = container.querySelector('#nav-hamburger');
  const mobileMenu = container.querySelector('#nav-mobile-menu');
  if (!hamburger || !mobileMenu) return;

  hamburger.addEventListener('click', function () {
    const isOpen = mobileMenu.classList.contains('is-open');
    if (isOpen) {
      closeMobileMenu(hamburger, mobileMenu);
    } else {
      openMobileMenu(hamburger, mobileMenu);
    }
  });

  // Close on clicking a link inside mobile menu
  mobileMenu.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', function () {
      closeMobileMenu(hamburger, mobileMenu);
    });
  });

  // Close on clicking outside
  document.addEventListener('click', function (e) {
    if (!mobileMenu.classList.contains('is-open')) return;
    if (!mobileMenu.contains(e.target) && !hamburger.contains(e.target)) {
      closeMobileMenu(hamburger, mobileMenu);
    }
  });

  // Sync mobile storage mode button with desktop one
  const desktopBtn = container.querySelector('#storage-mode-btn');
  const mobileBtn = container.querySelector('#storage-mode-btn-mobile');
  if (desktopBtn && mobileBtn) {
    var observer = new MutationObserver(function () {
      mobileBtn.textContent = desktopBtn.textContent;
      mobileBtn.className = desktopBtn.className;
    });
    observer.observe(desktopBtn, { childList: true, attributes: true, attributeFilter: ['class'] });
    // Initial sync
    mobileBtn.textContent = desktopBtn.textContent;
    mobileBtn.className = desktopBtn.className;
  }
}

function openMobileMenu(hamburger, mobileMenu) {
  mobileMenu.classList.add('is-open');
  hamburger.classList.add('is-open');
  hamburger.setAttribute('aria-expanded', 'true');
}

function closeMobileMenu(hamburger, mobileMenu) {
  mobileMenu.classList.remove('is-open');
  hamburger.classList.remove('is-open');
  hamburger.setAttribute('aria-expanded', 'false');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadAdminHeader);
} else {
  loadAdminHeader();
}
