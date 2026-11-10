/* =========================================================================
   Обзор, реестр, поиск, настройки, импорт и экспорт.
   Использует общие функции из app.js ($, icon, go, toast, ask …).
   ========================================================================= */
'use strict';

// Экраны, которые рисуются при каждом открытии (вызываются из go() в app.js)
const SCREENS = { overview: renderOverview, registry: renderRegistry, search: renderSearch, settings: renderSettings };

const SEV_RANK = { critical: 3, warning: 2, info: 1, ok: 0, none: -1 };
const parseDate = (s) => { const [d, m, y] = s.split('.').map(Number); return new Date(y, m - 1, d).getTime(); };
// Документы из базы (real.js) + демонстрационные, если они включены в настройках
const liveDocs = () => [...REAL.docs, ...(showDemo() ? DEMO.docs : [])].filter((d) => !d.deleted);
const findDoc = (id) => REAL.docs.find((x) => x.id === id) || DEMO.docs.find((x) => x.id === id);

// Для договора 124-А состояние проверки берём из редактора; документы из базы пока не проверялись
function issuesOf(d) {
  if (!d.issues && d.id !== 'doc-124a') return [0, 0, 0];
  if (d.id !== 'doc-124a') return d.issues;
  const p = DEMO.findings.filter((f) => !ed.res[f.id]);
  return ['critical', 'warning', 'info'].map((s) => p.filter((f) => f.severity === s).length);
}
function sevOf(d) {
  if (!d.issues && d.id !== 'doc-124a') return 'none';
  const [c, w, i] = issuesOf(d);
  return c ? 'critical' : w ? 'warning' : i ? 'info' : 'ok';
}
function checkLabel(d) {
  if (sevOf(d) === 'none') return 'Не проверен';
  const [c, w, i] = issuesOf(d);
  if (c) return `${c} ${plural(c, 'критичная', 'критичных', 'критичных')}`;
  if (w) return `${w} ${plural(w, 'замечание', 'замечания', 'замечаний')}`;
  if (i) return `${i} ${plural(i, 'совет', 'совета', 'советов')}`;
  return 'Без замечаний';
}
function issueText(d) {
  if (d.real) return `Версия ${d.version} · исходный файл ${d.filename}`;
  if (d.id === 'doc-124a') {
    const p = DEMO.findings.filter((f) => !ed.res[f.id] && f.severity === 'critical').map((f) => f.title.toLowerCase());
    return p.length ? p.join(', ') : 'Критичных ошибок нет';
  }
  return d.issueText || '';
}
const sheet = (lines = 7) => `<div class="sheet"><i class="t"></i>${'<i></i>'.repeat(lines - 2)}<i class="s"></i></div>`;

function openDoc(id) {
  const d = findDoc(id);
  if (!d) return;
  if (d.real) { openRealDoc(d.realId); return; }
  if (d.open) { restoreDemo(); go('editor'); return; }
  toast(`«${d.title}» — демонстрационный документ. В редакторе открываются договор № 124-А и документы, загруженные в базу.`, 'Открыть договор', () => { restoreDemo(); go('editor'); });
}

/* -------------------------------------------------------------------------
   Модальные окна
   ------------------------------------------------------------------------- */
