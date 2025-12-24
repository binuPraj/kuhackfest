/* Chatbot js file */
(function () {
  const els = {
    chat: document.getElementById('chat'),
    typing: document.getElementById('typing'),
    composer: document.getElementById('composer'),
    input: document.getElementById('message'),
    send: document.getElementById('send'),
    themeToggle: document.getElementById('themeToggle'),
    clearChat: document.getElementById('clearChat'),
    html: document.documentElement,
  };

  const STORAGE_KEYS = {
    THEME: 'standalone-chat-theme',
    MESSAGES: 'standalone-chat-messages',
  };

  const state = {
    messages: [], // { id, role: 'user'|'assistant', text, ts }
    busy: false,
  };

  // Utils
  const uid = () => Math.random().toString(36).slice(2, 9);
  const now = () => new Date();
  const fmtTime = (d) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  function saveMessages() {
    try { localStorage.setItem(STORAGE_KEYS.MESSAGES, JSON.stringify(state.messages)); } catch {}
  }
  function loadMessages() {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.MESSAGES);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function applyTheme(t) {
    if (t === 'light' || t === 'dark') {
      els.html.setAttribute('data-theme', t);
      try { localStorage.setItem(STORAGE_KEYS.THEME, t); } catch {}
      els.themeToggle.querySelector('.icon').textContent = t === 'dark' ? '🌙' : '☀️';
    } else {
      els.html.setAttribute('data-theme', 'auto');
      els.themeToggle.querySelector('.icon').textContent = '🌙';
    }
  }

  function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem(STORAGE_KEYS.THEME); } catch {}
    if (saved === 'light' || saved === 'dark') {
      applyTheme(saved);
      return;
    }
    applyTheme('auto');
  }

  function toggleTheme() {
    const cur = els.html.getAttribute('data-theme');
    if (cur === 'light') return applyTheme('dark');
    if (cur === 'dark') return applyTheme('light');
    // auto -> prefer dark if system is dark
    const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(prefersDark ? 'light' : 'dark');
  }

  function scrollToBottom() {
    els.chat.scrollTo({ top: els.chat.scrollHeight, behavior: 'smooth' });
  }

  function messageTemplate(msg) {
    const isUser = msg.role === 'user';
    const avatar = isUser ? '🧑' : '🤖';
    const classes = ['msg', isUser ? 'msg--user' : 'msg--bot'].join(' ');
    const ts = fmtTime(new Date(msg.ts));
    return `
      <article class="${classes}" data-id="${msg.id}" aria-label="${isUser ? 'User' : 'Assistant'} message">
        <div class="msg__avatar" aria-hidden="true">${avatar}</div>
        <div>
          <div class="msg__bubble">${escapeHtml(msg.text)}</div>
          <div class="msg__meta" aria-hidden="true">${isUser ? 'You' : 'Assistant'} • ${ts}</div>
        </div>
      </article>
    `;
  }

  function renderAll() {
    els.chat.innerHTML = state.messages.map(messageTemplate).join('');
    scrollToBottom();
  }

  function addMessage(role, text) {
    const msg = { id: uid(), role, text, ts: now().toISOString() };
    state.messages.push(msg);
    appendMessageEl(msg);
    saveMessages();
  }

  function appendMessageEl(msg) {
    const temp = document.createElement('div');
    temp.innerHTML = messageTemplate(msg).trim();
    const el = temp.firstElementChild;
    els.chat.appendChild(el);
    scrollToBottom();
  }

  function setTyping(on) {
    els.typing.classList.toggle('show', !!on);
    els.typing.setAttribute('aria-hidden', on ? 'false' : 'true');
  }

  // Mock assistant logic
  function replyFor(text) {
    const trimmed = text.trim();
    if (!trimmed) return "I didn't catch that. Could you rephrase?";
    if (/hello|hi|hey/i.test(trimmed)) return 'Hello! How can I help you today?';
    if (/time/i.test(trimmed)) return `The current time is ${fmtTime(new Date())}.`;
    if (/help|support/i.test(trimmed)) return 'Sure — tell me what you need help with.';
    return `You said: "${trimmed}"`;
  }

  function simulateAssistantResponse(userText) {
    state.busy = true;
    setTyping(true);
    els.input.setAttribute('disabled', 'true');
    els.send.setAttribute('disabled', 'true');

    const delay = Math.min(2000 + Math.random() * 1200, 3200);
    setTimeout(() => {
      const answer = replyFor(userText);
      addMessage('assistant', answer);
      setTyping(false);
      state.busy = false;
      els.input.removeAttribute('disabled');
      els.send.removeAttribute('disabled');
      els.input.focus();
    }, delay);
  }

  // Input autosize
  function autosize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  // HTML escaping to avoid injection in the simple template
  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Events
  els.composer.addEventListener('submit', (e) => {
    e.preventDefault();
    if (state.busy) return;
    const text = els.input.value.trim();
    if (!text) return;
    addMessage('user', text);
    els.input.value = '';
    autosize(els.input);
    simulateAssistantResponse(text);
  });

  els.input.addEventListener('input', () => autosize(els.input));

  // Enter to send, Shift+Enter for newline
  els.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      els.composer.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  });

  els.themeToggle.addEventListener('click', toggleTheme);

  els.clearChat.addEventListener('click', () => {
    if (!confirm('Clear the conversation?')) return;
    state.messages = [];
    saveMessages();
    renderAll();
    els.input.focus();
  });

  // Init
  initTheme();
  state.messages = loadMessages();
  if (state.messages.length === 0) {
    addMessage('assistant', 'Hi! I\'m your assistant. Ask me anything.');
  } else {
    renderAll();
  }
  autosize(els.input);
})();
