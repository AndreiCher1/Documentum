/* =========================================================================
   Documentum v2 — логика презентационного макета.
   Работает без бэкенда, на данных из demo-data.js.
   ========================================================================= */
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const icon = (name, cls = 'sm') => `<svg class="i ${cls}"><use href="#i-${name}"/></svg>`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const rub = (n) => n.toLocaleString('ru-RU') + ' ₽';
const mln = (n) => (n / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' млн ₽';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
};

function toast(msg, actionLabel, action) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<span>${esc(msg)}</span>` + (actionLabel ? `<button>${esc(actionLabel)}</button>` : '');
  if (actionLabel) el.querySelector('button').onclick = () => { action(); el.remove(); };
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* недоступно — не страшно */ } },
};

/* -------------------------------------------------------------------------
   Навигация
   ------------------------------------------------------------------------- */
function crumbs(parts) {
  $('#crumbs').innerHTML = parts.map((p, i) =>
    (i ? '<span class="sep">/</span>' : '') + (i === parts.length - 1 ? `<b>${esc(p)}</b>` : `<span>${esc(p)}</span>`)).join('');
}

function go(name) {
  $$('.screen').forEach((s) => s.classList.remove('active'));
  const railName = name === 'editor' || name === 'versions' ? 'registry' : name;
  $$('.rail [data-nav]').forEach((b) => b.classList.toggle('active', b.dataset.nav === railName));
  $(`#screen-${name}`).classList.add('active');
  // Экраны из screens.js рисуются при каждом открытии
  if (typeof SCREENS !== 'undefined' && SCREENS[name]) { SCREENS[name](); return; }
  if (name === 'editor') crumbs(ed.real ? ['Документы', ed.real.typeName, ed.real.title] : ['Документы', DEMO.contract.folder, DEMO.contract.title]);
  if (name === 'versions' && ed.real) { realVersions(); return; }
  if (name === 'assistant') crumbs(['Ассистент', chat.title || 'Новый вопрос']);
  if (name === 'versions') { crumbs(['Документы', DEMO.contract.title, 'История версий']); renderVersions(); }
}

document.addEventListener('click', (e) => {
  const nav = e.target.closest('[data-nav]');
  if (nav) { go(nav.dataset.nav); return; }
  if (e.target.closest('a[href="#"]')) e.preventDefault();
  const t = e.target.closest('[data-toast]');
  if (t) toast(t.dataset.toast);
});

/* -------------------------------------------------------------------------
   Тема
   ------------------------------------------------------------------------- */
function setTheme(t) { document.documentElement.dataset.theme = t; store.set('theme', t); }
setTheme(store.get('theme') || 'dark');
$('#theme-toggle').onclick = () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

/* =========================================================================
   РЕДАКТОР
   ========================================================================= */
const ed = {
  res: {},            // id находки → { status, html } — решения пользователя
  committed: new Set(),
  active: null,
  filter: 'all',
  showResolved: false,
  zoom: 1,
  version: 2,
};
const page = $('#page');
// Находки открытого документа: демо-договора или документа из базы (после проверки)
const FINDINGS = () => (ed.real ? ed.real.findings || [] : DEMO.findings);
const findingById = (id) => FINDINGS().find((f) => f.id === id);
const SEV_LABEL = { critical: 'Критично', warning: 'Замечание', info: 'Совет' };

function renderPage() {
  page.innerHTML = DEMO.contract.blocks.map((b) => {
    if (b.kind === 'h1') return `<h1 data-bid="${b.id}">${b.html}</h1>`;
    if (b.kind === 'h2') return `<h2 data-bid="${b.id}">${b.html}</h2>`;
    if (b.kind === 'meta') return `<p class="meta" data-bid="${b.id}">${b.html}</p>`;
    if (b.kind === 'req') return `<p class="req" data-bid="${b.id}">${b.html}</p>`;
    return `<p data-bid="${b.id}">${b.html}</p>`;
  }).join('');
  $('#doc-title').textContent = DEMO.contract.title;
}

const pending = () => FINDINGS().filter((f) => !ed.res[f.id]);
const markOf = (id) => page.querySelector(`[data-sid="${id}"]`);

function verdict() {
  const p = pending();
  if (p.some((f) => f.severity === 'critical')) return ['critical', 'Критично'];
  if (p.some((f) => f.severity === 'warning')) return ['warning', 'Есть замечания'];
  return ['ok', 'Готов'];
}

function renderLeft(tab = ed.leftTab || 'outline') {
  ed.leftTab = tab;
  $$('[data-ltab]').forEach((t) => t.classList.toggle('active', t.dataset.ltab === tab));
  if (ed.real) { realLeft(tab); return; }
  const body = $('#left-body');
  if (tab === 'outline') {
    const heads = DEMO.contract.blocks.filter((b) => b.kind === 'h1' || b.kind === 'h2');
    // Худшая несделанная находка в каждом разделе
    const sevOf = {};
    let current = null;
    for (const b of DEMO.contract.blocks) {
      if (b.kind === 'h1' || b.kind === 'h2') current = b.id;
      for (const f of pending()) if (f.block === b.id) {
        const rank = { critical: 3, warning: 2, info: 1 };
        if (!sevOf[current] || rank[f.severity] > rank[sevOf[current]]) sevOf[current] = f.severity;
      }
    }
    body.innerHTML = `<div class="outline">` + heads.map((h) => {
      const txt = h.html.replace(/<[^>]+>/g, '');
      const m = txt.match(/^(\d+)\.\s*(.*)$/);
      const label = m ? m[2].charAt(0) + m[2].slice(1).toLowerCase() : 'Договор поставки № 124-А';
      return `<button class="outline-item ${h.kind === 'h1' ? 'title' : ''}" data-go="${h.id}">
        <span class="n">${m ? m[1] : ''}</span>${esc(label)}${sevOf[h.id] ? `<span class="sev-dot ${sevOf[h.id]}"></span>` : ''}</button>`;
    }).join('') + `</div>`;
  } else {
    const fixed = (k) => (k === 'ИНН поставщика' && ed.res.f2?.status === 'accepted') || (k === 'Срок поставки' && ed.res.f3?.status === 'accepted');
    const val = (k, v) => k === 'ИНН поставщика' && fixed(k) ? '7725123450' : k === 'Срок поставки' && fixed(k) ? '30.09.2025' : v;
    body.innerHTML = `<div class="fields">` + DEMO.contract.fields.map(([k, v, bad]) =>
      `<div class="field"><div class="k">${k}</div><div class="v ${bad && !fixed(k) ? 'bad' : ''}">${esc(val(k, v))}</div></div>`).join('') +
      `</div><div class="label" style="padding:6px 16px">Связанные документы</div><div class="related">` +
      DEMO.contract.related.map(([t, ic]) => `<a href="#" data-toast="Откроется документ «${t}»">${icon(ic)}${esc(t)}</a>`).join('') + `</div>`;
  }
}
$$('[data-ltab]').forEach((t) => t.onclick = () => renderLeft(t.dataset.ltab));
$('#left-body').addEventListener('click', (e) => {
  const b = e.target.closest('[data-go]');
  if (b) scrollToBlock(b.dataset.go);
});