function openModal(html) {
  $('#modal-box').innerHTML = html;
  $('#modal').hidden = false;
}
function closeModal() { $('#modal').hidden = true; $('#modal-box').innerHTML = ''; }
$('#modal').addEventListener('mousedown', (e) => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#modal').hidden) closeModal(); });

document.addEventListener('click', (e) => {
  const o = e.target.closest('[data-open]');
  if (o) { (o.dataset.open === 'import' ? openImport : openExport)(); return; }
  if (e.target.closest('[data-close]')) { closeModal(); return; }
  const a = e.target.closest('[data-ask-global]');
  if (a) { go('assistant'); newChat(); ask(a.dataset.askGlobal); return; }
  const doc = e.target.closest('[data-doc]');
  if (doc && !e.target.closest('input')) openDoc(doc.dataset.doc);
});

/* =========================================================================
   ОБЗОР
   ========================================================================= */
function renderOverview() {
  crumbs(['Обзор']);
  const docs = liveDocs();
  const crit = docs.filter((d) => sevOf(d) === 'critical');
  const att = docs.filter((d) => sevOf(d) !== 'ok').sort((a, b) => SEV_RANK[sevOf(b)] - SEV_RANK[sevOf(a)]).slice(0, 6);
  const types = {};
  docs.forEach((d) => { types[d.type] = (types[d.type] || 0) + 1; });
  const typeRows = Object.entries(types).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const maxT = Math.max(...typeRows.map((r) => r[1]));
  const maxE = Math.max(...DEMO.errorStats.map((r) => r[1]));
  const soon = DEMO.deadlines.filter((x) => /через (\d+)/.exec(x.left)[1] <= 30).length;
  const recent = [...REAL.docs, ...(showDemo() ? ['doc-124a', 'd23', 'd22', 'd11'].map((id) => DEMO.docs.find((d) => d.id === id)) : [])].slice(0, 4);
  if (!REAL.loaded) refreshReal().then(() => { if ($('#screen-overview').classList.contains('active')) renderOverview(); });

  $('#ov').innerHTML = `
    <div><h1>Добрый день</h1><div class="muted">Вот что требует внимания в базе документов.</div></div>
    <label class="ov-ask"><span class="ai-mark">${icon('spark')}</span>
      <input id="ov-ask" placeholder="Спросите о документах: «утверждённые бюджеты за декабрь», «договоры с ТехЛайн»…">
      <button class="send" id="ov-send" title="Спросить">${icon('send')}</button></label>
    <div class="ov-hints">${['Утверждённые бюджеты', 'Договоры, истекающие в декабре', 'Все документы по ООО «Вектор Снаб»']
      .map((q) => `<button class="chip ai" data-ask-global="${esc(q)}">${esc(q)}</button>`).join('')}</div>
    <div class="tiles">
      <button class="tile" data-nav="registry"><span class="k">${icon('file')}Документов в базе</span><span class="v">${docs.length}</span><span class="s">+3 за неделю</span></button>
      <button class="tile critical" id="tile-crit"><span class="k">${icon('alert')}С критичными ошибками</span><span class="v">${crit.length}</span><span class="s">${crit.map((d) => d.title.split(' ').slice(0, 2).join(' ')).join(', ') || 'нет'}</span></button>
      <button class="tile ai" data-doc="doc-124a"><span class="k">${icon('check')}Правок ждут решения</span><span class="v">${DEMO.findings.filter((f) => !ed.res[f.id]).length}</span><span class="s">в договоре № 124-А</span></button>
      <button class="tile warning" id="tile-dl"><span class="k">${icon('history')}Сроки в ближайшие 30 дней</span><span class="v">${soon}</span><span class="s">ближайший — ${DEMO.deadlines[0].date}</span></button>
    </div>
    <div class="ov-grid">
      <div class="ov-col">
        <div class="box"><div class="box-head"><span>Требуют внимания</span><button class="btn ghost small" id="ov-all-issues">Все документы с ошибками</button></div>
          ${att.map((d) => `<div class="att-row" data-doc="${d.id}"><span class="sev-dot ${sevOf(d)}"></span>
            <div><div class="att-title">${esc(d.title)}</div><div class="att-sub">${esc(checkLabel(d))}${issueText(d) ? ' · ' + esc(issueText(d)) : ''}</div></div>
            <button class="btn small">${d.open ? 'Исправить' : 'Открыть'}</button></div>`).join('')}</div>
        <div><div class="label" style="margin-bottom:8px">Недавние</div><div class="recent">
          ${recent.map((d) => `<button class="doc-card" data-doc="${d.id}"><div class="thumb">${sheet()}</div><div class="meta"><b>${esc(d.title)}</b><span>${d.modified}</span></div></button>`).join('')}</div></div>
      </div>
      <div class="ov-col">
        <div class="box" id="ov-deadlines"><div class="box-head"><span>Ближайшие сроки</span></div>
          ${DEMO.deadlines.map((x) => `<div class="dl-row" data-doc="${x.doc}"><div><div class="dl-date">${x.date}</div><div class="dl-left ${x.sev}">${x.left}</div></div><div>${esc(x.what)}</div></div>`).join('')}</div>
        <div class="box"><div class="box-head"><span>Документы по типам</span><span>${docs.length}</span></div><div class="bars">
          ${typeRows.map(([t, n]) => `<div class="bar-row"><span>${t}</span><div class="bar-track"><div class="bar-fill" style="width:${n / maxT * 100}%;background:var(--info)"></div></div><span class="val">${n}</span></div>`).join('')}</div></div>
        <div class="box"><div class="box-head"><span>Частые ошибки за месяц</span><span>${DEMO.errorStats.reduce((s, r) => s + r[1], 0)}</span></div><div class="bars">
          ${[...DEMO.errorStats].sort((a, b) => b[1] - a[1]).map(([t, n]) => `<div class="bar-row"><span>${t}</span><div class="bar-track"><div class="bar-fill" style="width:${n / maxE * 100}%;background:var(--warning)"></div></div><span class="val">${n}</span></div>`).join('')}</div></div>
      </div>
    </div>`;

  const send = () => { const q = $('#ov-ask').value.trim(); if (!q) return; go('assistant'); newChat(); ask(q); };
  $('#ov-send').onclick = (e) => { e.preventDefault(); send(); };
  $('#ov-ask').onkeydown = (e) => { if (e.key === 'Enter') send(); };
  $('#tile-crit').onclick = $('#ov-all-issues').onclick = () => { Object.assign(reg, { folder: 'issues', q: '', type: '', status: '', cp: '' }); go('registry'); };
  $('#tile-dl').onclick = () => $('#ov-deadlines').scrollIntoView({ behavior: 'smooth' });
}

/* =========================================================================
   РЕЕСТР
   ========================================================================= */
const reg = { folder: 'all', q: '', type: '', status: '', cp: '', sort: 'date', dir: -1, sel: new Set(), focus: null, view: 'table' };

function regFiltered() {
  let list = reg.folder === 'trash' ? DEMO.docs.filter((d) => d.deleted) : liveDocs();
  if (reg.folder === 'real') list = REAL.docs;
  if (reg.folder === 'issues') list = list.filter((d) => !['ok', 'none'].includes(sevOf(d)));
  else if (!['all', 'trash', 'real'].includes(reg.folder)) list = list.filter((d) => d.folder === reg.folder);
  if (reg.type) list = list.filter((d) => d.type === reg.type);
  if (reg.status) list = list.filter((d) => d.status === reg.status);
  if (reg.cp) list = list.filter((d) => d.cp === reg.cp);
  if (reg.q) { const q = reg.q.toLowerCase(); list = list.filter((d) => (d.title + ' ' + d.cp + ' ' + d.type).toLowerCase().includes(q)); }
  const key = {
    title: (d) => d.title, type: (d) => d.type, date: (d) => parseDate(d.date), cp: (d) => d.cp, amount: (d) => d.amount,
    status: (d) => d.status, check: (d) => SEV_RANK[sevOf(d)] * 100 + issuesOf(d).reduce((a, b) => a + b, 0),
  }[reg.sort];
  return [...list].sort((a, b) => { const x = key(a), y = key(b); return (x > y ? 1 : x < y ? -1 : 0) * reg.dir; });
}

function renderRegistry() {
  crumbs(['Документы']);
  if (!REAL.loaded) refreshReal().then(() => { if ($('#screen-registry').classList.contains('active')) renderRegistry(); });
  const scr = $('#screen-registry');
  const all = liveDocs();
  const folderName = { all: 'Все документы', issues: 'С ошибками', trash: 'Корзина', real: 'Загруженные в базу' }[reg.folder] || reg.folder;
  const list = regFiltered();
  const opts = (field) => [...new Set(all.map((d) => d[field]).filter((v) => v && v !== '—'))].sort();
  const sel = (field, label) => `<select class="chip ${reg[field] ? 'set' : ''}" data-rf="${field}"><option value="">${label}</option>${opts(field === 'cp' ? 'cp' : field).map((v) => `<option ${reg[field] === v ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>`;
  const th = (key, label, cls = '') => `<th class="${cls}" data-sort="${key}">${label}${reg.sort === key ? ` <span class="arr">${reg.dir > 0 ? '↑' : '↓'}</span>` : ''}</th>`;
  const fcount = (f) => all.filter((d) => d.folder === f).length;

  scr.classList.toggle('with-drawer', !!reg.focus);
  scr.innerHTML = `
    <aside class="panel folders">
      <div class="panel-head"><span class="panel-title">Документы</span><button class="icon-btn" title="Новая папка" data-toast="Папка «Новая папка» создана">${icon('plus')}</button></div>
      <div class="scroll"><div class="folder-list">
        ${[['all', 'Все документы', all.length, 'file'], ['real', 'Загруженные в базу', REAL.docs.length, 'upload'],
          ['issues', 'С ошибками', all.filter((d) => !['ok', 'none'].includes(sevOf(d))).length, 'alert']]
          .map(([k, n, c, ic]) => `<button class="folder ${reg.folder === k ? 'active' : ''}" data-folder="${k}">${icon(ic)}${n}<span class="c">${c}</span></button>`).join('')}
        <div class="label" style="padding:12px 10px 4px">Папки</div>
        ${DEMO.folders.map((f) => `<button class="folder ${reg.folder === f ? 'active' : ''}" data-folder="${esc(f)}">${icon('folder')}${esc(f)}<span class="c">${fcount(f)}</span></button>`).join('')}
        <div style="height:10px"></div>
        <button class="folder ${reg.folder === 'trash' ? 'active' : ''}" data-folder="trash">${icon('x')}Корзина<span class="c">${DEMO.docs.filter((d) => d.deleted).length}</span></button>
      </div></div>
    </aside>
    <section class="reg">
      <div class="reg-head"><h1>${esc(folderName)}</h1><span class="faint">${list.length}</span><div class="spacer"></div>
        <div class="seg"><button data-view="table" class="${reg.view === 'table' ? 'on' : ''}">Таблица</button><button data-view="tiles" class="${reg.view === 'tiles' ? 'on' : ''}">Плитки</button></div>
        <button class="btn primary" data-open="import">${icon('upload')}Загрузить</button></div>
      <div class="reg-tools">
        <label class="inline-search">${icon('search')}<input id="reg-q" placeholder="Название, контрагент…" value="${esc(reg.q)}"></label>
        ${sel('type', 'Тип')}${sel('status', 'Статус')}${sel('cp', 'Контрагент')}
        ${reg.type || reg.status || reg.cp || reg.q ? `<button class="btn ghost small" id="reg-reset">Сбросить</button>` : ''}
      </div>
      <div class="reg-table-wrap">${reg.view === 'table' ? regTable(list, th) : regTiles(list)}</div>
      ${reg.sel.size ? `<div class="bulk-bar"><b>Выбрано: ${reg.sel.size}</b>
        <button class="btn small" id="bulk-check">${icon('shield')}Проверить</button>
        <button class="btn small" data-toast="Выбранные документы перемещены в папку">${icon('folder')}В папку</button>
        <button class="btn small" data-toast="Метка добавлена">Метка</button>
        <button class="btn small" data-toast="Экспортировано в ZIP: ${reg.sel.size} ${plural(reg.sel.size, 'файл', 'файла', 'файлов')}">${icon('download')}Экспорт</button>
        <button class="btn small ai" id="bulk-ask">${icon('spark')}Спросить ИИ</button>
        <button class="btn small ghost" id="bulk-del">${reg.folder === 'trash' ? 'Восстановить' : 'Удалить'}</button>
        <button class="icon-btn" id="bulk-clear" title="Снять выделение">${icon('x')}</button></div>` : ''}
    </section>
    ${reg.focus ? regDrawer(findDoc(reg.focus)) : ''}`;
  bindRegistry(list);
}

function regTable(list, th) {
  if (!list.length) return `<div class="empty"><b>Ничего не найдено</b><span>Измените фильтры или загрузите документы.</span></div>`;
  const allSel = list.every((d) => reg.sel.has(d.id));
  return `<table class="reg-table"><thead><tr>
    <th style="width:30px"><input type="checkbox" class="cb" id="sel-all" ${allSel ? 'checked' : ''}></th>
    ${th('title', 'Документ')}${th('type', 'Тип', 'opt')}${th('date', 'Дата')}${th('cp', 'Контрагент', 'opt')}${th('amount', 'Сумма', 'num')}${th('status', 'Статус')}${th('check', 'Проверка')}<th class="opt">Изменён</th></tr></thead><tbody>
    ${list.map((d) => `<tr data-row="${d.id}" class="${reg.sel.has(d.id) ? 'sel' : ''} ${reg.focus === d.id ? 'focus' : ''}">
      <td><input type="checkbox" class="cb" data-sel="${d.id}" ${reg.sel.has(d.id) ? 'checked' : ''}></td>
      <td><div class="td-title"><span class="ic">${icon('file')}</span><div><b>${esc(d.title)}</b><small>${esc(d.folder)}${d.cp !== '—' ? ' · ' + esc(d.cp) : ''}</small></div></div></td>
      <td class="opt">${d.type}</td><td>${d.date}</td><td class="opt">${esc(d.cp)}</td><td class="num">${d.amount ? rub(d.amount) : '—'}</td>
      <td><span class="status s-${d.status}">${d.status}</span></td>
      <td><span class="check ${sevOf(d)}"><span class="sev-dot ${sevOf(d)}"></span>${checkLabel(d)}</span></td>
      <td class="faint opt" style="white-space:nowrap">${d.modified}</td></tr>`).join('')}</tbody></table>`;
}

function regTiles(list) {
  return `<div class="tiles-view">${list.map((d) => `<button class="doc-card" data-row="${d.id}"><div class="thumb">${sheet()}</div>
    <div class="meta"><b>${esc(d.title)}</b><span class="check ${sevOf(d)}"><span class="sev-dot ${sevOf(d)}"></span>${checkLabel(d)}</span><span>${d.type} · ${d.date}</span></div></button>`).join('')}</div>`;
}

function regDrawer(d) {
  if (!d) return '';
  const related = d.real ? [] : d.id === 'doc-124a' ? ['d6', 'd7', 'd8'] : DEMO.docs.filter((x) => x.id !== d.id && x.cp === d.cp && d.cp !== '—').map((x) => x.id).slice(0, 3);
  const [c, w, i] = issuesOf(d);
  return `<aside class="panel drawer">
    <div class="panel-head"><span class="panel-title">Карточка</span><button class="icon-btn" id="drawer-close" title="Закрыть">${icon('x')}</button></div>
    <div class="scroll"><div class="thumb">${sheet(9)}</div><div class="drawer-body">
      <div><div class="drawer-title">${esc(d.title)}</div><div class="muted" style="font-size:13px">${d.type} · ${d.date} · <span class="status s-${d.status}">${d.status}</span></div></div>
      <div class="issue-box"><span class="check ${sevOf(d)}"><span class="sev-dot ${sevOf(d)}"></span><b>${checkLabel(d)}</b></span>
        ${c + w + i ? `<span class="muted">${esc(issueText(d))}</span><span class="faint" style="font-size:12px">Критично: ${c} · Замечания: ${w} · Советы: ${i}</span>` : '<span class="muted">Последняя проверка замечаний не нашла.</span>'}</div>
      <div class="fields" style="padding:0">
        ${[['Контрагент', d.cp], ['Сумма', d.amount ? rub(d.amount) : '—'], ['Папка', d.folder], ['Метки', d.tags.join(', ')], ['Изменён', d.modified]]
          .map(([k, v]) => `<div class="field"><div class="k">${k}</div><div class="v">${esc(v)}</div></div>`).join('')}</div>
      ${related.length ? `<div><div class="label" style="margin-bottom:6px">Связанные документы</div><div class="related" style="padding:0">
        ${related.map((id) => { const r = DEMO.docs.find((x) => x.id === id); return `<a href="#" data-focus="${id}">${icon('file')}${esc(r.title)}</a>`; }).join('')}</div></div>` : ''}
      <div style="display:grid;gap:8px">
        <button class="btn primary" data-doc="${d.id}">${d.open || d.real ? 'Открыть в редакторе' : 'Открыть'}</button>
        <button class="btn ai" data-ask-global="${esc('Кратко: ' + d.title)}">${icon('spark')}Спросить ИИ об этом документе</button>
      </div>
    </div></div></aside>`;
}

function bindRegistry(list) {
  const scr = $('#screen-registry');
  $$('[data-folder]', scr).forEach((b) => b.onclick = () => { reg.folder = b.dataset.folder; reg.sel.clear(); reg.focus = null; renderRegistry(); });
  $$('[data-view]', scr).forEach((b) => b.onclick = () => { reg.view = b.dataset.view; renderRegistry(); });
  $$('[data-rf]', scr).forEach((s) => s.onchange = () => { reg[s.dataset.rf] = s.value; renderRegistry(); });
  $$('[data-sort]', scr).forEach((h) => h.onclick = () => { if (reg.sort === h.dataset.sort) reg.dir *= -1; else { reg.sort = h.dataset.sort; reg.dir = h.dataset.sort === 'title' ? 1 : -1; } renderRegistry(); });
  const q = $('#reg-q');
  q.oninput = () => { reg.q = q.value; const pos = q.selectionStart; renderRegistry(); const n = $('#reg-q'); n.focus(); n.setSelectionRange(pos, pos); };
  const reset = $('#reg-reset');
  if (reset) reset.onclick = () => { Object.assign(reg, { q: '', type: '', status: '', cp: '' }); renderRegistry(); };
  const all = $('#sel-all');
  if (all) all.onchange = () => { list.forEach((d) => (all.checked ? reg.sel.add(d.id) : reg.sel.delete(d.id))); renderRegistry(); };
  $$('[data-sel]', scr).forEach((c) => c.onchange = () => { c.checked ? reg.sel.add(c.dataset.sel) : reg.sel.delete(c.dataset.sel); renderRegistry(); });
  $$('[data-row]', scr).forEach((r) => {
    r.onclick = (e) => { if (e.target.closest('input')) return; reg.focus = r.dataset.row; renderRegistry(); };
    r.ondblclick = () => openDoc(r.dataset.row);
  });
  $$('[data-focus]', scr).forEach((a) => a.onclick = (e) => { e.preventDefault(); reg.focus = a.dataset.focus; renderRegistry(); });
  const dc = $('#drawer-close');
  if (dc) dc.onclick = () => { reg.focus = null; renderRegistry(); };
  const bc = $('#bulk-clear');
  if (bc) {
    bc.onclick = () => { reg.sel.clear(); renderRegistry(); };
    $('#bulk-check').onclick = async () => {
      toast(`Проверяю ${reg.sel.size} ${plural(reg.sel.size, 'документ', 'документа', 'документов')}…`);
      await sleep(1400);
      toast('Проверка завершена: новых замечаний нет');
    };
    $('#bulk-ask').onclick = () => {
      const n = reg.sel.size;
      go('assistant'); newChat();
      $('#scope-chip').innerHTML = `${icon('folder')}Выбрано: ${n} ${plural(n, 'документ', 'документа', 'документов')}`;
      $('#chat-input').focus();
    };
    $('#bulk-del').onclick = () => {
      const realIds = [...reg.sel].filter((id) => findDoc(id)?.real);
      if (realIds.length) { confirmDeleteReal(realIds); return; }
      const ids = [...reg.sel];
      const restore = reg.folder === 'trash';
      ids.forEach((id) => { DEMO.docs.find((d) => d.id === id).deleted = !restore; });
      reg.sel.clear(); reg.focus = null; renderRegistry();
      if (!restore) toast(`Перемещено в корзину: ${ids.length}. Хранится 30 дней.`, 'Отменить', () => { ids.forEach((id) => { DEMO.docs.find((d) => d.id === id).deleted = false; }); renderRegistry(); });
    };
  }
}

// Документы в базе удаляются насовсем — поэтому спрашиваем подтверждение
function confirmDeleteReal(ids) {
  const docs = ids.map(findDoc);
  openModal(`<div class="modal-head"><h2>Удалить ${docs.length} ${plural(docs.length, 'документ', 'документа', 'документов')}?</h2><button class="icon-btn" data-close>${icon('x')}</button></div>
    <div class="modal-body"><div>Документы, их версии и исходные файлы будут удалены из базы без возможности восстановления:</div>
      <ul style="margin:0;padding-left:20px">${docs.map((d) => `<li>${esc(d.title)}</li>`).join('')}</ul></div>
    <div class="modal-foot"><div class="spacer"></div><button class="btn" data-close>Отмена</button><button class="btn primary" id="del-go" style="background:var(--critical);border-color:var(--critical);color:#fff">Удалить навсегда</button></div>`);
  $('#del-go').onclick = async () => {
    $('#del-go').disabled = true;
    try {
      for (const d of docs) await API.remove(d.realId);
      if (ed.real && docs.some((d) => d.realId === ed.real.id)) restoreDemo();
      toast(`Удалено: ${docs.length}`);
    } catch (e) {
      toast('Не удалось удалить: ' + e.message);
    }
    closeModal();
    reg.sel.clear(); reg.focus = null;
    await refreshReal();
    renderRegistry();
  };
}

/* =========================================================================
   ПОИСК
   ========================================================================= */
const srch = { q: '', mode: 'sem', types: new Set(), year: '', cp: '', min: '', max: '' };
const stem = (w) => { w = w.toLowerCase().replace(/ё/g, 'е'); return w.length > 5 ? w.slice(0, w.length - 2) : w; };

function searchDocs() {
  const words = srch.q.toLowerCase().replace(/ё/g, 'е').split(/[^a-zа-я0-9-]+/i).filter((w) => w.length >= 3 && !['для', 'все', 'как', 'что', 'где', 'это'].includes(w));
  if (!words.length) return [];
  const res = [];
  for (const d of DEMO.docs.filter((x) => !x.deleted)) {      // документы из базы ищет сервер
    const hay = (d.title + ' ' + d.text + ' ' + d.cp).toLowerCase().replace(/ё/g, 'е');
    let exact = 0, sem = 0;
    const terms = [];
    for (const w of words) {
      const s = stem(w);
      if (hay.includes(s)) { exact++; terms.push(s); continue; }
      if (srch.mode === 'sem') {
        const key = Object.keys(DEMO.synonyms).find((k) => s.startsWith(k) || k.startsWith(s));
        const syn = key && DEMO.synonyms[key].find((x) => hay.includes(x));
        if (syn) { sem++; terms.push(syn); }
      }
    }
    const ok = srch.mode === 'words' ? exact === words.length : exact + sem > 0 && (exact + sem) >= Math.ceil(words.length / 2);
    if (ok) res.push({ d, score: exact * 2 + sem, exact: exact === words.length, terms });
  }
  return res.filter(({ d }) => (!srch.types.size || srch.types.has(d.type)) && (!srch.year || d.date.endsWith(srch.year)) && (!srch.cp || d.cp === srch.cp)
    && (!srch.min || d.amount >= +srch.min) && (!srch.max || d.amount <= +srch.max)).sort((a, b) => b.score - a.score);
}

function snippet(d, terms) {
  const sentences = d.text.split(/(?<=\.)\s+/);
  const lower = (s) => s.toLowerCase().replace(/ё/g, 'е');
  const s = sentences.find((x) => terms.some((t) => lower(x).includes(t))) || sentences[0];
  let html = esc(s);
  terms.forEach((t) => {
    const re = new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[а-яёa-z0-9-]*)`, 'gi');
    html = html.replace(re, '<mark>$1</mark>');
  });
  return html;
}

