// AIFLOW — 交互：主题、搜索、标记已读、收藏
(function () {
  const root = document.documentElement;
  const THEME_KEY = 'aiflow-theme';

  /* ---------- 主题 ---------- */
  function applyTheme(mode) {
    const dark = mode === 'dark' || (mode === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    root.dataset.theme = dark ? 'dark' : 'light';
    document.querySelectorAll('[data-set-theme]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.setTheme === mode));
    });
  }
  const saved = localStorage.getItem(THEME_KEY) || 'auto';
  applyTheme(saved);
  document.addEventListener('click', function (e) {
    const b = e.target.closest('[data-set-theme]');
    if (!b) return;
    localStorage.setItem(THEME_KEY, b.dataset.setTheme);
    applyTheme(b.dataset.setTheme);
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if ((localStorage.getItem(THEME_KEY) || 'auto') === 'auto') applyTheme('auto');
  });

  /* ---------- 搜索 ---------- */
  const input = document.querySelector('[data-search]');
  const hasFeed = !!document.querySelector('[data-feed]');
  function filterFeed(q) {
    if (!hasFeed) return;
    q = q.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll('[data-feed] .feed-item').forEach(function (el) {
      const hit = !q || el.textContent.toLowerCase().includes(q);
      el.hidden = !hit;
      if (hit) shown++;
    });
    document.querySelectorAll('[data-day-group]').forEach(function (g) {
      const any = [...g.querySelectorAll('.feed-item')].some(function (el) { return !el.hidden; });
      g.hidden = !any;
    });
    const empty = document.querySelector('[data-empty]');
    if (empty) empty.hidden = shown > 0;
  }
  if (input) {
    input.addEventListener('input', function () { filterFeed(input.value); });
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); input.focus();
      } else if (e.key === '/' && document.activeElement !== input) {
        e.preventDefault(); input.focus();
      }
    });
  }

  /* ---------- 类型筛选（全部动态） ---------- */
  document.addEventListener('click', function (e) {
    const t = e.target.closest('[data-filter-type]');
    if (!t) return;
    e.preventDefault();
    const type = t.dataset.filterType;
    document.querySelectorAll('[data-filter-type]').forEach(function (a) {
      a.classList.toggle('is-active', a === t);
    });
    let firstShown = null;
    document.querySelectorAll('[data-feed] .feed-item').forEach(function (el) {
      const show = type === 'all' || el.dataset.type === type;
      el.hidden = !show;
      if (show) {
        el.classList.remove('is-fade');
        void el.offsetWidth;
        el.classList.add('is-fade');
        if (!firstShown) firstShown = el;
      }
    });
    document.querySelectorAll('[data-day-group]').forEach(function (g) {
      const n = [...g.querySelectorAll('.feed-item')].filter(function (el) { return !el.hidden; }).length;
      g.hidden = n === 0;
      const c = g.querySelector('.daybar .count');
      if (c) c.textContent = n + ' 条';
    });
    const total = document.querySelectorAll('[data-feed] .feed-item:not([hidden])').length;
    const empty = document.querySelector('[data-empty]');
    if (empty) empty.hidden = total > 0;
    history.replaceState(null, '', type === 'all' ? location.pathname : '#' + type);
    if (firstShown) {
      const y = firstShown.getBoundingClientRect().top + window.scrollY - 96;
      window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
    }
  });

  /* ---------- 收藏 ---------- */
  const FAV_KEY = 'aiflow-favs';
  const favs = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]'));
  document.querySelectorAll('[data-fav]').forEach(function (btn) {
    const id = btn.dataset.fav;
    if (favs.has(id)) { btn.classList.add('on'); btn.setAttribute('aria-pressed', 'true'); }
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      if (favs.has(id)) { favs.delete(id); btn.classList.remove('on'); btn.setAttribute('aria-pressed', 'false'); }
      else { favs.add(id); btn.classList.add('on'); btn.setAttribute('aria-pressed', 'true'); }
      localStorage.setItem(FAV_KEY, JSON.stringify([...favs]));
      document.dispatchEvent(new CustomEvent('aiflow:favs'));
    });
  });

  /* ---------- 只看未读 ---------- */
  const READ_KEY = 'aiflow-read';
  const read = new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]'));
  let unreadOnly = false;
  function paintUnread() {
    if (!hasFeed) return;
    document.querySelectorAll('[data-feed] .feed-item').forEach(function (el) {
      const id = el.dataset.id;
      el.classList.toggle('is-unread', !read.has(id));
      if (unreadOnly) el.hidden = read.has(id);
    });
    if (unreadOnly) {
      document.querySelectorAll('[data-day-group]').forEach(function (g) {
        g.hidden = ![...g.querySelectorAll('.feed-item')].some(function (el) { return !el.hidden; });
      });
    }
  }
  document.querySelectorAll('[data-unread-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      unreadOnly = !unreadOnly;
      btn.setAttribute('aria-pressed', String(unreadOnly));
      paintUnread();
    });
  });
  if (hasFeed) {
    paintUnread();
    document.addEventListener('click', function (e) {
      const a = e.target.closest('a[href]');
      if (!a) return;
      const el = a.closest('.feed-item');
      if (!el) return;
      read.add(el.dataset.id);
      localStorage.setItem(READ_KEY, JSON.stringify([...read]));
      paintUnread();
    });
  }

  /* ---------- 初始 hash 筛选 ---------- */
  const h = location.hash.replace('#', '');
  if (h && document.querySelector('[data-filter-type="' + h + '"]')) {
    document.querySelector('[data-filter-type="' + h + '"]').click();
  }
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
    var now = new Date();
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
      document.querySelector('[data-rr-roll]').disabled = true;
      return;
    }

    function pick() {
      var c = pool.filter(function (x) { return x.id !== lastId; });
      if (!c.length) c = pool;
      return c[Math.floor(Math.random() * c.length)];
    }

    function render(x) {
      lastId = x.id;
      var week = isoWeek(mon);
      out.innerHTML = '<article class="rr-card is-pop">' +
        '<div class="rr-card-meta"><span class="rr-type">' + esc(x.type) + '</span>' +
        '<span class="rr-co">' + esc(x.company) + '</span>' +
        '<span class="mono">' + esc(x.date.slice(5).replace('-', '/')) + '</span>' +
        '<span class="rr-conf">' + esc(x.conf) + '</span></div>' +
        '<h2 class="rr-card-title"><a href="' + esc(x.url) + '">' + esc(x.title) + '</a></h2>' +
        (x.rumor ? '<div class="rr-rumor-note">⚠ 小道消息 · ' + esc(x.rst) + ' · 来自 ' + esc(x.rs) + '，未经证实，请当线索看</div>' : '') +
        (x.reason ? '<p class="rr-card-reason">' + esc(x.reason) + '</p>' : '') +
        '<div class="rr-card-foot"><span class="muted">本周共 ' + pool.length + ' 条 · 再按一次换一条</span>' +
        '<a class="rr-link" href="weekly/' + mon.getFullYear() + '-W' + String(week).padStart(2, '0') + '.html">看本周全貌 →</a></div>' +
        '</article>';
      labelEl.textContent = '再抽一条';
    }

    document.addEventListener('click', function (e) {
      if (e.target.closest('[data-rr-roll]')) render(pick());
    });
  }

  fetch('assets/data/random.json')
    .then(function (r) { return r.json(); })
    .then(start)
    .catch(function () { if (countEl) countEl.textContent = '数据加载失败，刷新试试'; });
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