function scrollToBlock(bid, flash = true) {
  const el = page.querySelector(`[data-bid="${bid}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  if (flash) { el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }
}

function renderSummary() {
  const p = pending();
  const c = (s) => p.filter((f) => f.severity === s).length;
  const [vcls, vtxt] = verdict();
  const cats = ['all', ...new Set(FINDINGS().map((f) => f.category))];
  $('#review-summary').innerHTML = `
    <div class="verdict"><span class="verdict-badge ${vcls}">${vtxt}</span>
      <span class="counters"><span class="c-critical">Критично: <b>${c('critical')}</b></span>
      <span class="c-warning">Замечания: <b>${c('warning')}</b></span><span class="c-info">Советы: <b>${c('info')}</b></span></span></div>
    <div class="btn-row"><button class="btn small" id="accept-all" ${p.length ? '' : 'disabled'}>${icon('check')}Принять все</button>
      <button class="btn small" id="reject-all" ${p.length ? '' : 'disabled'}>Отклонить все</button></div>
    <div class="filters">${cats.map((k) => `<button class="chip ${ed.filter === k ? 'active' : ''}" data-filter="${k}">${k === 'all' ? 'Все' : k}</button>`).join('')}</div>`;
  $('#accept-all').onclick = () => bulk('accepted');
  $('#reject-all').onclick = () => bulk('rejected');
  $$('[data-filter]').forEach((b) => b.onclick = () => { ed.filter = b.dataset.filter; renderReview(); });

  const v = verdict();
  const pill = $('#doc-verdict');
  pill.className = 'status-pill ' + (v[0] === 'ok' ? '' : v[0]);
  pill.textContent = v[1];
}

function cardHTML(f) {
  const r = ed.res[f.id];
  const sevTag = `<span class="tag ${f.ai ? 'ai' : f.severity}"><span class="sev-dot ${f.severity}"></span>${SEV_LABEL[f.severity]} · ${f.category}${f.ai ? ' · ИИ' : ''}</span>`;
  const diff = f.noteOnly ? '' : `<div class="diff-line"><span class="was">${esc(f.before)}</span>${icon('arrow')}<span class="now">${esc(f.after)}</span></div>`;
  const src = f.source ? `<div class="card-source">${icon('file')}<span>${esc(f.source.text)} <a href="#" data-toast="Откроется «${esc(f.source.doc)}» рядом с договором">Открыть</a></span></div>` : '';
  const aiNote = f.ai ? `<div class="card-where" style="color:var(--ai)">Найдено языковой моделью — требует проверки человеком</div>` : '';
  let actions;
  if (r) {
    const txt = { accepted: ['ok', 'check', 'Принято'], rejected: ['critical', 'x', 'Отклонено'], ignored: ['info', 'check', 'Отмечено как просмотренное'] }[r.status];
    actions = `<div class="card-result tag ${txt[0]}">${icon(txt[1])}${txt[2]}${ed.committed.has(f.id) ? '' : `<button class="undo" data-undo="${f.id}">Вернуть</button>`}</div>`;
  } else if (f.noteOnly) {
    actions = `<div class="card-actions"><button class="btn small" data-goto="${f.id}">Перейти к месту</button><button class="btn small" data-act="ignored" data-id="${f.id}">Понятно</button></div>`;
  } else {
    actions = `<div class="card-actions"><button class="btn small" data-act="accepted" data-id="${f.id}">${icon('check')}Принять</button><button class="btn small" data-act="rejected" data-id="${f.id}">Отклонить</button></div>`;
  }
  return `<div class="card ${r ? 'resolved' : ''} ${ed.active === f.id ? 'active' : ''}" data-card="${f.id}">
    <div class="card-top">${sevTag}<span class="card-where">${f.where}</span></div>
    <div class="card-title">${esc(f.title)}</div>${diff}
    <div class="card-why">${esc(f.why)}</div>${src}${aiNote}${actions}</div>`;
}

function renderReview() {
  if (ed.real && !ed.real.findings) { realReview(); return; }   // документ из базы ещё не проверялся
  renderSummary();
  const list = FINDINGS().filter((f) => ed.filter === 'all' || f.category === ed.filter);
  const open = list.filter((f) => !ed.res[f.id]);
  const done = list.filter((f) => ed.res[f.id]);
  let html = open.map(cardHTML).join('');
  if (!open.length) html += `<div class="empty"><div class="big">${icon('check', '')}</div><b>Замечаний нет</b><span style="font-size:13px">Все находки разобраны. Последняя проверка — только что.</span></div>`;
  if (done.length) {
    html += `<button class="resolved-toggle" id="toggle-resolved">${ed.showResolved ? '▾' : '▸'} Решённые (${done.length})</button>`;
    if (ed.showResolved) html += done.map(cardHTML).join('');
  }
  $('#cards').innerHTML = html;
  const t = $('#toggle-resolved');
  if (t) t.onclick = () => { ed.showResolved = !ed.showResolved; renderReview(); };
  $('#cnt-review').textContent = pending().length;
  renderCommitBar();
  renderStatus();
  renderLeft();
}

$('#cards').addEventListener('click', (e) => {
  const act = e.target.closest('[data-act]');
  if (act) { resolve(act.dataset.id, act.dataset.act); return; }
  const undo = e.target.closest('[data-undo]');
  if (undo) { unresolve(undo.dataset.undo); return; }
  const gt = e.target.closest('[data-goto]');
  const card = e.target.closest('[data-card]');
  if (gt || (card && !card.classList.contains('resolved') && !e.target.closest('a'))) activate((gt || card).dataset.goto || card.dataset.card, true);
});
$('#cards').addEventListener('mouseover', (e) => {
  const card = e.target.closest('[data-card]');
  $$('.page .hover').forEach((m) => m.classList.remove('hover'));
  if (card) markOf(card.dataset.card)?.classList.add('hover');
});

function activate(id, scroll) {
  ed.active = id;
  $$('.page .active').forEach((m) => m.classList.remove('active'));
  const m = markOf(id);
  if (m) { m.classList.add('active'); if (scroll) m.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
  else if (scroll && findingById(id)?.block) scrollToBlock(findingById(id).block);   // замечание без пометки в тексте
  $$('.card').forEach((c) => c.classList.toggle('active', c.dataset.card === id));
  const card = $(`[data-card="${id}"]`);
  if (card && !scroll) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Клик и наведение на пометки в тексте связывают их с карточками
page.addEventListener('click', (e) => {
  const m = e.target.closest('[data-sid]');
  if (m) { switchRightTab('review'); activate(m.dataset.sid, false); }
});
page.addEventListener('mouseover', (e) => {
  const m = e.target.closest('[data-sid]');
  $$('.card.hover').forEach((c) => c.classList.remove('hover'));
  if (m) $(`[data-card="${m.dataset.sid}"]`)?.classList.add('hover');
});

function resolve(id, status) {
  const f = findingById(id);
  const m = markOf(id);
  if (!m && !f.noteOnly) return;
  // Замечание без пометки в тексте (например, «нет раздела») просто отмечаем решённым
  const html = m ? m.outerHTML : null;
  if (m) {
    const span = document.createElement('span');
    span.dataset.rid = id;
    if (f.noteOnly) span.append(...m.childNodes);
    else if (status === 'accepted') span.textContent = m.querySelector('ins')?.textContent || '';
    else { const d = m.querySelector('del'); if (d) span.append(...d.childNodes); }   // исходный текст с форматированием
    m.replaceWith(span);
  }
  ed.res[id] = { status, html };
  if (ed.active === id) ed.active = null;
  markSaved();
  renderReview();
  // Сразу переходим к следующей находке, как в ревью кода
  const next = pending().find((x) => ed.filter === 'all' || x.category === ed.filter);
  if (next) activate(next.id, false);
}

function unresolve(id) {
  const r = ed.res[id];
  if (!r) return;
  const span = page.querySelector(`[data-rid="${id}"]`);
  if (r.html && span) {
    const tmp = document.createElement('div');
    tmp.innerHTML = r.html;
    span.replaceWith(tmp.firstChild);
  }
  delete ed.res[id];
  if (ed.real) realOnInput();
  renderReview();
}

function bulk(status) {
  const list = pending().filter((f) => (ed.filter === 'all' || f.category === ed.filter) && !(status === 'accepted' && f.noteOnly));
  list.forEach((f) => resolve(f.id, f.noteOnly ? 'ignored' : status));
  toast(`${status === 'accepted' ? 'Принято' : 'Отклонено'}: ${list.length} ${plural(list.length, 'правка', 'правки', 'правок')}`, 'Отменить', () => { list.forEach((f) => unresolve(f.id)); });
}

function uncommitted() { return Object.keys(ed.res).filter((id) => !ed.committed.has(id)); }

function commitMessage(ids) {
  const acc = ids.filter((id) => ed.res[id].status === 'accepted').map((id) => { const t = findingById(id).title; return t.charAt(0).toLowerCase() + t.slice(1); });
  const rej = ids.filter((id) => ed.res[id].status === 'rejected').length;
  let msg = acc.length ? 'Исправлено: ' + acc.join('; ') + '.' : 'Разобраны замечания проверки.';
  if (rej) msg += ` Отклонено предложений: ${rej}.`;
  return msg;
}

function renderCommitBar() {
  if (ed.real) { realCommitBar(); return; }
  const ids = uncommitted();
  const bar = $('#commit-bar');
  bar.hidden = !ids.length;
  if (!ids.length) return;
  const acc = ids.filter((id) => ed.res[id].status === 'accepted').length;
  $('#commit-title').textContent = `Принято ${acc} из ${DEMO.findings.length} — сохранить как версию ${ed.version + 1}?`;
  if (!ed.msgEdited) $('#commit-msg').value = commitMessage(ids);
}
$('#commit-msg').addEventListener('input', () => { ed.msgEdited = true; });

$('#commit-btn').onclick = () => {
  if (ed.real) { realCommit(); return; }
  const ids = uncommitted();
  ed.version += 1;
  const now = new Date();
  DEMO.versions.forEach((v) => { v.current = false; });
  DEMO.versions.push({
    id: 'v' + ed.version, n: ed.version, name: 'Версия ' + ed.version, source: 'Принятые исправления', current: true,
    when: now.toLocaleDateString('ru-RU') + ', ' + now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
    desc: $('#commit-msg').value.trim() || commitMessage(ids), snapshot: snapshotPage(),
  });
  ids.forEach((id) => ed.committed.add(id));
  ed.msgEdited = false;
  $('#save-state').innerHTML = `${icon('check')}Сохранено · версия ${ed.version}`;
  renderReview();
  toast(`Сохранено как версия ${ed.version}`, 'Сравнить с прошлой', () => { cmp.a = 'v' + (ed.version - 1); cmp.b = 'v' + ed.version; go('versions'); });
};

function markSaved() {
  if (ed.real) { realOnInput(); return; }        // документ из базы — автосохранение черновика на сервер
  const s = $('#save-state');
  s.innerHTML = 'Сохраняется…';
  clearTimeout(ed.saveT);
  ed.saveT = setTimeout(() => { s.innerHTML = `${icon('check')}Сохранено · версия ${ed.version}`; }, 700);
}
page.addEventListener('input', () => { if (ed.real) realOnInput(); else markSaved(); renderStatus(); });

function renderStatus() {
  const words = (page.innerText.match(/\S+/g) || []).length;
  const p = pending().length;
  const mode = { markup: 'с правками', final: 'итог', original: 'оригинал' }[ed.view || 'markup'];
  $('#statusbar').innerHTML = `<span>Страница 1 из 2</span><span>${words} ${plural(words, 'слово', 'слова', 'слов')}</span>` +
    `<span class="${p ? 'warn' : ''}">${p ? `${p} ${plural(p, 'правка ожидает', 'правки ожидают', 'правок ожидают')} решения` : 'Все правки разобраны'}</span>` +
    `<span>Режим: ${mode}</span><span style="margin-left:auto">${Math.round(ed.zoom * 100)}%</span>`;
}

// Режим отображения правок
$$('#view-mode button').forEach((b) => b.onclick = () => {
  ed.view = b.dataset.view;
  $$('#view-mode button').forEach((x) => x.classList.toggle('on', x === b));
  page.classList.toggle('view-final', ed.view === 'final');
  page.classList.toggle('view-original', ed.view === 'original');
  renderStatus();
});

// Панель форматирования
$('#toolbar').addEventListener('mousedown', (e) => { if (e.target.closest('.tb-btn')) e.preventDefault(); });
$$('#toolbar [data-cmd]').forEach((el) => {
  const run = () => {
    page.focus();
    const cmd = el.dataset.cmd;
    const arg = el.tagName === 'SELECT' ? (cmd === 'formatBlock' ? `<${el.value}>` : el.value) : el.dataset.arg;
    document.execCommand(cmd, false, arg);
    markSaved();
    updateToolbarState();
  };
  if (el.tagName === 'SELECT') el.onchange = run; else el.onclick = run;
});
function updateToolbarState() {
  ['bold', 'italic', 'underline', 'strikeThrough', 'justifyLeft', 'justifyCenter', 'justifyFull'].forEach((c) => {
    const b = $(`#toolbar [data-cmd="${c}"]`);
    try { b.classList.toggle('on', document.queryCommandState(c)); } catch { /* нет выделения */ }
  });
}
document.addEventListener('selectionchange', () => { if (page.contains(document.getSelection().anchorNode)) updateToolbarState(); });