function renderSearch() {
  crumbs(['Поиск']);
  const scr = $('#screen-search');
  if (!scr.dataset.built) {
    scr.dataset.built = '1';
    scr.innerHTML = `
      <aside class="panel facets"><div class="panel-head"><span class="panel-title">Фильтры</span><button class="btn ghost small" id="f-reset">Сбросить</button></div>
        <div class="scroll">
          <div class="facet" id="f-types"><div class="facet-title">Тип документа</div></div>
          <div class="facet"><div class="facet-title">Год</div><select id="f-year"><option value="">Любой</option><option>2026</option><option>2025</option><option>2024</option></select></div>
          <div class="facet"><div class="facet-title">Контрагент</div><select id="f-cp"><option value="">Любой</option></select></div>
          <div class="facet"><div class="facet-title">Сумма, ₽</div><div class="range"><input type="text" id="f-min" placeholder="от"><input type="text" id="f-max" placeholder="до"></div></div>
        </div></aside>
      <section class="srch">
        <div class="srch-head">
          <label class="srch-box">${icon('search', '')}<input id="s-q" placeholder="Что найти? Например: неустойка за просрочку, аренда помещения"><span class="kbd">Enter</span></label>
          <div class="srch-opts"><div class="seg" id="s-mode"><button data-m="words">По словам</button><button data-m="sem">По смыслу</button></div>
            <span id="s-where"></span><span id="s-count" style="margin-left:auto"></span></div>
        </div>
        <div class="srch-results"><div class="srch-inner" id="s-res"></div></div>
      </section>`;
    const q = $('#s-q');
    q.oninput = () => { srch.q = q.value; renderHits(); };
    $$('#s-mode button').forEach((b) => b.onclick = () => { srch.mode = b.dataset.m; renderHits(); });
    $('#f-types').addEventListener('change', (e) => {
      const c = e.target.closest('[data-ft]');
      if (c) { c.checked ? srch.types.add(c.dataset.ft) : srch.types.delete(c.dataset.ft); renderHits(); }
    });
    $('#f-year').onchange = (e) => { srch.year = e.target.value; renderHits(); };
    $('#f-cp').onchange = (e) => { srch.cp = e.target.value; renderHits(); };
    $('#f-min').oninput = (e) => { srch.min = e.target.value.replace(/\D/g, ''); renderHits(); };
    $('#f-max').oninput = (e) => { srch.max = e.target.value.replace(/\D/g, ''); renderHits(); };
    $('#f-reset').onclick = () => {
      Object.assign(srch, { year: '', cp: '', min: '', max: '' }); srch.types.clear();
      $$('[data-ft]', scr).forEach((c) => { c.checked = false; });
      ['#f-year', '#f-cp', '#f-min', '#f-max'].forEach((s) => { $(s).value = ''; });
      renderHits();
    };
    $('#s-res').addEventListener('click', (e) => {
      const p = e.target.closest('[data-preset]');
      if (p) { srch.q = $('#s-q').value = p.dataset.preset; renderHits(); return; }
      const r = e.target.closest('[data-real-hit]');
      if (r) openRealDoc(+r.dataset.realHit, r.dataset.block != null ? { block: +r.dataset.block, start: +r.dataset.start, end: +r.dataset.end } : null);
    });
  }
  if (!REAL.loaded) refreshReal().then(() => { if ($('#screen-search').classList.contains('active')) renderHits(); });
  renderHits();
  setTimeout(() => $('#s-q').focus(), 0);
}

