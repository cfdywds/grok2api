/**
 * Copilot 图片助手 - 前端逻辑
 *
 * 功能：SSE 流式对话、会话管理、简易 Markdown 渲染、图片灯箱
 */

(function () {
  "use strict";

  // ==================== State ====================

  let currentSessionId = null;
  let isStreaming = false;

  // ==================== DOM ====================

  const sidebar = document.getElementById("sidebar");
  const toggleSidebarBtn = document.getElementById("toggleSidebar");
  const newSessionBtn = document.getElementById("newSessionBtn");
  const sessionListEl = document.getElementById("sessionList");
  const messagesArea = document.getElementById("messagesArea");
  const welcomeScreen = document.getElementById("welcomeScreen");
  const messagesList = document.getElementById("messagesList");
  const messageInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");

  // ==================== Auth ====================

  function getAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (typeof getApiKey === "function") {
      const key = getApiKey();
      if (key) headers["Authorization"] = `Bearer ${key}`;
    }
    return headers;
  }

  // ==================== Sidebar ====================

  toggleSidebarBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });

  // Mobile: start collapsed
  if (window.innerWidth <= 768) {
    sidebar.classList.add("collapsed");
  }

  // ==================== Sessions ====================

  async function loadSessions() {
    try {
      const res = await fetch("/v1/copilot/sessions", { headers: getAuthHeaders() });
      const data = await res.json();
      renderSessionList(data.sessions || []);
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  }

  function renderSessionList(sessions) {
    sessionListEl.innerHTML = "";
    if (sessions.length === 0) {
      sessionListEl.innerHTML =
        '<div class="text-xs text-[var(--accents-4)] text-center py-8">暂无对话记录</div>';
      return;
    }
    sessions.forEach((s) => {
      const item = document.createElement("div");
      item.className =
        "copilot-session-item" + (s.id === currentSessionId ? " active" : "");
      item.innerHTML = `
        <span class="copilot-session-title">${escapeHtml(s.title || "新对话")}</span>
        <button class="copilot-session-delete" title="删除">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      `;
      item.addEventListener("click", (e) => {
        if (e.target.closest(".copilot-session-delete")) return;
        switchSession(s.id);
      });
      item.querySelector(".copilot-session-delete").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteSession(s.id);
      });
      sessionListEl.appendChild(item);
    });
  }

  async function switchSession(sessionId) {
    if (isStreaming) return;
    currentSessionId = sessionId;
    try {
      const res = await fetch(`/v1/copilot/sessions/${sessionId}`, {
        headers: getAuthHeaders(),
      });
      const session = await res.json();
      renderMessages(session.messages || []);
      loadSessions(); // refresh active state
    } catch (e) {
      console.error("Failed to load session:", e);
      showToast("加载会话失败", "error");
    }
  }

  async function deleteSession(sessionId) {
    if (typeof showConfirm === "function") {
      const ok = await showConfirm("确定删除这个对话吗？");
      if (!ok) return;
    }
    try {
      await fetch(`/v1/copilot/sessions/${sessionId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (currentSessionId === sessionId) {
        currentSessionId = null;
        showWelcome();
      }
      loadSessions();
      showToast("对话已删除", "success");
    } catch (e) {
      showToast("删除失败", "error");
    }
  }

  newSessionBtn.addEventListener("click", () => {
    if (isStreaming) return;
    currentSessionId = null;
    showWelcome();
  });

  // ==================== Messages ====================

  function showWelcome() {
    welcomeScreen.style.display = "flex";
    messagesList.style.display = "none";
    messagesList.innerHTML = "";
  }

  function showMessages() {
    welcomeScreen.style.display = "none";
    messagesList.style.display = "block";
  }

  function renderMessages(messages) {
    messagesList.innerHTML = "";
    showMessages();
    messages.forEach((msg) => {
      appendMessage(msg.role, msg.content, false);
    });
    scrollToBottom();
  }

  function appendMessage(role, content, animate = true) {
    showMessages();
    const msgEl = document.createElement("div");
    msgEl.className = `copilot-message ${role}`;

    const avatarLabel = role === "user" ? "你" : "AI";
    msgEl.innerHTML = `
      <div class="copilot-avatar">${avatarLabel}</div>
      <div class="copilot-bubble">${renderMarkdown(content)}</div>
    `;

    messagesList.appendChild(msgEl);
    if (animate) scrollToBottom();

    // Bind image lightbox
    msgEl.querySelectorAll(".copilot-bubble img").forEach((img) => {
      img.addEventListener("click", () => openLightbox(img.src));
    });

    return msgEl;
  }

  function createStreamingMessage() {
    showMessages();
    const msgEl = document.createElement("div");
    msgEl.className = "copilot-message assistant";
    msgEl.innerHTML = `
      <div class="copilot-avatar">AI</div>
      <div class="copilot-bubble">
        <div class="copilot-typing"><span></span><span></span><span></span></div>
      </div>
    `;
    messagesList.appendChild(msgEl);
    scrollToBottom();
    return msgEl;
  }

  function updateStreamingMessage(msgEl, content) {
    const bubble = msgEl.querySelector(".copilot-bubble");
    bubble.innerHTML = renderMarkdown(content);
    // Bind lightbox for newly rendered images
    bubble.querySelectorAll("img").forEach((img) => {
      img.addEventListener("click", () => openLightbox(img.src));
    });
    scrollToBottom();
  }

  function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  // ==================== Simple Markdown ====================

  function renderMarkdown(text) {
    if (!text) return "";
    // Escape HTML first
    let html = escapeHtml(text);
    // Images: ![alt](url)
    html = html.replace(
      /!\[([^\]]*)\]\(([^)]+)\)/g,
      '<img src="$2" alt="$1" loading="lazy">'
    );
    // Links: [text](url)
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener" style="color:var(--accents-6);text-decoration:underline;">$1</a>'
    );
    // Blockquote: > text
    html = html.replace(
      /^&gt; (.+)$/gm,
      "<blockquote>$1</blockquote>"
    );
    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic: *text*
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    // Line breaks
    html = html.replace(/\n/g, "<br>");
    // Merge consecutive blockquotes
    html = html.replace(/<\/blockquote><br><blockquote>/g, "<br>");
    return html;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ==================== Lightbox ====================

  function openLightbox(src) {
    const overlay = document.createElement("div");
    overlay.className = "copilot-lightbox";
    overlay.innerHTML = `<img src="${src}" alt="preview">`;
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.remove();
    });
    document.body.appendChild(overlay);
  }

  // ==================== Send Message ====================

  async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isStreaming) return;

    // Show user message
    appendMessage("user", text);
    messageInput.value = "";
    autoResize();
    updateSendBtn();

    // Create streaming assistant message
    const streamingEl = createStreamingMessage();
    isStreaming = true;
    sendBtn.disabled = true;

    let collected = "";

    try {
      const body = {
        model: "copilot",
        messages: [{ role: "user", content: text }],
        stream: true,
      };
      if (currentSessionId) body.session_id = currentSessionId;

      const res = await fetch("/v1/copilot/chat", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error?.message || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === "[DONE]") continue;

          try {
            const data = JSON.parse(dataStr);

            // Capture session_id from first chunk
            if (data.session_id && !currentSessionId) {
              currentSessionId = data.session_id;
            }

            const delta = data.choices?.[0]?.delta?.content;
            if (delta) {
              collected += delta;
              updateStreamingMessage(streamingEl, collected);
            }
          } catch (_) {
            // skip invalid JSON
          }
        }
      }
    } catch (e) {
      console.error("Send failed:", e);
      if (!collected) {
        updateStreamingMessage(streamingEl, `发送失败: ${e.message}`);
      }
      showToast(e.message, "error");
    } finally {
      isStreaming = false;
      sendBtn.disabled = false;
      updateSendBtn();
      loadSessions(); // refresh sidebar
    }
  }

  // ==================== Input ====================

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  messageInput.addEventListener("input", () => {
    autoResize();
    updateSendBtn();
  });

  sendBtn.addEventListener("click", sendMessage);

  function autoResize() {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
  }

  function updateSendBtn() {
    sendBtn.disabled = !messageInput.value.trim() || isStreaming;
  }

  // ==================== Example prompts ====================

  document.querySelectorAll(".copilot-example-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      messageInput.value = btn.dataset.prompt;
      autoResize();
      updateSendBtn();
      messageInput.focus();
    });
  });

  // ==================== Toast helper ====================

  function showToast(msg, type) {
    if (typeof window.showToast === "function") {
      window.showToast(msg, type);
    }
  }

  // ==================== Init ====================

  loadSessions();
})();
