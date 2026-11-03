// AIFLOW — shared reader controls. Keep storage keys compatible with existing readers.
(function () {
  const store = {
    get(key, fallback) { try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Session controls still work. */ } },
    setOf(key) { try { const a = JSON.parse(this.get(key, '[]')); return new Set(Array.isArray(a) ? a.filter(x => typeof x === 'string') : []); } catch (_) { return new Set(); } }
  };
  const media = matchMedia('(prefers-color-scheme: dark)');
  let mode = store.get('aiflow-theme', 'auto');
  function applyTheme() {
    document.documentElement.dataset.theme = mode === 'dark' || (mode === 'auto' && media.matches) ? 'dark' : 'light';
    document.querySelectorAll('[data-set-theme]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.setTheme === mode)));
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-set-theme]');
    if (!b) return;
    mode = b.dataset.setTheme; store.set('aiflow-theme', mode); applyTheme();
  });
  media.addEventListener('change', applyTheme); applyTheme();
  const favs = store.setOf('aiflow-favs');
  const read = store.setOf('aiflow-read');
  const input = document.querySelector('[data-search]');
  const items = [...document.querySelectorAll('[data-feed] .feed-item')];
  const groups = [...document.querySelectorAll('[data-day-group]')];
  const types = new Set(['all', ...items.map(el => el.dataset.type)]);
  const qualityInput = document.querySelector('[data-quality-filter]');
  let state, limit = 24;
  const texts = new Map(items.map(el => [el, el.textContent.toLocaleLowerCase()]));
  function fromURL() {
    const p = new URLSearchParams(location.search);
    const type = p.get('type') || location.hash.slice(1);
    state = { quality: ['primary','reported','unreviewed','lead'].includes(p.get('quality')) ? p.get('quality') : 'all', q: p.get('q') || '', type: types.has(type) ? type : 'all', saved: p.get('saved') === '1', unread: p.get('unread') === '1' };
    if (input) input.value = state.q; if (qualityInput) qualityInput.value = state.quality;
  }
  fromURL();
  let controls, status, more, clear, savedButton, unreadButton, empty;
  if (items.length) {
    document.querySelectorAll('[data-unread-toggle]').forEach(el => el.remove());
    controls = document.createElement('div'); controls.className = 'reader-controls';
    controls.innerHTML = '<div class="reader-toggles"><button type="button" data-saved-toggle aria-pressed="false">只看收藏</button><button type="button" data-unread-toggle aria-pressed="false">只看未读</button><button type="button" data-reset-filters>重置筛选</button></div><p class="reader-status" role="status" aria-live="polite"></p>';
    const first = groups[0] || document.querySelector('[data-feed]'); first.before(controls);
    status = controls.querySelector('.reader-status'); clear = controls.querySelector('[data-reset-filters]');
    savedButton = controls.querySelector('[data-saved-toggle]'); unreadButton = controls.querySelector('[data-unread-toggle]');
    empty = document.querySelector('[data-empty]');
    if (!empty) { empty = document.createElement('p'); empty.className = 'empty'; empty.dataset.empty = ''; (groups.at(-1) || document.querySelector('[data-feed]')).after(empty); }
    empty.textContent = '没有符合条件的记录。试试更换关键词，或重置筛选。';
    more = document.createElement('button'); more.type = 'button'; more.className = 'load-more'; more.textContent = '加载更多'; empty.after(more);
    more.addEventListener('click', () => {
      const old = new Set(items.filter(el => !el.hidden)); limit += 24; render(false);
      const next = items.find(el => !el.hidden && !old.has(el));
      if (next) next.querySelector('h3 a')?.focus({ preventScroll: true });
    });
    savedButton.addEventListener('click', () => { state.saved = !state.saved; refresh(); });
    unreadButton.addEventListener('click', () => { state.unread = !state.unread; refresh(); });
    clear.addEventListener('click', () => { state = { quality: 'all', q: '', type: 'all', saved: false, unread: false }; if (qualityInput) qualityInput.value = 'all'; if (input) input.value = ''; refresh(); });
    items.forEach(el => {
      const card = el.querySelector('.card'); if (!card) return;
      const extras = [...card.querySelectorAll(':scope > .quote-box, :scope > .card-foot')];
      if (!extras.length) return;
      const details = document.createElement('details'); details.className = 'card-extra';
      const summary = document.createElement('summary'); summary.textContent = '摘录与推荐理由'; details.append(summary);
      extras.forEach(extra => details.append(extra)); card.append(details);
    });
  }
  function syncURL() {
    const url = new URL(location.href);
    for (const [key, value] of Object.entries(state)) {
      const active = value && value !== 'all';
      if (active) url.searchParams.set(key, value === true ? '1' : value); else url.searchParams.delete(key);
    }
    if (types.has(url.hash.slice(1))) url.hash = '';
    history.replaceState(null, '', url);
  }
  function paintFavorites() {
    document.querySelectorAll('[data-fav]').forEach(btn => {
      const on = favs.has(btn.dataset.fav); btn.classList.toggle('on', on);
      btn.setAttribute('aria-pressed', String(on)); btn.setAttribute('aria-label', on ? '取消收藏' : '收藏'); if (btn.classList.contains('save-text')) btn.textContent = on ? '已收藏 · 点击取消' : '收藏这条记录';
    });
  }
  function render(updateURL = true) {
    paintFavorites(); if (!items.length) return;
    const q = state.q.trim().toLocaleLowerCase(); let matches = 0;
    items.forEach(el => {
      const id = el.dataset.id;
      const hit = (state.quality === 'all' || el.dataset.quality === state.quality) && (!q || texts.get(el).includes(q)) && (state.type === 'all' || el.dataset.type === state.type) && (!state.saved || favs.has(id)) && (!state.unread || !read.has(id));
      el.classList.toggle('is-unread', !read.has(id));
      el.hidden = !hit || ++matches > limit;
    });
    groups.forEach(g => {
      const visible = [...g.querySelectorAll('.feed-item')].filter(el => !el.hidden).length;
      g.hidden = !visible; const count = g.querySelector('.daybar .count'); if (count) count.textContent = visible + ' 条';
    });
    empty.hidden = matches > 0; more.hidden = matches <= limit;
    more.textContent = '加载更多 · 还有 ' + Math.max(0, matches - limit) + ' 条';
    status.textContent = matches > limit ? '已显示 ' + limit + ' / ' + matches + ' 条' : '共 ' + matches + ' 条记录';
    savedButton.setAttribute('aria-pressed', String(state.saved)); unreadButton.setAttribute('aria-pressed', String(state.unread));
    const filtered = !!(q || state.saved || state.unread || state.type !== 'all' || state.quality !== 'all');
    clear.hidden = !filtered;
    document.querySelectorAll('.hot-card').forEach(el => el.hidden = filtered);
    document.querySelectorAll('[data-filter-type]').forEach(b => {
      const active = b.dataset.filterType === state.type;
      b.classList.toggle('is-active', active); b.setAttribute('aria-pressed', String(active));
    });
    if (updateURL) syncURL();
  }
  function refresh() { limit = 24; render(); }
  qualityInput?.addEventListener('change', () => { state.quality = qualityInput.value; refresh(); });
  input?.addEventListener('input', () => { state.q = input.value; refresh(); });
  document.addEventListener('keydown', e => {
    if (!input || e.isComposing) return;
    const editing = e.target.closest('input, textarea, select, [contenteditable="true"]');
    if (((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') || (e.key === '/' && !editing && !e.metaKey && !e.ctrlKey && !e.altKey)) {
      e.preventDefault(); input.focus();
    }
  });
  document.addEventListener('click', e => {
    const type = e.target.closest('[data-filter-type]');
    if (type) { state.type = type.dataset.filterType; refresh(); }
    const fav = e.target.closest('[data-fav]');
    if (fav) {
      e.preventDefault(); const id = fav.dataset.fav;
      favs.has(id) ? favs.delete(id) : favs.add(id);
      store.set('aiflow-favs', JSON.stringify([...favs])); render(false);
      document.dispatchEvent(new CustomEvent('aiflow:favs'));
    }
    const link = e.target.closest('.feed-item h3 a');
    if (link) { read.add(link.closest('.feed-item').dataset.id); store.set('aiflow-read', JSON.stringify([...read])); }
  });
  window.addEventListener('popstate', () => { fromURL(); refresh(); });
  function syncStoredLists() {
    for (const [key, set] of [['aiflow-read', read], ['aiflow-favs', favs]]) {
      try { const data = JSON.parse(store.get(key, 'null')); if (Array.isArray(data)) { set.clear(); data.filter(x => typeof x === 'string').forEach(x => set.add(x)); } } catch (_) {}
    }
    render(false);
  }
  window.addEventListener('pageshow', syncStoredLists);
  window.addEventListener('storage', e => { if (e.key === 'aiflow-read' || e.key === 'aiflow-favs') syncStoredLists(); });
  render(false);
})();