// Фильтры строятся по документам, которые реально есть: из базы и (если включены) демонстрационным
function renderFacets(counts) {
  const docs = liveDocs();
  const types = [...new Set(docs.map((d) => d.type))].sort();
  $('#f-types').innerHTML = `<div class="facet-title">Тип документа</div>` + types.map((t) =>
    `<label><input type="checkbox" class="cb" data-ft="${esc(t)}" ${srch.types.has(t) ? 'checked' : ''}>${esc(t)}<span class="c">${counts ? counts[t] || '' : docs.filter((d) => d.type === t).length}</span></label>`).join('');
  const cps = [...new Set([...REAL.docs.flatMap((d) => d.parties || []), ...(showDemo() ? DEMO.counterparties.map((c) => c[0]) : [])])].sort();
  const sel = $('#f-cp');
  if (sel.dataset.sig !== cps.join('|')) {
    sel.dataset.sig = cps.join('|');
    sel.innerHTML = `<option value="">Любой</option>` + cps.map((c) => `<option ${srch.cp === c ? 'selected' : ''}>${esc(c)}</option>`).join('');
  }
  $('#s-where').innerHTML = `Где: <b>вся база</b> · ${docs.length} ${plural(docs.length, 'документ', 'документа', 'документов')}`;
}

// Фрагмент найденного текста с подсветкой (смещения считает сервер)
function snippetHTML(s) {
  let html = '', pos = 0;
  for (const [a, b] of s.highlights) {
    if (a < pos) continue;
    html += esc(s.text.slice(pos, a)) + '<mark>' + esc(s.text.slice(a, b)) + '</mark>';
    pos = b;
  }
  html += esc(s.text.slice(pos));
  return (s.prefix ? '… ' : '') + html + (s.suffix ? ' …' : '');
}

async function realSearch() {
  if (!API.online || !srch.q.trim()) return [];
  const p = new URLSearchParams({ q: srch.q, mode: srch.mode });
  if (srch.year) { p.set('from', `${srch.year}-01-01`); p.set('to', `${srch.year}-12-31`); }
  if (srch.cp) p.set('cp', srch.cp);
  if (srch.min) p.set('min', srch.min);
  if (srch.max) p.set('max', srch.max);
  const hits = await API.search(p);
  return hits.map((h) => ({ d: mapReal(h.document), exact: h.exact, snippets: h.snippets }))
    .filter(({ d }) => !srch.types.size || srch.types.has(d.type));
}

let searchSeq = 0;
async function renderHits() {
  $$('#s-mode button').forEach((b) => b.classList.toggle('on', b.dataset.m === srch.mode));
  const box = $('#s-res');
  const seq = ++searchSeq;
  if (!srch.q.trim()) {
    $('#s-count').textContent = '';
    renderFacets(null);
    box.innerHTML = `<div class="label" style="margin-top:6px">Частые запросы</div><div class="followups">
      ${['неустойка за просрочку', 'аренда помещения', 'охрана труда', 'бюджет на декабрь', 'назначение директора', 'закупка оргтехники']
        .map((p) => `<button class="chip" data-preset="${p}">${icon('search')}${p}</button>`).join('')}</div>`;
    return;
  }
  let real = [];
  let realError = '';
  try { real = await realSearch(); } catch (e) { realError = e.message; }
  if (seq !== searchSeq) return;                   // пока ждали сервер, запрос уже изменился
  const demo = showDemo() ? searchDocs() : [];
  const total = real.length + demo.length;
  const counts = {};
  [...real, ...demo].forEach(({ d }) => { counts[d.type] = (counts[d.type] || 0) + 1; });
  renderFacets(counts);
  $('#s-count').textContent = `${total} ${plural(total, 'документ', 'документа', 'документов')}`;
  const question = /\?$|^(какие|какой|сколько|кто|когда|где|почему|утвержд)/i.test(srch.q.trim());
  const realHTML = real.map(({ d, exact, snippets }) => {
    const first = snippets[0];
    return `<div class="hit" data-real-hit="${d.realId}" ${first ? `data-block="${first.block}" data-start="${first.start}" data-end="${first.end}"` : ''}>
      <div class="hit-top"><span class="hit-title">${esc(d.title)}</span><span class="tag ai" style="font-size:11.5px">из базы</span>
        <span class="match ${exact ? 'exact' : 'sem'}">${exact ? 'точное совпадение' : 'по смыслу'}</span></div>
      <div class="hit-meta">${d.type} · ${d.date}${d.cp !== '—' ? ' · ' + esc(d.cp) : ''}${d.amount ? ' · ' + rub(d.amount) : ''}</div>
      ${snippets.map((s) => `<div class="hit-snip">${snippetHTML(s)}</div>`).join('')}</div>`;
  }).join('');
  box.innerHTML = (realError ? `<div class="qi-note">${icon('alert')}<span>Поиск по базе недоступен: ${esc(realError)}</span></div>` : '') +
    (question || !total ? `<div class="ask-card" data-ask-global="${esc(srch.q)}"><span class="ai-mark">${icon('spark')}</span>
      <span>Похоже на вопрос. <b>Спросить ассистента:</b> «${esc(srch.q)}» — он найдёт документы, посчитает суммы и покажет источники.</span></div>` : '') +
    realHTML +
    (total ? demo.map(({ d, exact, terms }) => `<div class="hit" data-doc="${d.id}">
      <div class="hit-top"><span class="hit-title">${esc(d.title)}</span><span class="match ${exact ? 'exact' : 'sem'}">${exact ? 'точное совпадение' : 'по смыслу'}</span></div>
      <div class="hit-meta">${d.type} · ${d.date}${d.cp !== '—' ? ' · ' + esc(d.cp) : ''}${d.amount ? ' · ' + rub(d.amount) : ''}</div>
      <div class="hit-snip">${snippet(d, terms)}</div></div>`).join('')
      : `<div class="empty"><b>Ничего не найдено</b><span>${srch.mode === 'words' ? 'Попробуйте поиск «По смыслу» или снимите фильтры.' : 'Снимите фильтры или переформулируйте запрос.'}</span></div>`);
}