// Масштаб
function setZoom(z) {
  ed.zoom = Math.min(1.6, Math.max(0.6, Math.round(z * 10) / 10));
  $('#page-wrap').style.zoom = ed.zoom;
  $('#zoom-val').textContent = Math.round(ed.zoom * 100) + '%';
  renderStatus();
}
$('#zoom-in').onclick = () => setZoom(ed.zoom + 0.1);
$('#zoom-out').onclick = () => setZoom(ed.zoom - 0.1);

// Сворачивание боковых панелей
const screenEd = $('#screen-editor');
function syncPanels() {
  $('#expand-left').hidden = !screenEd.classList.contains('left-collapsed');
  $('#expand-right').hidden = !screenEd.classList.contains('right-collapsed');
}
$('#collapse-left').onclick = () => { screenEd.classList.add('left-collapsed'); syncPanels(); };
$('#expand-left').onclick = () => { screenEd.classList.remove('left-collapsed'); syncPanels(); };
$('#collapse-right').onclick = () => { screenEd.classList.add('right-collapsed'); syncPanels(); };
$('#expand-right').onclick = () => { screenEd.classList.remove('right-collapsed'); syncPanels(); };

// Повторная проверка — показывает этапы, как будет в рабочей версии
$('#run-check').onclick = async () => {
  if (ed.real) { realRunCheck(); return; }
  switchRightTab('review');
  const box = $('#review-summary');
  const stages = ['Правила: реквизиты, даты, суммы, нумерация', 'Сверка с базой: счета, приказы, справочник контрагентов', 'Смысловой анализ (языковая модель)'];
  for (let i = 0; i < stages.length; i++) {
    box.innerHTML = `<div class="steps">${stages.map((s, j) => `<div class="step ${j < i ? 'done' : ''}"><span class="spin"></span>${s}</div>`).join('')}</div>`;
    await sleep(650);
  }
  renderReview();
  toast(`Проверка завершена: ${pending().length} ${plural(pending().length, 'находка', 'находки', 'находок')}`);
};

