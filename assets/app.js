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
  let state, limit = 24;
  const texts = new Map(items.map(el => [el, el.textContent.toLocaleLowerCase()]));
  function fromURL() {
    const p = new URLSearchParams(location.search);
    const type = p.get('type') || location.hash.slice(1);
    state = { q: p.get('q') || '', type: types.has(type) ? type : 'all', saved: p.get('saved') === '1', unread: p.get('unread') === '1' };
    if (input) input.value = state.q;
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
    clear.addEventListener('click', () => { state = { q: '', type: 'all', saved: false, unread: false }; if (input) input.value = ''; refresh(); });
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
      btn.setAttribute('aria-pressed', String(on)); btn.setAttribute('aria-label', on ? '取消收藏' : '收藏');
    });
  }
  function render(updateURL = true) {
    paintFavorites(); if (!items.length) return;
    const q = state.q.trim().toLocaleLowerCase(); let matches = 0;
    items.forEach(el => {
      const id = el.dataset.id;
      const hit = (!q || texts.get(el).includes(q)) && (state.type === 'all' || el.dataset.type === state.type) && (!state.saved || favs.has(id)) && (!state.unread || !read.has(id));
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
    const filtered = !!(q || state.saved || state.unread || state.type !== 'all');
    clear.hidden = !filtered;
    document.querySelectorAll('.hot-card').forEach(el => el.hidden = filtered);
    document.querySelectorAll('[data-filter-type]').forEach(b => {
      const active = b.dataset.filterType === state.type;
      b.classList.toggle('is-active', active); b.setAttribute('aria-pressed', String(active));
    });
    if (updateURL) syncURL();
  }
  function refresh() { limit = 24; render(); }
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
  window.addEventListener('pageshow', () => {
    store.setOf('aiflow-read').forEach(id => read.add(id)); render(false);
  });
  render(false);
})();

/* ---------- 随机周报（一次一条） ---------- */
(function () {
  var out = document.getElementById('rr-out');
  if (!out) return;
  var rangeEl = document.querySelector('[data-week-range]');
  var countEl = document.querySelector('[data-rr-count]');
  var labelEl = document.querySelector('[data-rr-label]');
  var lastId = null;

  function weekRange(now) {
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var dow = (d.getDay() + 6) % 7;
    var mon = new Date(d); mon.setDate(d.getDate() - dow);
    var sun = new Date(mon); sun.setDate(mon.getDate() + 6); sun.setHours(23, 59, 59, 999);
    return [mon, sun];
  }
  function fmt(d) { return (d.getMonth() + 1) + '月' + d.getDate() + '日'; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var dn = (t.getUTCDay() + 6) % 7;
    t.setUTCDate(t.getUTCDate() - dn + 3);
    var ft = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
    var fn = (ft.getUTCDay() + 6) % 7;
    ft.setUTCDate(ft.getUTCDate() - fn + 3);
    return 1 + Math.round((t - ft) / (7 * 24 * 3600 * 1000));
  }

  function start(ALL) {
    var parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric', day: 'numeric' }).formatToParts(new Date());
    var date = Object.fromEntries(parts.map(p => [p.type, p.value]));
    var now = new Date(Number(date.year), Number(date.month) - 1, Number(date.day));
    var range = weekRange(now);
    var mon = range[0], sun = range[1];
    var pool = ALL.filter(function (x) {
      var t = new Date(x.date + 'T12:00:00');
      return t >= mon && t <= sun;
    });
    if (rangeEl) rangeEl.textContent = fmt(mon) + ' – ' + fmt(sun);
    var rumorCount = pool.filter(function (x) { return x.rumor; }).length;
    if (countEl) countEl.textContent = pool.length
      ? '本周共 ' + pool.length + ' 条记录' + (rumorCount ? '（含 ' + rumorCount + ' 条小道消息）' : '') + '，闭眼按一下'
      : '本周窗口（' + fmt(mon) + ' – ' + fmt(sun) + '）还没有记录';

    if (!pool.length) {
      labelEl.textContent = '本周暂无';
      out.innerHTML = '<p class="empty">本周还没有记录。<a href="weekly.html">浏览往期周报 →</a></p>';
      document.querySelector('[data-rr-roll]').disabled = true;
      return;
    }

    document.querySelector('[data-rr-roll]').disabled = false;
    labelEl.textContent = '随机一条';
    function pick() {
      var c = pool.filter(function (x) { return x.id !== lastId; });
      if (!c.length) c = pool;
      return c[Math.floor(Math.random() * c.length)];
    }

    function render(x) {
      lastId = x.id;
      var week = isoWeek(mon);
      var thursday = new Date(mon); thursday.setDate(mon.getDate() + 3);
      out.innerHTML = '<article class="rr-card is-pop">' +
        '<div class="rr-card-meta"><span class="rr-type">' + esc(x.type) + '</span>' +
        '<span class="rr-co">' + esc(x.company) + '</span>' +
        '<span class="mono">' + esc(x.date.slice(5).replace('-', '/')) + '</span>' +
        '<span class="rr-conf">' + esc(x.conf) + '</span></div>' +
        '<h2 class="rr-card-title"><a href="' + esc(x.url) + '">' + esc(x.title) + '</a></h2>' +
        (x.rumor ? '<div class="rr-rumor-note">⚠ 小道消息 · ' + esc(x.rst) + ' · 来自 ' + esc(x.rs) + '，未经证实，请当线索看</div>' : '') +
        (x.reason ? '<p class="rr-card-reason">' + esc(x.reason) + '</p>' : '') +
        '<div class="rr-card-foot"><span class="muted">本周共 ' + pool.length + ' 条 · 再按一次换一条</span>' +
        '<a class="rr-link" href="weekly/' + thursday.getFullYear() + '-W' + String(week).padStart(2, '0') + '.html">看本周全貌 →</a></div>' +
        '</article>';
      labelEl.textContent = '再抽一条';
    }

    document.addEventListener('click', function (e) {
      if (e.target.closest('[data-rr-roll]')) render(pick());
    });
  }

  fetch('assets/data/random.json')
    .then(function (r) { if (!r.ok) throw new Error('Unavailable'); return r.json(); })
    .then(start)
    .catch(function () { if (countEl) countEl.textContent = '数据暂时无法加载，请刷新重试。'; labelEl.textContent = '暂不可用'; out.innerHTML = '<p class="empty"><a href="weekly.html">先浏览往期周报 →</a></p>'; });
})();