/* =========================================================================
   НАСТРОЙКИ
   ========================================================================= */
const setState = { section: 'org', profile: 'std', terms: ['Покупатель', 'Поставщик', 'КС-2', 'пролонгация', 'СЭД', 'АХО', 'неустойка'] };
const SECTIONS = [['org', 'Организация', 'home'], ['dict', 'Справочники', 'table'], ['rules', 'Правила проверок', 'shield'], ['ai', 'Искусственный интеллект', 'spark'],
  ['storage', 'Хранилище и копии', 'folder'], ['ui', 'Интерфейс', 'moon'], ['about', 'О программе', 'settings']];

function innValid(v) {
  if (!/^\d{10}$|^\d{12}$/.test(v)) return false;
  const d = v.split('').map(Number);
  const chk = (w) => w.reduce((s, x, i) => s + x * d[i], 0) % 11 % 10;
  if (v.length === 10) return chk([2, 4, 10, 3, 5, 9, 4, 6, 8]) === d[9];
  return chk([7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) === d[10] && chk([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) === d[11];
}

function renderSettings() {
  crumbs(['Настройки', SECTIONS.find((s) => s[0] === setState.section)[1]]);
  const scr = $('#screen-settings');
  scr.innerHTML = `<aside class="panel set-nav"><div class="panel-head"><span class="panel-title">Настройки</span></div>
    <div class="folder-list">${SECTIONS.map(([k, n, ic]) => `<button class="folder ${setState.section === k ? 'active' : ''}" data-sec="${k}">${icon(ic)}${n}</button>`).join('')}</div></aside>
    <section class="set-body"><div class="set-inner">${settingsBody()}</div></section>`;
  $$('[data-sec]', scr).forEach((b) => b.onclick = () => { setState.section = b.dataset.sec; renderSettings(); });
  bindSettings(scr);
}

function settingsBody() {
  const save = `<div class="set-actions"><button class="btn primary" data-toast="Настройки сохранены">Сохранить</button></div>`;
  switch (setState.section) {
    case 'org': return `<h1>Организация</h1><div class="lead">Свои реквизиты — с ними сверяются договоры, счета и приказы.</div>
      <div class="form-grid">
        <div class="form-row full"><label>Полное наименование</label><input value="Общество с ограниченной ответственностью «Северный Терминал»"></div>
        <div class="form-row"><label>ИНН</label><input id="org-inn" value="6311098769" maxlength="12"><span class="hint" id="inn-hint"></span></div>
        <div class="form-row"><label>КПП</label><input value="631101001"></div>
        <div class="form-row"><label>ОГРН</label><input value="1186313012345"></div>
        <div class="form-row"><label>Руководитель</label><input value="Ковалёв Игорь Петрович"><span class="hint">По приказу № 112 от 03.03.2025</span></div>
        <div class="form-row full"><label>Юридический адрес</label><input value="443013, г. Самара, ул. Заводская, д. 14"></div>
        <div class="form-row"><label>Банк</label><input value="ПАО «Волга-Банк»"></div>
        <div class="form-row"><label>БИК</label><input value="043601999"></div>
        <div class="form-row full"><label>Расчётный счёт</label><input value="40702810900000067890"></div>
      </div>${save}`;
    case 'dict': return `<h1>Справочники</h1><div class="lead">С ними система сверяет реквизиты и не считает ошибкой специальные термины.</div>
      <div class="box"><div class="box-head"><span>Контрагенты · ${DEMO.counterparties.length}</span><button class="btn small" data-toast="Форма нового контрагента">${icon('plus')}Добавить</button></div>
      <table class="data"><thead><tr><th>Название</th><th>ИНН</th><th>КПП</th><th>Руководитель</th><th class="num">Документов</th></tr></thead><tbody>
      ${DEMO.counterparties.map((c) => `<tr><td>${esc(c[0])}</td><td>${c[1]} ${innValid(c[1]) ? '' : '<span class="tag critical">неверный</span>'}</td><td>${c[2]}</td><td>${c[3]}</td><td class="num">${c[4]}</td></tr>`).join('')}</tbody></table></div>
      <div class="box"><div class="box-head"><span>Словарь терминов · не считаются опечатками</span></div><div style="padding:12px 14px;display:grid;gap:10px">
        <div class="followups" id="terms">${setState.terms.map((t, i) => `<span class="chip filter">${esc(t)}<button class="x" data-term="${i}" style="background:none;border:0;padding:0">${icon('x')}</button></span>`).join('')}</div>
        <label class="inline-search" style="width:280px">${icon('plus')}<input id="term-in" placeholder="Новый термин и Enter"></label></div></div>`;
    case 'rules': return `<h1>Правила проверок</h1><div class="lead">Что ищет проверка и насколько это важно. Отключённые правила не показываются в панели правок.</div>
      <div class="box">${DEMO.rules.map((r, i) => `<div class="rule-row"><div><div class="cat">${r[0]}</div>${esc(r[1])}</div>
        <select data-rule-sev="${i}">${[['critical', 'Критично'], ['warning', 'Замечание'], ['info', 'Совет']].map(([v, n]) => `<option value="${v}" ${r[2] === v ? 'selected' : ''}>${n}</option>`).join('')}</select>
        <label class="switch"><input type="checkbox" data-rule-on="${i}" ${r[3] ? 'checked' : ''}><span></span></label></div>`).join('')}</div>
      <div class="box"><div class="box-head"><span>Обязательные разделы по типам</span><button class="btn small ghost" data-toast="Редактор шаблонов будет в рабочей версии">Изменить</button></div>
        <div class="kv"><span class="k">Договор</span><span>Предмет, цена, порядок расчётов, сроки, ответственность, разрешение споров, реквизиты и подписи</span>
        <span class="k">Приказ</span><span>Номер, дата, основание, распорядительная часть, ответственный, подпись руководителя</span>
        <span class="k">Служебная записка</span><span>Адресат, суть, обоснование, сумма (если есть), подпись</span>
        <span class="k">Техническое задание</span><span>Цели, требования, сроки этапов, порядок приёмки, стоимость</span></div></div>${save}`;
    case 'ai': {
      const P = { lite: ['Лёгкий', 'Для ПК с 8 ГБ памяти', 'Модель 1,5B · ≈1,2 ГБ', 'Ответ: 20–40 с'], std: ['Стандарт', 'Для ПК с 16 ГБ памяти', 'Модель 3–4B · ≈2,5 ГБ', 'Ответ: 15–30 с'] };
      const mem = setState.profile === 'std' ? [['Интерфейс', 0.5, 'var(--text-faint)'], ['Сервер данных', 0.5, 'var(--info)'], ['AI-сервис', 0.3, 'var(--ok)'], ['Языковая модель', 2.5, 'var(--ai)'], ['Поиск по смыслу', 0.5, 'var(--warning)']]
        : [['Интерфейс', 0.5, 'var(--text-faint)'], ['Сервер данных', 0.5, 'var(--info)'], ['AI-сервис', 0.3, 'var(--ok)'], ['Языковая модель', 1.2, 'var(--ai)'], ['Поиск по смыслу', 0.5, 'var(--warning)']];
      const limit = setState.profile === 'std' ? 6 : 3.5;
      const used = mem.reduce((s, m) => s + m[1], 0);
      return `<h1>Искусственный интеллект</h1><div class="lead">Всё работает на этом компьютере, без интернета. На этом ПК найдено 16 ГБ памяти — рекомендован профиль «Стандарт».</div>
        <div class="profiles">${Object.entries(P).map(([k, p]) => `<button class="profile ${setState.profile === k ? 'on' : ''}" data-profile="${k}"><b>${p[0]}</b><span class="muted">${p[1]}</span><span class="faint" style="font-size:12.5px">${p[2]} · ${p[3]}</span></button>`).join('')}</div>
        <div class="box"><div class="box-head"><span>Языковая модель на этом компьютере</span></div><div class="kv" id="llm-status"><span class="k">Состояние</span><span>Проверяю…</span></div></div>
        <div class="box"><div class="box-head"><span>Память приложения</span><span>${used.toFixed(1).replace('.', ',')} из ${String(limit).replace('.', ',')} ГБ</span></div><div class="mem">
          <div class="mem-bar">${mem.map((m) => `<span style="width:${m[1] / limit * 100}%;background:${m[2]}"></span>`).join('')}</div>
          <div class="mem-legend">${mem.map((m) => `<span><i style="background:${m[2]}"></i>${m[0]} — ${String(m[1]).replace('.', ',')} ГБ</span>`).join('')}</div></div></div>
        <div class="box">${[['Использовать видеокарту', 'Видеопамяти 2 ГБ — ускорение будет небольшим', false], ['Выгружать модель после 10 минут простоя', 'Освобождает память для Word и 1С', true], ['Смысловая проверка новых документов в фоне', 'Работает с низким приоритетом, не мешает редактору', true]]
          .map(([t, h, on]) => `<div class="rule-row" style="grid-template-columns:1fr 34px"><div>${t}<div class="cat">${h}</div></div><label class="switch"><input type="checkbox" ${on ? 'checked' : ''}><span></span></label></div>`).join('')}</div>
        <div class="set-actions"><button class="btn" id="ai-index">${icon('revert')}Перестроить индекс поиска</button><button class="btn" id="ai-bench">${icon('spark')}Проверить скорость</button></div>`;
    }
    case 'storage': return `<h1>Хранилище и резервные копии</h1><div class="lead">База — одна папка на этом компьютере. Её можно скопировать или восстановить одним файлом.</div>
      <div class="box"><div class="kv"><span class="k">Папка базы</span><span>C:\\Documentum\\data</span><span class="k">Занято</span><span>1,8 ГБ — документы 1,2 ГБ, версии 0,2 ГБ, индекс поиска 0,4 ГБ</span>
        <span class="k">Последняя копия</span><span>Вчера, 18:00 · D:\\Backup\\Documentum</span><span class="k">Корзина</span><span>Хранить удалённое 30 дней</span></div></div>
      <div class="box"><div class="rule-row" style="grid-template-columns:1fr 34px"><div>Ежедневная резервная копия в 18:00<div class="cat">Хранится 14 последних копий</div></div><label class="switch"><input type="checkbox" checked><span></span></label></div>
        <div class="rule-row" style="grid-template-columns:1fr 34px"><div>Шифровать базу и спрашивать пароль при запуске<div class="cat">Защита, если компьютер украдут</div></div><label class="switch"><input type="checkbox"><span></span></label></div></div>
      <div class="set-actions"><button class="btn primary" id="backup-now">${icon('download')}Создать копию сейчас</button><button class="btn" data-toast="Выберите файл копии для восстановления">${icon('revert')}Восстановить из копии</button><button class="btn ghost" data-toast="Открыта папка C:\\Documentum\\data">Открыть папку</button></div>`;
    case 'ui': return `<h1>Интерфейс</h1>
      <div class="form-grid"><div class="form-row"><label>Тема</label><select id="ui-theme"><option value="dark">Тёмная</option><option value="light">Светлая</option></select></div>
        <div class="form-row"><label>Масштаб интерфейса</label><select><option>90 %</option><option selected>100 %</option><option>110 %</option><option>125 %</option></select></div>
        <div class="form-row"><label>Шрифт документа по умолчанию</label><select><option>Times New Roman</option><option>Arial</option><option>Calibri</option></select></div>
        <div class="form-row"><label>Размер шрифта</label><select><option>12</option><option>14</option></select></div></div>
      <div class="box"><div class="rule-row" style="grid-template-columns:1fr 34px"><div>Показывать демонстрационные документы<div class="cat">23 примера для презентации: договоры, приказы, бюджеты. Загруженные вами документы показываются всегда.</div></div>
        <label class="switch"><input type="checkbox" id="ui-demo" ${showDemo() ? 'checked' : ''}><span></span></label></div></div>
      <div class="box"><div class="box-head"><span>Горячие клавиши</span></div><div class="kv">
        ${[['Ctrl + K', 'Быстрый поиск'], ['Ctrl + J', 'Показать или скрыть панель правок'], ['Ctrl + S', 'Сохранить версию'], ['Ctrl + Z / Ctrl + Y', 'Отменить / повторить'], ['Ctrl + B / I / U', 'Жирный / курсив / подчёркнутый'], ['Esc', 'Закрыть окно']]
          .map(([k, v]) => `<span class="k"><span class="kbd">${k}</span></span><span>${v}</span>`).join('')}</div></div>`;
    default: return `<h1>О программе</h1><div class="lead">Documentum 0.2.0 · демонстрационная версия</div>
      <div class="box"><div class="box-head"><span>Сервер документов</span></div><div class="kv" id="srv-status"><span class="k">Состояние</span><span>Проверяю…</span></div></div>
      <div class="box"><div class="box-head"><span>Состояние служб</span><button class="btn small ghost" data-toast="Журнал ошибок пуст">Журнал ошибок</button></div><div class="kv">
        ${[['Интерфейс', 'работает'], ['Сервер данных', 'работает · 127.0.0.1:8080'], ['AI-сервис', 'работает · 127.0.0.1:8000'], ['Языковая модель', 'загружена · профиль «Стандарт»'], ['Индекс поиска', '23 документа · обновлён 5 минут назад']]
          .map(([k, v]) => `<span class="k">${k}</span><span class="svc"><span class="sev-dot ok"></span>${v}</span>`).join('')}</div></div>
      <div class="muted" style="font-size:13px">Все данные хранятся только на этом компьютере. Сетевые запросы — только внутри машины (localhost).</div>`;
  }
}

function bindSettings(scr) {
  const inn = $('#org-inn', scr);
  if (inn) {
    const check = () => {
      const ok = innValid(inn.value.trim());
      inn.classList.toggle('ok', ok);
      $('#inn-hint').className = 'hint ' + (ok ? 'ok' : 'bad');
      $('#inn-hint').textContent = ok ? 'Контрольная сумма верна' : 'Контрольная сумма не сходится';
    };
    inn.oninput = check; check();
  }
  const ti = $('#term-in', scr);
  if (ti) {
    ti.onkeydown = (e) => { if (e.key === 'Enter' && ti.value.trim()) { setState.terms.push(ti.value.trim()); renderSettings(); $('#term-in').focus(); } };
    $$('[data-term]', scr).forEach((b) => b.onclick = () => { setState.terms.splice(+b.dataset.term, 1); renderSettings(); });
  }
  $$('[data-rule-on]', scr).forEach((c) => c.onchange = () => { DEMO.rules[+c.dataset.ruleOn][3] = c.checked; toast(c.checked ? 'Правило включено' : 'Правило отключено'); });
  $$('[data-rule-sev]', scr).forEach((s) => s.onchange = () => { DEMO.rules[+s.dataset.ruleSev][2] = s.value; });
  $$('[data-profile]', scr).forEach((b) => b.onclick = () => { setState.profile = b.dataset.profile; renderSettings(); toast(`Профиль «${b.querySelector('b').textContent}» включится после перезапуска модели`); });
  const idx = $('#ai-index', scr);
  if (idx) {
    idx.onclick = async () => { idx.disabled = true; idx.textContent = 'Индексация… 0 %'; for (let p = 20; p <= 100; p += 20) { await sleep(300); idx.textContent = `Индексация… ${p} %`; } toast('Индекс поиска перестроен: 23 документа'); renderSettings(); };
    $('#ai-bench').onclick = async () => { toast('Проверяю скорость модели…'); await sleep(1500); toast('Первые слова ответа — через 4,1 с, скорость — 9 слов в секунду'); };
  }
  const bk = $('#backup-now', scr);
  if (bk) bk.onclick = async () => { bk.disabled = true; bk.textContent = 'Создаю копию…'; await sleep(1200); toast('Копия создана: D:\\Backup\\Documentum\\2025-11-09.zip (1,8 ГБ)'); renderSettings(); };
  const demo = $('#ui-demo', scr);
  if (demo) demo.onchange = () => { store.set('showDemo', demo.checked ? 'on' : 'off'); toast(demo.checked ? 'Демонстрационные документы показаны' : 'Демонстрационные документы скрыты'); };
  const srv = $('#srv-status', scr);
  if (srv) refreshReal().then(serverStatusHTML).then((h) => { srv.innerHTML = h; });
  const llm = $('#llm-status', scr);
  if (llm) {
    // настоящее состояние модели: файл .gguf в папке ai-service/models и библиотека llama.cpp
    API.assistantStatus().then((st) => {
      const state = st.available ? (st.loaded ? 'загружена в память' : 'подключена, загрузится при первом вопросе ассистенту') : 'не подключена';
      llm.innerHTML = `<span class="k">Состояние</span><span class="svc"><span class="sev-dot ${st.available ? 'ok' : 'warning'}"></span>${state}</span>`
        + (st.model ? `<span class="k">Файл модели</span><span>${esc(st.model)}</span>` : '')
        + (st.reason ? `<span class="k">Причина</span><span>${esc(st.reason)}</span>` : '')
        + (st.available ? '' : '<span class="k">Что это значит</span><span>Ассистент работает: списки и суммы считаются точно, а вывод составляется по шаблону.</span>');
      // поиск по смыслу: отпечатки абзацев считаются в фоне, изменённые абзацы — заново, остальные берутся готовыми
      const se = st.search;
      if (se) {
        const state = !se.available ? 'не подключён — поиск работает по словам и синонимам'
          : se.pending ? `индексация: готово ${se.ready} из ${se.blocks} абзацев` : `готов · ${se.blocks} ${plural(se.blocks, 'абзац', 'абзаца', 'абзацев')}`;
        llm.innerHTML += `<span class="k">Поиск по смыслу</span><span class="svc"><span class="sev-dot ${se.available && !se.pending ? 'ok' : 'warning'}"></span>${state}</span>`
          + (se.model ? `<span class="k">Модель поиска</span><span>${esc(se.model)}</span>` : '');
      }
    }).catch(() => { llm.innerHTML = '<span class="k">Состояние</span><span class="svc"><span class="sev-dot warning"></span>нет связи с сервером Documentum</span>'; });
  }
  const th = $('#ui-theme', scr);
  if (th) { th.value = document.documentElement.dataset.theme; th.onchange = () => setTheme(th.value); }
}

/* =========================================================================
   ИМПОРТ
   ========================================================================= */
const STAGES = ['Чтение', 'Распознавание', 'Тип', 'Данные', 'Проверка'];
let importQueue = [];

function guessType(name) {
  const n = name.toLowerCase();
  const map = [['догов', 'Договор'], ['соглаш', 'Доп. соглашение'], ['приказ', 'Приказ'], ['акт', 'Акт'], ['счет', 'Счёт'], ['счёт', 'Счёт'], ['служеб', 'Служебная записка'], ['регламент', 'Регламент'], ['тз', 'ТЗ'], ['бюджет', 'Бюджет']];
  return (map.find(([k]) => n.includes(k)) || [null, 'Прочее'])[1];
}

function openImport() {
  importQueue = [];
  openModal(`<div class="modal-head"><h2>Загрузка документов</h2><button class="icon-btn" data-close>${icon('x')}</button></div>
    <div class="modal-body">
      <div class="form-grid"><div class="form-row"><label>Папка</label><select id="imp-folder"><option value="">Определить автоматически</option>${DEMO.folders.map((f) => `<option>${esc(f)}</option>`).join('')}</select></div>
        <div class="form-row"><label>Метки</label><input id="imp-tags" placeholder="например: поставка, 2025"></div></div>
      <div class="drop" id="drop"><span class="big-ic">${icon('upload', '')}</span><b>Перетащите файлы сюда</b>
        <span>DOCX, DOC, RTF, ODT, PDF, TXT и сканы (JPG, PNG, TIFF). Можно целую папку.</span>
        <div style="display:flex;gap:8px;margin-top:6px"><button class="btn" id="pick">Выбрать файлы</button><button class="btn ghost" id="demo-files">Добавить демо-файлы</button></div>
        <input type="file" id="file-in" multiple hidden></div>
      <div class="queue" id="queue"></div>
    </div>
    <div class="modal-foot"><span class="muted" id="imp-status">Файлы проверяются сразу после загрузки</span><div class="spacer"></div>
      <button class="btn" data-close>Закрыть</button><button class="btn primary" id="imp-open" disabled>Открыть в реестре</button></div>`);
  const drop = $('#drop');
  $('#pick').onclick = () => $('#file-in').click();
  $('#file-in').onchange = (e) => addFiles([...e.target.files].map((f) => ({ name: f.name, size: f.size, file: f })));
  API.check().then((ok) => {
    if (!importQueue.length) $('#imp-status').textContent = API.statusText();
    if (!ok && API.outdated) toast('Сервер Documentum старой версии: загрузка в базу недоступна до обновления.');
  });
  $('#demo-files').onclick = () => addFiles([
    { name: 'Договор_поставки_124-А_ред3.docx', size: 48210, dup: 'doc-124a' },
    { name: 'Акт_сверки_ВекторСнаб_ноябрь.pdf', size: 182300, link: 'doc-124a', type: 'Акт', issues: [0, 1, 0] },
    { name: 'Скан_приказ_340.jpg', size: 1630000, scan: true, type: 'Приказ', issues: [0, 0, 1] },
  ]);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); addFiles([...e.dataTransfer.files].map((f) => ({ name: f.name, size: f.size, file: f }))); };
  $('#imp-open').onclick = () => {
    closeModal();
    Object.assign(reg, { folder: importQueue.some((x) => x.realDoc) ? 'real' : 'all', sort: 'date', dir: -1, focus: null });
    go('registry');
  };
}