/* ---------- Правая панель: вкладки, комментарии, вопросы к документу ---------- */
function switchRightTab(tab) {
  $$('[data-rtab]').forEach((t) => t.classList.toggle('active', t.dataset.rtab === tab));
  ['review', 'comments', 'ask'].forEach((t) => { $('#rtab-' + t).hidden = t !== tab; });
  if (screenEd.classList.contains('right-collapsed')) { screenEd.classList.remove('right-collapsed'); syncPanels(); }
}
$$('[data-rtab]').forEach((t) => t.onclick = () => switchRightTab(t.dataset.rtab));

function renderComments() {
  $('#comments').innerHTML = DEMO.comments.map((c, i) => `<div class="comment">
    <div class="who"><span class="avatar">${c.initials}</span>${esc(c.who)}<span class="faint" style="font-weight:400;font-size:12px;margin-left:auto">${c.time}</span></div>
    ${c.quote ? `<div class="quote">${esc(c.quote)}</div>` : ''}
    ${c.draft ? `<textarea style="padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg-input);height:60px;resize:none;outline:none" data-draft="${i}" placeholder="Текст комментария…"></textarea>
      <button class="btn small primary" data-save-comment="${i}">Добавить</button>` : `<div>${esc(c.text)}</div>`}</div>`).join('');
  $('#cnt-comments').textContent = DEMO.comments.filter((c) => !c.draft).length;
  const d = $('[data-draft]');
  if (d) d.focus();
}
$('#comments').addEventListener('click', (e) => {
  const b = e.target.closest('[data-save-comment]');
  if (!b) return;
  const i = +b.dataset.saveComment;
  const text = $(`[data-draft="${i}"]`).value.trim();
  if (!text) { DEMO.comments.splice(i, 1); } else { Object.assign(DEMO.comments[i], { text, draft: false }); }
  renderComments();
});
$('#add-comment').onclick = () => {
  const sel = document.getSelection();
  const quote = page.contains(sel.anchorNode) ? sel.toString().trim().slice(0, 120) : '';
  DEMO.comments.unshift({ who: 'Вы', initials: 'ВЫ', time: 'только что', quote, text: '', draft: true });
  switchRightTab('comments');
  renderComments();
};

function docAnswer(q) {
  const ql = q.toLowerCase();
  return DEMO.docQA.find((x) => x.keys.some((k) => ql.includes(k)));
}
async function askDoc(q) {
  if (!q.trim()) return;
  const msgs = $('#doc-msgs');
  msgs.insertAdjacentHTML('beforeend', `<div class="bubble user">${esc(q)}</div>`);
  const holder = document.createElement('div');
  holder.className = 'bubble bot';
  holder.innerHTML = `<div class="steps"><div class="step"><span class="spin"></span>Читаю документ…</div></div>`;
  msgs.appendChild(holder);
  holder.scrollIntoView({ block: 'end' });
  if (ed.real) { await askRealDoc(q, holder); return; }
  await sleep(900);
  const hit = docAnswer(q);
  if (!hit) {
    holder.textContent = 'В этом документе не нашёл ответа на вопрос. Попробуйте переформулировать или спросите ассистента по всей базе.';
    return;
  }
  holder.innerHTML = '';
  await typeInto(holder, hit.a, 12);
  holder.insertAdjacentHTML('beforeend', '<div>' + hit.cites.map(([t, bid]) => `<button class="cite" data-cite="${bid}">${icon('file')}${t}</button>`).join('') + '</div>');
}
// Вопрос по настоящему документу: сервер выбирает абзацы, модель отвечает, ссылки ведут к месту в тексте
async function askRealDoc(q, holder) {
  let res;
  try {
    if (isDirty()) await API.draft(ed.real.id, cleanHTML()).catch(() => {});
    res = await API.assistant(q, null, ed.real.id);
  } catch (e) {
    holder.textContent = 'Не удалось получить ответ: ' + e.message;
    return;
  }
  const src = Object.fromEntries((res.sources || []).map((s) => [s.n, s]));
  holder._src = src;
  holder.innerHTML = '';
  await typeInto(holder, (res.summary || '').replace(/\s*\[\d+\]/g, ''), 10);
  holder.innerHTML = esc(res.summary || '').replace(/\[(\d+)\]/g, (m, n) => (src[n] ? `<span class="ref" data-src="${n}">${n}</span>` : ''));
  if (res.sources?.length) {
    holder.insertAdjacentHTML('beforeend', '<div>' + res.sources.map((s) => `<button class="cite" data-src="${s.n}" title="${esc(s.quote)}">${icon('file')}${esc(s.quote.slice(0, 42))}${s.quote.length > 42 ? '…' : ''}</button>`).join('') + '</div>');
  }
  if (res.found) {
    holder.insertAdjacentHTML('beforeend', `<div class="faint" style="font-size:12px;margin-top:6px">${res.generated ? 'Ответ сформулирован языковой моделью по тексту документа — сверяйте с источником.' : 'Языковая модель не подключена — показаны подходящие места.'}</div>`);
  }
  holder.scrollIntoView({ block: 'end' });
}
$('#doc-msgs').addEventListener('click', (e) => {
  const s = e.target.closest('[data-src]');
  const place = s && s.closest('.bubble')?._src?.[s.dataset.src];
  if (place) { showFound(place); return; }
  const c = e.target.closest('[data-cite]');
  if (c) scrollToBlock(c.dataset.cite);
});
$('#doc-suggest').innerHTML = DEMO.docQA.map((x) => `<button class="chip ai" data-dq="${esc(x.q)}">${esc(x.q)}</button>`).join('');
$('#doc-suggest').addEventListener('click', (e) => { const c = e.target.closest('[data-dq]'); if (c) askDoc(c.dataset.dq); });
bindComposer('#doc-input', '#doc-send', askDoc);

function bindComposer(inputSel, btnSel, fn) {
  const input = $(inputSel);
  const send = () => { const v = input.value; input.value = ''; input.style.height = ''; fn(v); };
  $(btnSel).onclick = send;
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(120, input.scrollHeight) + 'px'; });
}

// Печать текста по словам, как при генерации моделью
async function typeInto(el, text, delay = 18) {
  const words = text.split(/(\s+)/);
  const caret = document.createElement('span');
  caret.className = 'caret';
  el.appendChild(caret);
  for (const w of words) {
    caret.insertAdjacentText('beforebegin', w);
    if (w.trim()) await sleep(delay + Math.random() * delay);
  }
  caret.remove();
}

/* -------------------------------------------------------------------------
   Снимок текста документа — для сравнения версий
   ------------------------------------------------------------------------- */
function blockTextFromHTML(html, mode = 'before') {
  const d = document.createElement('div');
  d.innerHTML = html;
  d.querySelectorAll('.sug').forEach((s) => {
    const pick = mode === 'after' ? s.querySelector('ins') : s.querySelector('del');
    s.replaceWith(document.createTextNode(pick ? pick.textContent : ''));
  });
  return d.textContent.replace(/\s+/g, ' ').trim();
}
function snapshotPage() {
  const snap = {};
  $$('[data-bid]', page).forEach((el) => {
    const c = el.cloneNode(true);
    c.querySelectorAll('.sug').forEach((s) => s.replaceWith(document.createTextNode(s.querySelector('del')?.textContent || '')));
    snap[el.dataset.bid] = el.classList.contains('meta') ? [...c.children].map((x) => x.textContent).join(' — ') : c.textContent.replace(/\s+/g, ' ').trim();
  });
  return snap;
}