/* ---------- 日历 ---------- */
(function () {
  var el = document.getElementById('cal-data');
  if (!el) return;
  var DATA = JSON.parse(el.textContent);
  var grid = document.querySelector('[data-cal-grid]');
  var title = document.querySelector('[data-cal-title]');
  var list = document.querySelector('[data-cal-list]');
  var dates = Object.keys(DATA).sort();
  var today = new Date();
  var todayIso = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
  var view = dates.length ? new Date(dates[dates.length - 1] + 'T12:00:00') : new Date();
  view = new Date(view.getFullYear(), view.getMonth(), 1);

  function weekStart(d) {
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var dow = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - dow);
    return x;
  }
  function fmt(d) { return (d.getMonth() + 1) + '月' + d.getDate() + '日'; }

  function render() {
    var y = view.getFullYear(), m = view.getMonth();
    title.textContent = y + ' 年 ' + (m + 1) + ' 月';
    var first = new Date(y, m, 1);
    var offset = (first.getDay() + 6) % 7;
    var days = new Date(y, m + 1, 0).getDate();
    var ws = weekStart(today), we = new Date(ws); we.setDate(ws.getDate() + 6);
    var html = '';
    for (var i = 0; i < offset; i++) html += '<span class="cal-cell is-empty"></span>';
    for (var d = 1; d <= days; d++) {
      var dt = new Date(y, m, d);
      var key = y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var rec = DATA[key];
      var cls = 'cal-cell';
      if (rec) cls += ' has';
      if (dt >= ws && dt <= we) cls += ' is-week';
      if (key === todayIso) cls += ' is-today';
      html += '<button class="' + cls + '" type="button" data-date="' + key + '"' + (rec ? '' : ' disabled') + '>' +
        '<span class="cal-d">' + d + '</span>' +
        (rec ? '<i class="cal-dot"></i>' : '') + '</button>';
    }
    grid.innerHTML = html;
    // 当月有记录的日期列表
    var rows = dates.filter(function (k) { return k.indexOf(y + '-' + String(m + 1).padStart(2, '0')) === 0; });
    list.innerHTML = rows.length ? '<h3>' + (m + 1) + ' 月记录</h3>' + rows.map(function (k) {
      var r = DATA[k];
      return '<a class="cal-row" href="daily/' + k + '.html"><span class="mono">' + k.slice(5).replace('-', '/') + '</span>' +
        '<span class="cal-row-n">' + r.n + ' 条</span><span class="cal-row-t">' + r.top.replace(/[&<>"]/g, '') + '</span></a>';
    }).join('') : '<p class="muted" style="text-align:center">这个月没有记录</p>';
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-date]');
    if (b && !b.disabled) { location.href = 'daily/' + b.dataset.date + '.html'; return; }
    if (e.target.closest('[data-cal-prev]')) { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); }
    if (e.target.closest('[data-cal-next]')) { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); }
    if (e.target.closest('[data-cal-today]')) {
      view = new Date(today.getFullYear(), today.getMonth(), 1); render();
    }
  });
  render();
})();