function addFiles(files) {
  files.forEach((f) => {
    const item = { ...f, id: 'q' + Math.random().toString(36).slice(2, 8), stage: 0, done: false };
    item.type = item.type || guessType(f.name);
    item.issues = item.issues || [0, f.name.length % 3, f.name.length % 2];
    importQueue.push(item);
    runImport(item);
  });
  renderQueue();
}

async function runImport(item) {
  if (item.file) {
    // Настоящий файл никогда не «загружаем понарошку»: либо в базу, либо честная причина
    if (API.online === null) await API.check();
    if (API.online) { realImport(item); return; }
    item.error = API.outdated
      ? 'Файл не сохранён: запущен сервер Documentum старой версии. Закройте приложение и запустите обновлённую сборку.'
      : 'Файл не сохранён: сервер Documentum не запущен. Запустите Documentum.exe и загрузите файл снова.';
    item.stage = 0; item.done = true;
    renderQueue();
    return;
  }
  for (let s = 0; s < STAGES.length; s++) {
    item.stage = s;
    renderQueue();
    await sleep(item.scan && s === 1 ? 1500 : 450 + Math.random() * 250);
  }
  item.stage = STAGES.length;
  item.done = true;
  if (!item.dup) addImported(item);
  renderQueue();
}

function addImported(item) {
  const today = new Date();
  DEMO.docs.unshift({
    id: 'imp-' + item.id, type: item.type, title: item.name.replace(/\.[^.]+$/, '').replace(/_/g, ' '), date: today.toLocaleDateString('ru-RU'),
    cp: item.link ? 'ООО «Вектор Снаб»' : '—', amount: 0, status: 'Проект', issues: item.issues, modified: 'Только что',
    folder: $('#imp-folder')?.value || (item.type === 'Приказ' ? 'Приказы' : item.type === 'Акт' || item.type === 'Счёт' ? 'Счета и акты' : 'Договоры'),
    tags: ($('#imp-tags')?.value || '').split(',').map((t) => t.trim()).filter(Boolean),
    issueText: item.scan ? '3 слова распознаны неуверенно' : '', text: '',
  });
}