/* =========================================================================
   СРАВНЕНИЕ ВЕРСИЙ
   ========================================================================= */
const cmp = { a: 'v1', b: 'v2', idx: 0, changed: [] };

function docText(id) {
  const base = {};
  DEMO.contract.blocks.forEach((b) => {
    base[b.id] = b.kind === 'meta' ? 'г. Самара — 21 июля 2025 г.' : blockTextFromHTML(b.html, 'before');
  });
  if (id === 'cp') return { ...base, ...DEMO.counterparty.patch };
  const v = DEMO.versions.find((x) => x.id === id);
  if (v.snapshot) return v.snapshot;
  return { ...base, ...v.patch };
}
function docName(id) {
  if (id === 'cp') return DEMO.counterparty.name;
  const v = DEMO.versions.find((x) => x.id === id);
  return `${v.name} · ${v.source.toLowerCase()}`;
}

// Пословное сравнение (наибольшая общая подпоследовательность)
function wordDiff(a, b) {
  const A = a.split(/\s+/).filter(Boolean), B = b.split(/\s+/).filter(Boolean);
  const n = A.length, m = B.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const left = [], right = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { left.push(esc(A[i])); right.push(esc(B[j])); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { left.push(`<span class="d">${esc(A[i])}</span>`); i++; }
    else { right.push(`<span class="a">${esc(B[j])}</span>`); j++; }
  }
  while (i < n) left.push(`<span class="d">${esc(A[i++])}</span>`);
  while (j < m) right.push(`<span class="a">${esc(B[j++])}</span>`);
  return [left.join(' '), right.join(' ')];
}

function verStats(id, prevId) {
  if (!prevId) return '';
  const A = docText(prevId), B = docText(id);
  let plus = 0, minus = 0;
  Object.keys(B).forEach((k) => {
    if (A[k] === B[k]) return;
    const aw = new Set((A[k] || '').split(/\s+/)), bw = new Set((B[k] || '').split(/\s+/));
    bw.forEach((w) => { if (!aw.has(w)) plus++; });
    aw.forEach((w) => { if (!bw.has(w)) minus++; });
  });
  return `<div class="ver-stat"><span class="plus">+${plus}</span> <span class="minus">−${minus}</span> ${plural(plus + minus, 'слово', 'слова', 'слов')}</div>`;
}

function renderVersions() {
  const vs = [...DEMO.versions].reverse();
  $('#timeline').innerHTML = vs.map((v) => {
    const prev = DEMO.versions.find((x) => x.n === v.n - 1);
    const ab = cmp.a === v.id ? '<span class="ab a">БЫЛО</span>' : cmp.b === v.id ? '<span class="ab b">СТАЛО</span>' : '';
    return `<div class="ver ${v.current ? 'current' : ''} ${cmp.a === v.id ? 'sel-a' : ''} ${cmp.b === v.id ? 'sel-b' : ''}" data-ver="${v.id}">
      <span class="line"></span><span class="node"></span>
      <div><div class="ver-name">${v.name}${v.current ? '<span class="tag ai">текущая</span>' : ''}${ab}</div>
      <div class="ver-meta">${v.when} · ${v.source}</div><div class="ver-desc">${esc(v.desc)}</div>${verStats(v.id, prev?.id)}</div></div>`;
  }).join('');
  const cp = DEMO.counterparty;
  $('#ext-docs').innerHTML = `<div class="ver ${cmp.a === 'cp' ? 'sel-a' : ''}" data-ver="cp" data-ext="1"><span class="node" style="background:var(--warning)"></span>
    <div><div class="ver-name">${cp.name}${cmp.a === 'cp' ? '<span class="ab a">БЫЛО</span>' : ''}</div><div class="ver-meta">${cp.when}</div><div class="ver-desc">${cp.desc}</div></div></div>`;
  renderCompare();
}

$('#screen-versions').addEventListener('click', (e) => {
  if (ed.real) return;                      // для настоящих документов — обработчик в real.js
  const v = e.target.closest('[data-ver]');
  if (!v) return;
  const id = v.dataset.ver;
  if (v.dataset.ext) { cmp.a = 'cp'; cmp.b = DEMO.versions.find((x) => x.current).id; }
  else if (e.shiftKey) { if (id !== cmp.b) cmp.a = id; }
  else if (id !== cmp.a) { cmp.b = id; }
  // «Было» всегда раньше «стало» (кроме внешнего документа)
  const num = (x) => (x === 'cp' ? 0 : DEMO.versions.find((y) => y.id === x).n);
  if (cmp.a !== 'cp' && num(cmp.a) > num(cmp.b)) [cmp.a, cmp.b] = [cmp.b, cmp.a];
  cmp.idx = 0;
  renderVersions();
});

function renderCompare() {
  const A = docText(cmp.a), B = docText(cmp.b);
  $('#cmp-a').textContent = $('#col-a-name').textContent = docName(cmp.a);
  $('#cmp-b').textContent = $('#col-b-name').textContent = docName(cmp.b);
  let la = '', lb = '';
  cmp.changed = [];
  DEMO.contract.blocks.forEach((b) => {
    const ta = A[b.id] || '', tb = B[b.id] || '';
    const h = b.kind === 'h1' || b.kind === 'h2' ? ' h' : '';
    if (ta === tb) {
      la += `<div class="blk${h}" data-cb="${b.id}">${esc(ta)}</div>`;
      lb += `<div class="blk${h}" data-cb="${b.id}">${esc(tb)}</div>`;
    } else {
      cmp.changed.push(b.id);
      const [x, y] = wordDiff(ta, tb);
      la += `<div class="blk changed${h}" data-cb="${b.id}">${x}</div>`;
      lb += `<div class="blk changed${h}" data-cb="${b.id}">${y}</div>`;
    }
  });
  $('#col-a').innerHTML = la;
  $('#col-b').innerHTML = lb;

  const key = `${cmp.a}|${cmp.b}`;
  let points = DEMO.versionSummaries[key] || autoSummary(A, B);
  if (cmp.a === 'cp' && !DEMO.versionSummaries[key]) points = [...DEMO.versionSummaries['cp|v2'], 'Плюс исправления, принятые после проверки: сумма прописью, реквизиты, даты.'];
  $('#ai-summary').innerHTML = `<div class="answer-head"><span class="ai-mark">${icon('spark')}</span>Что по сути изменилось · ${cmp.changed.length} ${plural(cmp.changed.length, 'пункт', 'пункта', 'пунктов')}</div>
    <ul>${points.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>`;
  $('#revert-btn').disabled = cmp.a === 'cp';
  focusChange(0, false);
}

const BLOCK_NAMES = { 'b-pre': 'Преамбула', 'p8-2': 'Реквизиты Поставщика', 'p8-3': 'Реквизиты Покупателя' };
function autoSummary(A, B) {
  if (!cmp.changed.length) return ['Версии совпадают.'];
  return cmp.changed.slice(0, 6).map((id) => {
    const a = (A[id] || '').split(/\s+/), b = (B[id] || '').split(/\s+/);
    const removed = a.filter((w) => !b.includes(w)).join(' ').replace(/[,.;]$/, '');
    const added = b.filter((w) => !a.includes(w)).join(' ').replace(/[,.;]$/, '');
    const num = (B[id] || '').match(/^(\d+\.\d+)\./);
    const where = num ? 'п. ' + num[1] : (BLOCK_NAMES[id] || 'Фрагмент');
    if (removed && added) return `${where}: «${removed}» → «${added}»`;
    if (added) return `${where}: добавлено «${added}»`;
    return `${where}: удалено «${removed}»`;
  });
}