/* Random archive: reviewed talent stories only, with original publication dates. */
(function () {
  const out = document.getElementById('rr-out'); if (!out) return;
  const button = document.querySelector('[data-rr-roll]');
  const label = document.querySelector('[data-rr-label]');
  const count = document.querySelector('[data-rr-count]');
  let lastId, pool = [];
  const esc = s => String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  button.addEventListener('click', () => {
    const candidates = pool.filter(x => x.id !== lastId); const choices = candidates.length ? candidates : pool;
    if (!choices.length) return;
    const x = choices[Math.floor(Math.random() * choices.length)]; lastId = x.id;
    out.innerHTML = '<article class="rr-card"><div class="rr-card-meta"><span>'+esc(x.type)+'</span><span>'+esc(x.company)+'</span><time>'+esc(x.date)+'</time><span>'+esc(x.conf)+'</span></div><h2 class="rr-card-title"><a href="'+esc(x.url)+'">'+esc(x.title)+'</a></h2><p class="rr-card-reason">'+esc(x.summary)+'</p><div class="rr-card-foot"><a href="'+esc(x.url)+'">查看原始来源 →</a></div></article>';
    label.textContent = '再回顾一条';
  });
  fetch('assets/data/random.json').then(r => { if (!r.ok) throw Error('Unavailable'); return r.json(); }).then(data => {
    pool = Array.isArray(data) ? data : [];
    count.textContent = pool.length + ' 条已核对人才记录'; button.disabled = !pool.length;
    label.textContent = pool.length ? '随机回顾一条' : '暂无已核对记录';
  }).catch(() => { label.textContent = '加载未完成'; count.textContent = '请刷新重试，或从资料库继续阅读。'; });
})();