function renderQueue() {
  const q = $('#queue');
  if (!q) return;
  const size = (b) => b > 1e6 ? (b / 1e6).toFixed(1).replace('.', ',') + ' МБ' : Math.max(1, Math.round(b / 1e3)) + ' КБ';
  q.innerHTML = importQueue.map((it) => {
    const [c, w, i] = it.issues;
    const sev = c ? 'critical' : w ? 'warning' : i ? 'info' : 'ok';
    const label = c ? `${c} критичных` : w ? `${w} ${plural(w, 'замечание', 'замечания', 'замечаний')}` : i ? `${i} ${plural(i, 'совет', 'совета', 'советов')}` : 'Без замечаний';
    let tail = '';
    if (it.done && it.error) tail = `<div class="qi-note" style="background:var(--critical-bg)">${icon('alert')}<span>${esc(it.error)}</span></div>`;
    else if (it.done && it.realDoc) tail = `<div class="qi-result"><span class="status">${esc(it.type)}</span><span class="check none"><span class="sev-dot none"></span>Сохранён в базу · версия 1</span>
        <span class="spacer" style="flex:1"></span><button class="btn small primary" data-open-real="${it.realDoc.id}">Открыть в редакторе</button></div>`
      + it.warnings.map((w) => `<div class="qi-note">${icon('alert')}<span>${esc(w)}</span></div>`).join('');
    else if (it.done && it.dup && !it.dupDone) tail = `<div class="qi-note">${icon('alert')}<span>Похожий документ уже есть: <b>Договор поставки № 124-А</b> (совпадение 94 %)</span><span class="spacer"></span>
      <button class="btn small primary" data-dup="version" data-q="${it.id}">Сделать новой версией</button><button class="btn small" data-dup="separate" data-q="${it.id}">Отдельно</button><button class="btn small ghost" data-dup="skip" data-q="${it.id}">Пропустить</button></div>`;
    else if (it.done && it.dup) tail = `<div class="qi-result tag ok">${icon('check')}${it.dupDone}</div>`;
    else if (it.done) tail = `<div class="qi-result"><span class="status">${it.type}</span><span class="check ${sev}"><span class="sev-dot ${sev}"></span>${label}</span>${it.scan ? '<span class="faint">распознано с точностью 97 %</span>' : ''}</div>`
      + (it.link && !it.linkDone ? `<div class="qi-note link">${icon('file')}<span>Относится к договору <b>№ 124-А</b> с ООО «Вектор Снаб»?</span><span class="spacer"></span><button class="btn small" data-link="yes" data-q="${it.id}">Да, связать</button><button class="btn small ghost" data-link="no" data-q="${it.id}">Нет</button></div>` : '')
      + (it.linkDone ? `<div class="qi-result tag ok">${icon('check')}Связан с договором № 124-А</div>` : '');
    return `<div class="qi"><div class="qi-top">${icon('file')}<b>${esc(it.name)}</b><span class="faint" style="font-size:12px">${size(it.size)}</span></div>
      <div class="pipeline">${STAGES.map((s, k) => `<span class="${k < it.stage ? 'done' : k === it.stage ? 'run' : ''}">${s}</span>`).join('')}</div>${tail}</div>`;
  }).join('');
  const done = importQueue.filter((x) => x.done).length;
  $('#imp-status').textContent = importQueue.length ? `Готово: ${done} из ${importQueue.length}` : 'Файлы проверяются сразу после загрузки';
  $('#imp-open').disabled = !done;
  $$('[data-dup]', q).forEach((b) => b.onclick = () => {
    const it = importQueue.find((x) => x.id === b.dataset.q);
    it.dupDone = { version: `Сохранено как версия ${ed.version + 1} договора № 124-А`, separate: 'Сохранено отдельным документом', skip: 'Пропущено' }[b.dataset.dup];
    if (b.dataset.dup === 'separate') addImported(it);
    renderQueue();
  });
  $$('[data-open-real]', q).forEach((b) => b.onclick = () => { closeModal(); openRealDoc(+b.dataset.openReal); });
  $$('[data-link]', q).forEach((b) => b.onclick = () => { const it = importQueue.find((x) => x.id === b.dataset.q); it.linkDone = b.dataset.link === 'yes'; it.link = null; renderQueue(); });
}