function focusChange(i, scroll = true) {
  const n = cmp.changed.length;
  $('#chg-pos').textContent = n ? `${i + 1} из ${n}` : 'нет изменений';
  if (!n) return;
  cmp.idx = (i + n) % n;
  $('#chg-pos').textContent = `${cmp.idx + 1} из ${n}`;
  $$('.col-body .focus').forEach((x) => x.classList.remove('focus'));
  const id = cmp.changed[cmp.idx];
  ['#col-a', '#col-b'].forEach((c) => {
    const el = $(`${c} [data-cb="${id}"]`);
    el.classList.add('focus');
    if (scroll) {
      const col = $(c);
      col.scrollTo({ top: el.offsetTop - col.clientHeight / 2 + el.offsetHeight / 2, behavior: 'smooth' });
    }
  });
}
$('#chg-next').onclick = () => focusChange(cmp.idx + 1);
$('#chg-prev').onclick = () => focusChange(cmp.idx - 1);

// Синхронная прокрутка колонок
let syncing = false;
['#col-a', '#col-b'].forEach((sel, k) => {
  $(sel).addEventListener('scroll', () => {
    if (syncing) { syncing = false; return; }
    const src = $(sel), dst = $(k ? '#col-a' : '#col-b');
    syncing = true;
    dst.scrollTop = src.scrollTop * (dst.scrollHeight - dst.clientHeight) / Math.max(1, src.scrollHeight - src.clientHeight);
  });
});

$('#revert-btn').onclick = () => {
  if (ed.real) { realRevert(); return; }
  const from = DEMO.versions.find((x) => x.id === cmp.a);
  ed.version += 1;
  DEMO.versions.forEach((v) => { v.current = false; });
  DEMO.versions.push({ id: 'v' + ed.version, n: ed.version, name: 'Версия ' + ed.version, source: 'Возврат', current: true,
    when: new Date().toLocaleDateString('ru-RU'), desc: `Возврат к тексту версии ${from.n}. История сохранена.`, snapshot: docText(from.id) });
  $('#save-state').innerHTML = `${icon('check')}Сохранено · версия ${ed.version}`;
  cmp.a = DEMO.versions[DEMO.versions.length - 2].id; cmp.b = 'v' + ed.version;
  renderVersions();
  toast(`Создана версия ${ed.version} — возврат к версии ${from.n}. Ничего не удалено.`);
};

/* =========================================================================
   АССИСТЕНТ ПО БАЗЕ
   ========================================================================= */
const chat = { title: '', ctx: null };

function renderHistory(activeId) {
  $('#history-list').innerHTML = DEMO.chatHistory.map((h) =>
    `<button class="history-item ${h.id === activeId ? 'active' : ''}" data-hist="${h.id}">${esc(h.title)}<small>${h.when}</small></button>`).join('');
}
$('#history-list').addEventListener('click', (e) => {
  const h = e.target.closest('[data-hist]');
  if (!h) return;
  newChat();
  renderHistory(h.dataset.hist);
  const q = { budgets: 'Утверждённые бюджеты', expiring: 'Договоры, истекающие в декабре', vector: 'Все документы по ООО «Вектор Снаб»', orders: 'Действующие приказы по охране труда' }[h.dataset.hist];
  ask(q);
});

function newChat() {
  chat.ctx = null; chat.rctx = null; chat.mode = null; chat.title = '';
  renderHistory(null);
  $('#chat').innerHTML = `<div class="welcome"><span class="ai-mark" style="width:44px;height:44px;border-radius:12px">${icon('spark', '')}</span>
    <h2>Что найти в документах?</h2><div class="muted">Ассистент ищет по всей базе, считает суммы и показывает, откуда взят каждый ответ.</div>
    <div class="followups">${['Утверждённые бюджеты', 'Договоры, истекающие в декабре', 'Все документы по ООО «Вектор Снаб»', 'Действующие приказы по охране труда']
      .map((q) => `<button class="chip ai" data-ask="${esc(q)}">${esc(q)}</button>`).join('')}</div></div>`;
  crumbs(['Ассистент', 'Новый вопрос']);
}
$('#new-chat').onclick = newChat;
$('#chat').addEventListener('click', (e) => {
  const a = e.target.closest('[data-ask]');
  if (a) { ask(a.dataset.ask); return; }
  const r = e.target.closest('[data-ref]');
  if (r) {
    const b = DEMO.budgets.find((x) => x.n === +r.dataset.ref);
    toast(`Откроется документ: ${b ? b.basis + ' — ' + b.title : r.dataset.ref}`);
  }
});
bindComposer('#chat-input', '#chat-send', (q) => ask(q));

function stepsHTML(list, done) {
  return `<div class="steps">${list.map((s, j) => `<div class="step ${j < done ? 'done' : ''}"><span class="spin"></span>${s}</div>`).join('')}</div>`;
}

async function ask(q) {
  q = q.trim();
  if (!q) return;
  if ($('#chat .welcome')) $('#chat').innerHTML = '';
  if (!chat.title) { chat.title = q.length > 40 ? q.slice(0, 40) + '…' : q; crumbs(['Ассистент', chat.title]); }
  const box = $('#chat');
  box.insertAdjacentHTML('beforeend', `<div class="q-row"><div class="q">${esc(q)}</div></div>`);
  const ans = document.createElement('div');
  ans.className = 'answer';
  box.appendChild(ans);
  const scroll = () => { $('#chat-scroll').scrollTop = $('#chat-scroll').scrollHeight; };

  ans.innerHTML = `<div class="answer-head"><span class="ai-mark">${icon('spark')}</span>Ассистент</div><div class="st"></div><div class="body" style="display:grid;gap:14px"></div>`;
  const st = $('.st', ans);
  st.innerHTML = stepsHTML(['Ищу в базе документов'], 0);
  scroll();
  // Сначала настоящая база (real.js), демо-сценарии — если в базе ответа нет.
  // Уточнение к демо-ответу («за декабрь») остаётся в демо-сценарии.
  const real = typeof realPlan === 'function' ? realPlan : async () => null;
  let plan;
  if (chat.mode === 'demo') { plan = route(q); if (plan.miss) plan = (await real(q)) || plan; }
  else plan = (await real(q)) || route(q);
  if (plan.real) chat.mode = 'real'; else if (!plan.miss) chat.mode = 'demo';
  for (let i = 0; i <= plan.steps.length; i++) { st.innerHTML = stepsHTML(plan.steps, i); scroll(); if (i < plan.steps.length) await sleep(plan.real ? 180 : 520); }
  await plan.render($('.body', ans), scroll);
  scroll();
}