/* ---------- 右上角迷你日历 ---------- */
(function () {
  var dataEl = document.getElementById('cal-days');
  var pop = document.querySelector('[data-cal-pop]');
  var trigger = document.querySelector('[data-cal-toggle]');
  if (!dataEl || !pop || !trigger) return;
  var DATA = JSON.parse(dataEl.textContent);
  var grid = pop.querySelector('[data-cal-grid]');
  var title = pop.querySelector('[data-cal-title]');
  var detail = pop.querySelector('[data-cal-detail]');
  var today = new Date();
  var todayIso = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
  var view = new Date(today.getFullYear(), today.getMonth(), 1);
  var selected = todayIso;

  function fmt(d) { return (d.getMonth() + 1) + '月' + d.getDate() + '日'; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function renderDetail(iso) {
    var list = DATA[iso] || [];
    if (!list.length) {
      detail.innerHTML = '<p class="muted">' + fmt(new Date(iso + 'T12:00:00')) + ' 没有记录</p>';
      return;
    }
    detail.innerHTML = '<div class="cal-pop-dt">' + fmt(new Date(iso + 'T12:00:00')) + ' · ' + list.length + ' 条</div>' +
      list.slice(0, 4).map(function (x) {
        return '<a class="cal-pop-item" href="' + esc(x.u) + '"><span class="t">' + esc(x.t) + '</span><span class="c">' + esc(x.c) + '</span></a>';
      }).join('') +
      '<a class="cal-pop-more" href="daily/' + iso + '.html">查看当日快照 →</a>';
  }
  function render() {
    var y = view.getFullYear(), m = view.getMonth();
    title.textContent = y + ' 年 ' + (m + 1) + ' 月';
    var first = new Date(y, m, 1);
    var offset = (first.getDay() + 6) % 7;
    var days = new Date(y, m + 1, 0).getDate();
    var html = '';
    for (var i = 0; i < offset; i++) html += '<span class="cal-pop-cell is-empty"></span>';
    for (var d = 1; d <= days; d++) {
      var iso = y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var has = !!DATA[iso];
      var cls = 'cal-pop-cell';
      if (has) cls += ' has';
      if (iso === todayIso) cls += ' is-today';
      if (iso === selected) cls += ' is-sel';
      html += '<button class="' + cls + '" type="button" data-cd="' + iso + '">' + d + '</button>';
    }
    grid.innerHTML = html;
    renderDetail(selected);
    // 如果选中日不在当前视图，详情仍显示
  }
  function toggle(open) {
    var show = open == null ? pop.hidden : open;
    pop.hidden = !show;
    trigger.setAttribute('aria-expanded', String(show));
    if (show) render();
  }
  trigger.addEventListener('click', function (e) { e.stopPropagation(); toggle(); });
  pop.addEventListener('click', function (e) {
    e.stopPropagation();
    var cell = e.target.closest('[data-cd]');
    if (cell) { selected = cell.dataset.cd; render(); return; }
    if (e.target.closest('[data-cal-prev]')) { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); }
    if (e.target.closest('[data-cal-next]')) { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); }
  });
  document.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') toggle(false); });
  var jump = document.querySelector('[data-cal-jump]');
  if (jump) jump.addEventListener('click', function (e) {
    e.preventDefault();
    if (location.pathname.endsWith('index.html') || location.pathname === '/') toggle(true);
    else location.href = 'index.html';
  });
})();