/* =========================================================================
   ЭКСПОРТ
   ========================================================================= */
function openExport() {
  const st = { fmt: 'DOCX', variant: 'clean' };
  const real = !!ed.real;
  const title = real ? ed.real.title : DEMO.contract.title;
  const variants = [['clean', 'Чистовик', 'Итоговый текст без пометок'], ['markup', 'С правками и комментариями', 'Режим рецензирования Word: правки можно принять у получателя'],
    ['protocol', 'Протокол разногласий', 'Таблица «редакция контрагента — наша редакция — обоснование»'], ['report', 'Отчёт о проверке', 'Список найденных ошибок с объяснениями']]
    .filter(([k]) => !real || k === 'clean');
  const disabledFmt = real ? ['ODT', 'RTF'] : [];
  const fname = () => `${title}${{ clean: '', markup: ' (с правками)', protocol: ' — протокол разногласий', report: ' — отчёт о проверке' }[st.variant]}.${st.fmt.toLowerCase()}`;
  const draw = () => {
    openModal(`<div class="modal-head"><h2>Экспорт документа</h2><button class="icon-btn" data-close>${icon('x')}</button></div>
      <div class="modal-body">
        <div><div class="label" style="margin-bottom:8px">Формат</div><div class="formats">
          ${[['DOCX', 'Word'], ['PDF', 'для печати'], ['ODT', 'LibreOffice'], ['RTF', 'универсальный'], ['TXT', 'только текст']].map(([f, s]) => `<button class="fmt ${st.fmt === f ? 'on' : ''}" data-fmt="${f}" ${disabledFmt.includes(f) ? 'disabled style="opacity:.4;cursor:default" title="Будет доступен позже"' : ''}>${f}<small>${s}</small></button>`).join('')}</div></div>
        <div><div class="label" style="margin-bottom:8px">Что выгрузить</div><div class="variants">
          ${variants.map(([k, n, s]) => `<label class="variant ${st.variant === k ? 'on' : ''}"><input type="radio" name="v" data-var="${k}" ${st.variant === k ? 'checked' : ''}><span><b>${n}</b><small>${s}</small></span></label>`).join('')}</div></div>
        <div class="form-grid"><div class="form-row"><label>Версия</label><select>${real ? `<option>Текущее содержимое редактора (версия ${ed.real.current}${isDirty() ? ' + несохранённые правки' : ''})</option>`
          : DEMO.versions.slice().reverse().map((v) => `<option>${v.name} · ${v.source.toLowerCase()}${v.current ? ' (текущая)' : ''}</option>`).join('')}</select></div>
          <div class="form-row"><label>Папка</label><input value="Документы\\Documentum\\Экспорт"></div>
          <div class="form-row full"><label>Имя файла</label><input id="exp-name" value="${esc(fname())}"></div></div>
        ${st.variant === 'clean' && pending().length ? `<div class="qi-note">${icon('alert')}<span>В документе ${pending().length} ${plural(pending().length, 'непринятая правка', 'непринятые правки', 'непринятых правок')}. В чистовик попадёт текст без них.</span></div>` : ''}
      </div>
      <div class="modal-foot"><span class="muted">${st.fmt === 'PDF' ? 'Оформление сохраняется как на экране' : 'Шрифты, таблицы и нумерация сохраняются'}</span><div class="spacer"></div>
        <button class="btn" data-close>Отмена</button><button class="btn primary" id="exp-go">${icon('download')}Экспортировать</button></div>`);
    $$('[data-fmt]').forEach((b) => b.onclick = () => { if (b.disabled) return; st.fmt = b.dataset.fmt; draw(); });
    $$('[data-var]').forEach((r) => r.onchange = () => { st.variant = r.dataset.var; draw(); });
    $('#exp-go').onclick = async () => {
      const name = $('#exp-name').value;
      $('#exp-go').disabled = true; $('#exp-go').textContent = 'Сохраняю…';
      if (real) {
        try {
          const msg = await realExport(st.fmt, name);
          closeModal();
          if (msg) toast(msg);
        } catch (e) {
          toast('Не удалось экспортировать: ' + e.message);
          $('#exp-go').disabled = false; $('#exp-go').textContent = 'Экспортировать';
        }
        return;
      }
      await sleep(700);
      closeModal();
      toast(`Сохранено: ${name}`, 'Показать в папке', () => toast('Открыта папка Документы\\Documentum\\Экспорт'));
    };
  };
  draw();
}

/* -------------------------------------------------------------------------
   Ответ ассистента «Кратко: <документ>» — из карточки в реестре
   ------------------------------------------------------------------------- */
function briefAnswer(q) {
  const title = q.replace(/^кратко:\s*/i, '');
  const d = DEMO.docs.find((x) => x.title === title);
  if (!d) return null;
  return {
    steps: [`Читаю документ «${title}»`, 'Сверяю с карточкой и результатами проверки'],
    async render(el) {
      const facts = [d.type + ' от ' + d.date, d.cp !== '—' ? 'контрагент — ' + d.cp : '', d.amount ? 'сумма — ' + rub(d.amount) : '', 'статус — ' + d.status.toLowerCase()].filter(Boolean).join(', ');
      const text = `${facts.charAt(0).toUpperCase() + facts.slice(1)}. ${d.text || 'Текст документа ещё индексируется.'} Проверка: ${checkLabel(d).toLowerCase()}${issueText(d) ? ' — ' + issueText(d).charAt(0).toLowerCase() + issueText(d).slice(1) : ''}.`;
      const s = document.createElement('div');
      s.className = 'summary';
      el.appendChild(s);
      await typeInto(s, text, 12);
      el.insertAdjacentHTML('beforeend', `<div class="actions-row"><button class="btn small" data-doc="${d.id}">${icon('file')}Открыть документ</button></div>`);
    },
  };
}

// Стартовый экран можно задать параметрами: ?screen=editor, ?screen=assistant&ask=Утверждённые бюджеты
// (удобно для презентации и снимков экрана)
(() => {
  const qs = new URLSearchParams(location.search);
  if (qs.get('still') === '1') document.documentElement.classList.add('no-anim');   // для снимков экрана
  const screen = qs.get('screen');
  go(['overview', 'registry', 'editor', 'search', 'assistant', 'settings', 'versions'].includes(screen) ? screen : 'overview');
  const questions = qs.getAll('ask');
  if (screen === 'assistant' && questions.length) {
    newChat();
    questions.reduce((p, q) => p.then(() => ask(q)), Promise.resolve());
  }
})();