// Определяем сценарий по вопросу и контексту диалога
function route(q) {
  const ql = q.toLowerCase();
  const hasBudget = /бюджет/.test(ql);
  const followUp = chat.ctx?.topic === 'budgets' && /(декабр|подраздел|прошл|сравн)/.test(ql);
  if (hasBudget || followUp) {
    // Новый вопрос про бюджеты сбрасывает фильтр, уточнение — сохраняет его
    const month = /декабр/.test(ql) ? 12 : (hasBudget ? null : chat.ctx.month);
    const ctx = { topic: 'budgets', month };
    chat.ctx = ctx;
    if (/прошл|сравн/.test(ql)) return compareBudgets(ctx);
    if (/подраздел/.test(ql)) return budgetsByDept(ctx);
    return budgetAnswer(ctx);
  }
  if (/истека|заканчива|срок/.test(ql) && /договор/.test(ql)) { chat.ctx = { topic: 'contracts' }; return expiringAnswer(); }
  if (/вектор/.test(ql)) { chat.ctx = { topic: 'vendor' }; return vendorAnswer(); }
  if (/приказ/.test(ql) && /охран|труд/.test(ql)) { chat.ctx = { topic: 'orders' }; return ordersAnswer(); }
  if (/^кратко:/.test(ql) && typeof briefAnswer === 'function') { const b = briefAnswer(q); if (b) return b; }
  return notFound(q);
}

function budgetRows(ctx) {
  return DEMO.budgets.filter((b) => !ctx.month || b.month === ctx.month);
}

function budgetAnswer(ctx) {
  const rows = budgetRows(ctx);
  const total = rows.reduce((s, b) => s + b.amount, 0);
  const dec = ctx.month === 12;
  return {
    steps: ['Понял запрос: документы о бюджетах со статусом «утверждён»' + (dec ? ', период — декабрь 2025' : ''),
      dec ? 'Нашёл 6 документов за декабрь: 1 исключён как старая редакция, 1 квартальный — учтён отдельно'
        : 'Нашёл 9 подходящих документов, 2 исключены (старая редакция и нераспознанный скан)',
      'Извлёк суммы из карточек документов и сложил их',
      'Составляю сводку'],
    async render(el, scroll) {
      el.innerHTML = `
        <div class="headline">${dec ? 'За декабрь 2025 утверждено' : 'Найдено'} <span class="num">${rows.length} ${dec ? '' : plural(rows.length, 'утверждённый ', 'утверждённых ', 'утверждённых ')}${plural(rows.length, 'бюджет', 'бюджета', 'бюджетов')}</span> на общую сумму <span class="num">${mln(total)}</span></div>
        ${dec ? `<div class="scope-chips"><span class="chip filter">Статус: утверждён</span><span class="chip filter">Период: декабрь 2025 <button class="x" data-ask="Все бюджеты" style="background:none;border:0;padding:0">${icon('x')}</button></span></div>` : ''}
        <div class="box"><div class="box-head"><span>Документы-источники</span><span>Суммы взяты из текста документов · наведите на сумму, чтобы увидеть цитату</span></div>
        <table class="data"><thead><tr><th>#</th><th>Документ</th><th>Утверждён</th><th>Подразделение</th><th>Период</th><th class="num">Сумма</th></tr></thead><tbody>
        ${rows.map((b) => `<tr><td><span class="ref" data-ref="${b.n}">${b.n}</span></td><td><span class="doc-link" data-ref="${b.n}">${esc(b.title)}</span><div class="faint" style="font-size:12px">${esc(b.basis)}</div></td>
          <td>${b.approved}</td><td>${b.dept}</td><td>${b.period}</td><td class="num" title="«…утвердить бюджет в сумме ${rub(b.amount)}…» — ${esc(b.basis)}">${rub(b.amount)}</td></tr>`).join('')}
        <tr class="total"><td></td><td>Итого</td><td></td><td></td><td></td><td class="num">${rub(total)}</td></tr></tbody></table></div>
        <div class="box"><div class="box-head"><span>Распределение по подразделениям</span><span>${mln(total)}</span></div><div class="bars">
        ${[...rows].sort((a, b) => b.amount - a.amount).map((b) => `<div class="bar-row"><span>${b.dept}</span><div class="bar-track"><div class="bar-fill" data-w="${(b.amount / Math.max(...rows.map((r) => r.amount))) * 100}"></div></div><span class="val">${mln(b.amount)}</span></div>`).join('')}
        </div></div>
        <div class="summary"></div>`;
      scroll();
      setTimeout(() => $$('.bar-fill', el).forEach((f) => { f.style.width = f.dataset.w + '%'; }), 60);
      const text = dec
        ? 'Больше половины декабрьских средств приходится на отдел продаж — 8,65 млн ₽ [1]. Далее маркетинг — 3,15 млн ₽ [3], АХО — 1,98 млн ₽ [4] и юридический отдел — 1,24 млн ₽ [5]. Все четыре бюджета утверждены в последнюю неделю ноября.'
        : 'Крупнейшая статья — бюджет ИТ-департамента на IV квартал: 12,75 млн ₽ [2], это треть общей суммы. Четыре бюджета относятся к декабрю 2025 года и вместе дают 15,02 млн ₽ [1] [3] [4] [5]. Годовая корректировка бюджета отдела кадров — 6,3 млн ₽ [6], бюджет логистики на ноябрь — 4,87 млн ₽ [7].';
      const sum = $('.summary', el);
      await typeInto(sum, text, 16);
      sum.innerHTML = esc(text).replace(/\[(\d)\]/g, '<span class="ref" data-ref="$1">$1</span>');
      const alerts = [];
      if (dec) alerts.push('Бюджет ИТ-департамента на IV квартал (12,75 млн ₽) <span class="ref" data-ref="2">2</span> охватывает декабрь, но помесячной разбивки в нём нет — в итог не включён.');
      alerts.push('Бюджет отдела продаж на декабрь утверждён дважды: приказ № 318 от 25.11.2025 — 8 400 000 ₽ и служебная записка № 77 от 28.11.2025 — 8 650 000 ₽ <span class="ref" data-ref="1">1</span>. В итог взята последняя редакция.');
      if (!dec) alerts.push('В документе «Бюджет проекта „Склад-2“» сумма не распознана (скан низкого качества) — он не включён в итог.');
      el.insertAdjacentHTML('beforeend', `<div class="alerts">${alerts.map((a) => `<div class="alert">${icon('alert')}<span>${a}</span></div>`).join('')}</div>
        <div class="followups">${(dec ? ['По подразделениям', 'Сравнить с прошлым годом', 'Все бюджеты'] : ['За декабрь', 'По подразделениям', 'Сравнить с прошлым годом'])
          .map((f) => `<button class="chip ai" data-ask="${f}">${f}</button>`).join('')}</div>
        <div class="actions-row"><button class="btn small" data-toast="Сохранено: Бюджеты_${dec ? 'декабрь_' : ''}2025.xlsx">${icon('table')}Экспорт в Excel</button>
          <button class="btn small" data-toast="Сохранено: Сводка_по_бюджетам.pdf">${icon('download')}PDF</button>
          <button class="btn small" data-toast="Ответ скопирован">${icon('copy')}Копировать</button>
          <button class="btn small ghost" data-toast="Документы открыты в реестре с фильтром">${icon('file')}Открыть все в реестре</button></div>`);
      scroll();
    },
  };
}

function budgetsByDept(ctx) {
  const rows = budgetRows(ctx);
  return {
    steps: ['Группирую найденные бюджеты по подразделениям'],
    async render(el) {
      const total = rows.reduce((s, b) => s + b.amount, 0);
      el.innerHTML = `<div class="box"><div class="box-head"><span>По подразделениям${ctx.month === 12 ? ' · декабрь 2025' : ''}</span><span>${mln(total)}</span></div>
        <table class="data"><thead><tr><th>Подразделение</th><th class="num">Доля</th><th class="num">Сумма</th></tr></thead><tbody>
        ${[...rows].sort((a, b) => b.amount - a.amount).map((b) => `<tr><td>${b.dept} <span class="ref" data-ref="${b.n}">${b.n}</span></td><td class="num">${Math.round(b.amount / total * 100)} %</td><td class="num">${rub(b.amount)}</td></tr>`).join('')}
        <tr class="total"><td>Итого</td><td class="num">100 %</td><td class="num">${rub(total)}</td></tr></tbody></table></div>
        <div class="followups"><button class="chip ai" data-ask="Сравнить с прошлым годом">Сравнить с прошлым годом</button></div>`;
    },
  };
}

function compareBudgets(ctx) {
  return {
    steps: ['Ищу утверждённые бюджеты за ' + (ctx.month === 12 ? 'декабрь 2024 года' : '2024 год'), 'Сопоставляю подразделения'],
    async render(el) {
      const text = ctx.month === 12
        ? 'Сравнить не с чем: в базе нет утверждённых бюджетов на декабрь 2024 года. Самые ранние бюджеты в базе — за март 2025 года. Если загрузить документы за 2024 год, я смогу построить сравнение.'
        : 'В базе нет утверждённых бюджетов за 2024 год, поэтому сравнение построить нельзя. Самые ранние бюджеты в базе — за март 2025 года.';
      const d = document.createElement('div');
      d.className = 'summary';
      el.appendChild(d);
      await typeInto(d, text, 14);
      el.insertAdjacentHTML('beforeend', `<div class="actions-row"><button class="btn small" data-toast="Импорт документов будет на следующем шаге макета">${icon('upload')}Загрузить документы за 2024 год</button></div>`);
    },
  };
}

function expiringAnswer() {
  const rows = [
    ['Договор аренды № 87/24', 'ООО «ТехЛайн»', '15.12.2025', 'нет', '120 000 ₽/мес.'],
    ['Договор на обслуживание № 15-СО', 'ИП Гусев А. В.', '20.12.2025', 'да, на 1 год', '45 000 ₽/мес.'],
    ['Договор поставки № 124-А', 'ООО «Вектор Снаб»', '31.12.2025', 'нет', '1 250 000 ₽'],
    ['Договор подряда № 33/П', 'ООО «СтройМонтаж»', '31.12.2025', 'нет', '2 380 000 ₽'],
  ];
  return {
    steps: ['Ищу договоры со сроком действия до 31.12.2025', 'Проверяю условия об автопролонгации'],
    async render(el) {
      el.innerHTML = `<div class="headline">В декабре истекают <span class="num">4 договора</span>, автопролонгация есть только у одного</div>
        <div class="box"><table class="data"><thead><tr><th>Договор</th><th>Контрагент</th><th>Действует до</th><th>Автопролонгация</th><th class="num">Сумма</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td><span class="doc-link" data-ref="${esc(r[0])}">${r[0]}</span></td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td><td class="num">${r[4]}</td></tr>`).join('')}</tbody></table></div>
        <div class="alerts"><div class="alert">${icon('alert')}<span>Договор аренды № 87/24 истекает через 36 дней, автопролонгации нет. Уведомление о продлении нужно направить за 30 дней — до 15.11.2025.</span></div></div>`;
    },
  };
}

function vendorAnswer() {
  return {
    steps: ['Ищу документы, где упоминается ООО «Вектор Снаб» (ИНН 7725123450)'],
    async render(el) {
      el.innerHTML = `<div class="headline">По ООО «Вектор Снаб» найдено <span class="num">5 документов</span></div>
        <div class="box"><table class="data"><thead><tr><th>Документ</th><th>Дата</th><th>Состояние проверки</th></tr></thead><tbody>
        <tr><td><span class="doc-link" data-nav="editor">Договор поставки № 124-А</span></td><td>21.07.2025</td><td><span class="tag critical"><span class="sev-dot critical"></span>3 критичных</span></td></tr>
        <tr><td><span class="doc-link" data-ref="Счёт № 412">Счёт № 412</span></td><td>05.08.2025</td><td><span class="tag ok"><span class="sev-dot ok"></span>Без замечаний</span></td></tr>
        <tr><td><span class="doc-link" data-ref="Спецификация">Спецификация (Приложение № 1)</span></td><td>21.07.2025</td><td><span class="tag ok"><span class="sev-dot ok"></span>Без замечаний</span></td></tr>
        <tr><td><span class="doc-link" data-ref="Акт № 58">Акт приёма-передачи № 58</span></td><td>03.10.2025</td><td><span class="tag warning"><span class="sev-dot warning"></span>Приёмка позже срока поставки</span></td></tr>
        <tr><td><span class="doc-link" data-ref="Претензия">Претензия о просрочке поставки</span></td><td>02.10.2025</td><td><span class="tag ok"><span class="sev-dot ok"></span>Без замечаний</span></td></tr>
        </tbody></table></div>`;
    },
  };
}

function ordersAnswer() {
  const rows = [
    ['Приказ № 14-ОТ «О назначении ответственного за охрану труда»', '10.01.2025', 'Действует', 'ok'],
    ['Приказ № 52-ОТ «Об утверждении инструкций по охране труда»', '03.03.2025', 'Действует', 'ok'],
    ['Приказ № 97-ОТ «О проведении обучения по охране труда»', '15.05.2025', 'Ссылается на отменённый приказ № 8-ОТ', 'warning'],
  ];
  return {
    steps: ['Ищу приказы по охране труда', 'Проверяю, не отменены ли они более поздними приказами'],
    async render(el) {
      el.innerHTML = `<div class="headline">Действуют <span class="num">3 приказа</span> по охране труда, в одном есть ссылка на отменённый документ</div>
        <div class="box"><table class="data"><thead><tr><th>Приказ</th><th>Дата</th><th>Состояние</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td><span class="doc-link" data-ref="${esc(r[0])}">${esc(r[0])}</span></td><td>${r[1]}</td><td><span class="tag ${r[3]}"><span class="sev-dot ${r[3]}"></span>${r[2]}</span></td></tr>`).join('')}
        </tbody></table></div>
        <div class="alerts"><div class="alert">${icon('alert')}<span>Приказ № 97-ОТ ссылается на приказ № 8-ОТ, который отменён приказом № 52-ОТ от 03.03.2025.</span></div></div>`;
    },
  };
}

function notFound(q) {
  return {
    miss: true,
    steps: ['Ищу по словам и по смыслу во всех документах'],
    async render(el) {
      const d = document.createElement('div');
      d.className = 'summary';
      el.appendChild(d);
      await typeInto(d, `По запросу «${q}» в базе не нашлось документов, которые отвечают на вопрос. Я не буду придумывать ответ: попробуйте переформулировать или уточнить тип документа и период.`, 12);
      el.insertAdjacentHTML('beforeend', `<div class="followups"><button class="chip ai" data-ask="Утверждённые бюджеты">Утверждённые бюджеты</button><button class="chip ai" data-ask="Договоры, истекающие в декабре">Договоры, истекающие в декабре</button></div>`);
    },
  };
}

/* -------------------------------------------------------------------------
   Горячие клавиши и запуск
   ------------------------------------------------------------------------- */
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key.toLowerCase() === 'k') { e.preventDefault(); $('#quick-search').focus(); }
  if (e.ctrlKey && e.key.toLowerCase() === 'j') { e.preventDefault(); screenEd.classList.toggle('right-collapsed'); syncPanels(); }
});
$('#quick-search').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && e.target.value.trim()) { const q = e.target.value; e.target.value = ''; go('assistant'); newChat(); ask(q); }
});

renderPage();
renderReview();
renderComments();
newChat();
go('editor');
activate('f1', false);
