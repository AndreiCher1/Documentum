/* =========================================================================
   Настоящие документы: связь с сервером Documentum (Java, порт 8085).
   Реестр из базы, импорт файлов, редактор с автосохранением, версии, экспорт.
   Демо-данные продолжают работать, если сервер не запущен.
   ========================================================================= */
'use strict';

/* -------------------------------------------------------------------------
   Клиент API
   ------------------------------------------------------------------------- */
const API = (() => {
  const base = new URLSearchParams(location.search).get('api') || store.get('apiBase') || 'http://127.0.0.1:8085';
  let online = null;
  let outdated = false;     // сервер запущен, но старой версии — без API редактора
  const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  async function req(path, opts = {}, timeout = 120000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const r = await fetch(base + path, { ...opts, signal: ctrl.signal });
      if (!r.ok) {
        let msg = `Ошибка сервера (${r.status})`;
        try { const j = await r.json(); msg = j.message || j.detail || msg; } catch { /* не JSON */ }
        throw new Error(msg);
      }
      return r;
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('Сервер не ответил вовремя');
      if (e instanceof TypeError) { online = false; throw new Error('Сервер Documentum недоступен'); }
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    base,
    get online() { return online; },
    get outdated() { return outdated; },
    // Проверяем именно API редактора: старый сервер отвечает на /api/health, но не умеет работать с документами
    async check() {
      try {
        await req('/api/editor/documents', {}, 3000);
        online = true; outdated = false;
      } catch {
        online = false;
        try { await req('/api/health', {}, 2500); outdated = true; } catch { outdated = false; }
        online = false;
      }
      return online;
    },
    statusText() {
      if (online) return 'Файлы сохраняются в базу на этом компьютере';
      if (outdated) return 'Сервер Documentum старой версии — закройте приложение и запустите обновлённую сборку. Пока файлы показываются в демонстрационном режиме.';
      return 'Сервер не запущен — файлы будут показаны в демонстрационном режиме';
    },
    list: async () => (await req('/api/editor/documents')).json(),
    importFile: async (file) => { const fd = new FormData(); fd.append('file', file); return (await req('/api/editor/documents', { method: 'POST', body: fd }, 600000)).json(); },
    open: async (id) => (await req(`/api/editor/documents/${id}`, {}, 600000)).json(),
    draft: (id, html) => req(`/api/editor/documents/${id}/draft`, json('PUT', { html })),
    saveVersion: async (id, html, description, source) => (await req(`/api/editor/documents/${id}/versions`, json('POST', { html, description, source }))).json(),
    version: async (id, n) => (await req(`/api/editor/documents/${id}/versions/${n}`)).json(),
    rename: (id, title) => req(`/api/editor/documents/${id}`, json('PATCH', { title })),
    search: async (params) => (await req(`/api/editor/documents/search?${params}`, {}, 30000)).json(),
    checkDoc: async (id, html, deep = false) => (await req(`/api/editor/documents/${id}/check`, json('POST', { html, deep }), deep ? 900000 : 60000)).json(),
    exportDocx: async (id, html) => (await req(`/api/editor/documents/${id}/export/docx`, json('POST', { html }), 120000)).blob(),
    remove: (id) => req(`/api/documents/${id}`, { method: 'DELETE' }),
    // языковая модель на процессоре может отвечать долго — ждём до 5 минут
    assistant: async (question, context, docId = null) => (await req('/api/editor/documents/assistant', json('POST', { question, context, docId }), 300000)).json(),
    assistantStatus: async () => (await req('/api/editor/documents/assistant/status', {}, 5000)).json(),
  };
})();

/* -------------------------------------------------------------------------
   Реестр из базы
   ------------------------------------------------------------------------- */
const REAL = { docs: [], loaded: false, loading: null };

const TYPE_UI = {
  CONTRACT: ['Договор', 'Договоры'], SUPPLEMENTARY_AGREEMENT: ['Доп. соглашение', 'Договоры'], CLAIM: ['Претензия', 'Договоры'],
  ORDER: ['Приказ', 'Приказы'], BUDGET: ['Бюджет', 'Бюджеты'], MEMO: ['Служебная записка', 'Служебные записки'],
  REGULATION: ['Регламент', 'Регламенты'], TECH_SPEC: ['ТЗ', 'ТЗ'], INVOICE: ['Счёт', 'Счета и акты'], ACT: ['Акт', 'Счета и акты'],
  WAYBILL: ['Накладная', 'Счета и акты'],
};
const showDemo = () => store.get('showDemo') !== 'off';

function fmtDate(iso) { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString('ru-RU'); }
function relTime(iso) {
  const d = new Date(iso);
  const mins = Math.round((Date.now() - d) / 60000);
  if (mins < 1) return 'Только что';
  if (mins < 60) return `${mins} мин назад`;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  if (d >= today) return `Сегодня, ${time}`;
  if (d >= today - 864e5) return `Вчера, ${time}`;
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}

function mapReal(it) {
  const [type, folder] = TYPE_UI[it.documentType] || ['Прочее', 'Прочее'];
  if (!DEMO.folders.includes(folder)) DEMO.folders.push(folder);
  const parties = it.counterparties || [];
  return {
    id: 'r' + it.id, realId: it.id, real: true, type, folder, title: it.title,
    // дата и контрагент — из текста документа (если найдены), иначе дата загрузки
    date: fmtDate(it.docDate || it.createdAt), cp: parties[0] || '—', parties, amount: it.amount || 0,
    number: it.number, validUntil: it.validUntil,
    status: 'Проект', issues: it.checkedAt ? [it.checkCritical || 0, it.checkWarning || 0, it.checkInfo || 0] : null,
    modified: relTime(it.updatedAt), tags: [], text: '', version: it.currentVersion, filename: it.originalFilename,
  };
}

async function refreshReal() {
  if (REAL.loading) return REAL.loading;
  REAL.loading = (async () => {
    if (await API.check()) {
      try { REAL.docs = (await API.list()).map(mapReal); } catch (e) { console.warn(e); }
    }
    REAL.loaded = true;
    REAL.loading = null;
  })();
  return REAL.loading;
}

/* -------------------------------------------------------------------------
   Редактор: настоящий документ
   ------------------------------------------------------------------------- */
// HTML без служебных пометок: непринятые правки возвращаются к исходному тексту,
// принятые и отклонённые становятся обычным текстом
function cleanHTML(root = page) {
  const c = root.cloneNode(true);
  c.querySelectorAll('.sug').forEach((s) => { const d = s.querySelector('del'); s.replaceWith(...(d ? d.childNodes : [])); });
  c.querySelectorAll('.note, [data-rid], mark.search-hit').forEach((s) => s.replaceWith(...s.childNodes));
  // пустые теги начертания, оставшиеся после пометок, не должны считаться изменением текста
  c.querySelectorAll('b,i,u,s,strong,em,span').forEach((el) => { if (!el.textContent && !el.querySelector('br,img')) el.remove(); });
  c.normalize();
  c.querySelectorAll('[data-bid]').forEach((el) => el.removeAttribute('data-bid'));
  c.querySelectorAll('.flash,.hover,.active').forEach((el) => el.classList.remove('flash', 'hover', 'active'));
  c.querySelectorAll('[class=""]').forEach((el) => el.removeAttribute('class'));
  return c.innerHTML;
}

// focus — место из поиска: { block, start, end } — документ откроется на нём с подсветкой
async function openRealDoc(id, focus = null) {
  if (!ed.real) { ed.demoHTML = page.innerHTML; ed.demoTitle = $('#doc-title').textContent; }
  go('editor');
  page.innerHTML = '<p style="text-indent:0;color:#888">Открываю документ…</p>';
  try {
    const doc = await API.open(id);
    // База для «есть ли изменения» — последняя сохранённая версия (черновик может от неё отличаться)
    const tmp = document.createElement('div');
    tmp.innerHTML = doc.hasUnsavedDraft ? (await API.version(id, doc.currentVersion)).html : doc.html;
    const base = cleanHTML(tmp);
    ed.real = { id, title: doc.title, typeName: doc.documentTypeName, filename: doc.originalFilename, size: doc.fileSize,
      created: doc.createdAt, versions: doc.versions, current: doc.currentVersion, baseHTML: base, cache: { [doc.currentVersion]: base },
      fields: doc.fields || null };
    page.innerHTML = doc.html || '<p><br></p>';
    if (doc.lastCheck) setFindings(doc.lastCheck);
    $('#doc-title').textContent = doc.title;
    crumbs(['Документы', TYPE_UI[doc.documentType]?.[1] || 'Прочее', doc.title]);
    setSaveState(doc.hasUnsavedDraft ? 'Черновик восстановлен' : 'Сохранено');
    ed.msgEdited = false;
    renderReview();
    if (focus) showFound(focus);
    if (doc.warnings?.length) toast(doc.warnings.join(' '));
  } catch (e) {
    page.innerHTML = `<p style="text-indent:0;color:#b42318">Не удалось открыть документ: ${esc(e.message)}</p>`;
  }
}

function restoreDemo() {
  if (!ed.real) return;
  ed.real = null;
  page.innerHTML = ed.demoHTML;
  $('#doc-title').textContent = ed.demoTitle;
  $('#save-state').innerHTML = `${icon('check')}Сохранено · версия ${ed.version}`;
  renderReview();
}

function setSaveState(text) {
  $('#save-state').innerHTML = `${icon('check')}${text} · версия ${ed.real.current}`;
}

const isDirty = () => ed.real && cleanHTML() !== ed.real.baseHTML;

function realOnInput() {
  $('#save-state').textContent = 'Сохраняется…';
  clearTimeout(ed.draftT);
  ed.draftT = setTimeout(async () => {
    try { await API.draft(ed.real.id, cleanHTML()); setSaveState(isDirty() ? 'Черновик сохранён' : 'Сохранено'); }
    catch (e) { $('#save-state').textContent = 'Не сохранено: ' + e.message; }
    realCommitBar();
  }, 1200);
}

// Подсветка найденного места: слово в абзаце помечается, абзац прокручивается в центр
function showFound({ block, start, end }) {
  page.querySelectorAll('mark.search-hit').forEach((m) => m.replaceWith(...m.childNodes));
  const el = pageBlocks()[block];
  if (!el) return;
  const range = start != null && end > start ? rangeInText(el, start, end) : null;
  if (range) {
    try {
      const mark = document.createElement('mark');
      mark.className = 'search-hit';
      mark.append(range.extractContents());
      range.insertNode(mark);
    } catch { /* пересекается с пометкой проверки — просто прокрутим */ }
  }
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
  // подсветка снимается при первом действии в документе
  const clear = () => { page.querySelectorAll('mark.search-hit').forEach((m) => m.replaceWith(...m.childNodes)); page.normalize(); };
  page.addEventListener('mousedown', clear, { once: true });
  page.addEventListener('keydown', clear, { once: true });
}

function realLeft(tab) {
  const body = $('#left-body');
  if (tab === 'outline') {
    pageBlocks().forEach((el, i) => { el.dataset.bid = 'rb' + i; });     // те же метки, что у находок проверки
    const heads = $$('h1, h2, h3', page);
    body.innerHTML = heads.length ? `<div class="outline">${heads.map((h) =>
      `<button class="outline-item ${h.tagName === 'H1' ? 'title' : ''}" data-go="${h.dataset.bid}" style="padding-left:${8 + (+h.tagName[1] - 1) * 10}px">${esc(h.textContent.trim().slice(0, 80))}</button>`).join('')}</div>`
      : `<div class="empty" style="padding:24px 16px"><span style="font-size:13px">В документе нет заголовков. Задайте их кнопкой «Стиль абзаца» на панели.</span></div>`;
  } else {
    const r = ed.real;
    const size = r.size > 1e6 ? (r.size / 1e6).toFixed(1).replace('.', ',') + ' МБ' : Math.max(1, Math.round(r.size / 1e3)) + ' КБ';
    const f = r.fields || {};
    const field = (k, v, cls = '') => `<div class="field"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`;
    const fromText = [
      field('Номер', esc(f.number || '—')),
      field('Дата документа', f.date ? fmtDate(f.date) : '—'),
      field('Контрагенты', f.counterparties?.length ? f.counterparties.map(esc).join('<br>') : '—'),
      field('Сумма', f.amount ? rub(f.amount) : '—'),
      field('Действует до', f.validUntil ? fmtDate(f.validUntil) : '—'),
      ...(f.inns || []).map((i) => field('ИНН', `${i.value}${i.valid ? '' : ' — неверная контрольная сумма'}`, i.valid ? '' : 'bad')),
    ].join('');
    body.innerHTML = `<div class="label" style="padding:12px 16px 0">Из текста документа</div><div class="fields">${fromText}</div>
      <div class="label" style="padding:4px 16px 0">Файл и версии</div>
      <div class="fields">${[['Тип', r.typeName], ['Исходный файл', r.filename], ['Размер файла', size], ['Загружен', fmtDate(r.created)],
      ['Текущая версия', String(r.current)], ['Всего версий', String(r.versions.length)]].map(([k, v]) => field(k, esc(v || '—'))).join('')}</div>`;
  }
}

function realReview() {
  $('#review-summary').innerHTML = `<div class="verdict"><span class="verdict-badge" style="background:var(--bg-active);color:var(--text-muted)">Не проверен</span></div>`;
  $('#cards').innerHTML = `<div class="empty"><div class="big" style="background:var(--bg-active);color:var(--text-muted)">${icon('shield', '')}</div>
    <b>Проверка ещё не выполнялась</b><span style="font-size:13px">Система найдёт ошибки в реквизитах, датах, суммах, нумерации и оформлении и предложит правки.</span>
    <button class="btn primary" id="first-check">${icon('shield')}Проверить документ</button></div>`;
  $('#first-check').onclick = realRunCheck;
  $('#cnt-review').textContent = '0';
  const pill = $('#doc-verdict');
  pill.className = 'status-pill';
  pill.textContent = ed.real.typeName;
  realCommitBar();
  renderStatus();
  renderLeft();
}

// Принятые, но ещё не сохранённые в версию правки этого документа
const acceptedHere = () => uncommitted().filter((id) => id.startsWith(`r${ed.real.id}-`) && ed.res[id].status === 'accepted');

function realCommitBar() {
  const bar = $('#commit-bar');
  bar.hidden = !isDirty();
  if (bar.hidden) return;
  const changed = alignBlocks(blocksOf(ed.real.baseHTML), blocksOf(cleanHTML())).filter((r) => r.kind !== 'same').length;
  const acc = acceptedHere();
  $('#commit-title').textContent = acc.length
    ? `Принято правок: ${acc.length} — сохранить как версию ${ed.real.current + 1}?`
    : `Есть изменения — сохранить как версию ${ed.real.current + 1}?`;
  if (!ed.msgEdited) $('#commit-msg').value = acc.length ? commitMessage(acc) : `Ручная правка: ${changed} ${plural(changed, 'фрагмент', 'фрагмента', 'фрагментов')}`;
}

/* -------------------------------------------------------------------------
   Проверка по правилам: находки → пометки в тексте
   ------------------------------------------------------------------------- */
const BLOCK_SEL = 'h1,h2,h3,p,li,td,th';
// Те же блоки, что выделяет сервер: элементы-абзацы, не вложенные в другой абзац
const pageBlocks = () => $$(BLOCK_SEL, page).filter((el) => !el.parentElement.closest(BLOCK_SEL));

function setFindings(check) {
  const prefix = `r${ed.real.id}-`;
  Object.keys(ed.res).filter((k) => k.startsWith(prefix)).forEach((k) => { delete ed.res[k]; ed.committed.delete(k); });
  ed.active = null;
  ed.filter = 'all';
  ed.real.checkedAt = check.checkedAt;
  ed.real.findings = (check.findings || []).map((f) => ({
    id: prefix + f.id, severity: f.severity, category: f.category, title: f.title, why: f.why, where: f.where,
    block: f.block != null ? 'rb' + f.block : null, before: f.quote, after: f.replacement, noteOnly: f.replacement == null,
    ai: !!f.ai, source: f.source || null,
    raw: f,
  }));
  applyMarks();
}

// Ставит пометки в текст. Позиции считаются по тексту блока; если текст уже другой, ищем цитату.
function applyMarks() {
  const blocks = pageBlocks();
  blocks.forEach((el, i) => { el.dataset.bid = 'rb' + i; });
  const list = ed.real.findings.filter((f) => f.raw.block != null && f.raw.start != null)
    .sort((a, b) => b.raw.block - a.raw.block || b.raw.start - a.raw.start);   // с конца, чтобы не сдвигать позиции
  for (const f of list) {
    const el = blocks[f.raw.block];
    if (!el) continue;
    const text = el.textContent;
    let start = f.raw.start;
    if (text.slice(start, f.raw.end) !== f.raw.quote) {
      start = text.indexOf(f.raw.quote);
      if (start < 0 || !f.raw.quote) continue;
    }
    const range = rangeInText(el, start, start + f.raw.quote.length);
    if (!range) continue;
    const frag = range.extractContents();
    const span = document.createElement('span');
    span.dataset.sid = f.id;
    if (f.noteOnly) {
      span.className = 'note';
      span.append(frag);
    } else {
      span.className = 'sug';
      span.contentEditable = 'false';
      const del = document.createElement('del');
      del.append(frag);
      const ins = document.createElement('ins');
      ins.textContent = f.after;
      span.append(del, ins);
    }
    range.insertNode(span);
  }
}

function rangeInText(root, start, end) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  let pos = 0, node, startSet = false;
  while ((node = walker.nextNode())) {
    const len = node.data.length;
    // начало ставим в следующий текстовый узел, если позиция на стыке: так выделение не захватывает соседний тег целиком
    if (!startSet && start < pos + len) { range.setStart(node, start - pos); startSet = true; }
    if (startSet && end <= pos + len) { range.setEnd(node, end - pos); return range; }
    pos += len;
  }
  return null;
}

async function realRunCheck(quiet = false, deep = false) {
  if (quiet !== true) quiet = false;          // при вызове из обработчика клика сюда приходит событие
  if (deep !== true) deep = false;
  switchRightTab('review');
  const box = $('#review-summary');
  box.innerHTML = `<div class="steps"><div class="step"><span class="spin"></span>Правила: реквизиты, даты, суммы, нумерация, риски</div>
    <div class="step"><span class="spin"></span>Сверка с другими документами базы</div>
    ${deep ? '<div class="step"><span class="spin"></span>Языковая модель читает документ — это может занять одну-две минуты</div>' : ''}</div>`;
  $('#cards').innerHTML = '';
  try {
    const html = cleanHTML();
    const check = await API.checkDoc(ed.real.id, html, deep);
    ed.real.semantic = deep ? (check.semantic || { available: false }) : null;
    page.innerHTML = html;
    setFindings(check);
    ed.msgEdited = false;
    renderReview();
    refreshReal();
    const n = ed.real.findings.length;
    const sem = ed.real.semantic;
    if (deep && !sem.available) toast('Языковая модель не подключена — выполнена проверка по правилам и сверка с базой');
    else if (deep) toast(`Модель прочитала ${sem.chunks < sem.total ? `начало документа (${sem.chunks} из ${sem.total} частей)` : 'документ целиком'}: находок — ${sem.found}`);
    else if (!quiet) toast(n ?`Проверка завершена: ${n} ${plural(n, 'находка', 'находки', 'находок')}` : 'Проверка завершена: замечаний нет');
  } catch (e) {
    toast('Проверка не выполнена: ' + e.message);
    renderReview();
  }
}

async function realCommit() {
  const btn = $('#commit-btn');
  btn.disabled = true;
  try {
    const html = cleanHTML();
    const acc = acceptedHere();
    const meta = await API.saveVersion(ed.real.id, html, $('#commit-msg').value.trim(), acc.length ? 'REVIEW' : 'MANUAL');
    acc.forEach((id) => ed.committed.add(id));
    ed.real.versions.unshift(meta);
    ed.real.current = meta.number;
    ed.real.baseHTML = html;
    ed.real.cache[meta.number] = html;
    ed.msgEdited = false;
    setSaveState('Сохранено');
    realCommitBar();
    renderLeft();
    await realRunCheck(true);                 // перепроверяем сохранённый текст: счётчики в реестре станут актуальными
    toast(`Сохранено как версия ${meta.number}`, 'Сравнить с прошлой', () => { rcmp.a = meta.number - 1; rcmp.b = meta.number; go('versions'); });
  } catch (e) {
    toast('Не удалось сохранить версию: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

$('#doc-title').addEventListener('blur', async () => {
  if (!ed.real) return;
  const t = $('#doc-title').textContent.trim();
  if (!t || t === ed.real.title) { $('#doc-title').textContent = ed.real.title; return; }
  try { await API.rename(ed.real.id, t); ed.real.title = t; refreshReal(); toast('Документ переименован'); }
  catch (e) { toast('Не удалось переименовать: ' + e.message); }
});
$('#doc-title').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } });

/* -------------------------------------------------------------------------
   Сравнение версий для любых документов
   ------------------------------------------------------------------------- */
const rcmp = { a: null, b: null };

function blocksOf(html) {
  const d = document.createElement('div');
  d.innerHTML = html || '';
  const out = [];
  d.querySelectorAll('h1,h2,h3,p,li,tr').forEach((el) => {
    if (el.closest('tr') && el.tagName !== 'TR') return;          // ячейки берём строкой целиком
    const text = (el.tagName === 'TR' ? [...el.children].map((c) => c.textContent.trim()).join(' | ') : el.textContent).replace(/\s+/g, ' ').trim();
    if (text) out.push({ text, h: /^H/.test(el.tagName) });
  });
  return out;
}

// Выравнивание абзацев двух версий: совпадающие, изменённые, добавленные, удалённые
function alignBlocks(A, B) {
  const n = A.length, m = B.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = A[i].text === B[j].text ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const rows = [];
  let i = 0, j = 0;
  const dels = [], adds = [];
  // Удалённый и добавленный абзацы считаем «изменённым», только если они похожи по словам
  const sim = (x, y) => {
    const a = new Set(x.toLowerCase().split(/\s+/)), b = new Set(y.toLowerCase().split(/\s+/));
    let common = 0;
    a.forEach((w) => { if (b.has(w)) common++; });
    return common / Math.max(1, Math.min(a.size, b.size));
  };
  const flush = () => {
    const used = new Set();
    const match = adds.map((b) => {
      let best = -1, score = 0.4;
      dels.forEach((a, k) => { if (!used.has(k)) { const s = sim(a.text, b.text); if (s > score) { score = s; best = k; } } });
      if (best >= 0) used.add(best);
      return best;
    });
    dels.forEach((a, k) => { if (!used.has(k)) rows.push({ kind: 'del', a, b: null }); });
    adds.forEach((b, k) => rows.push(match[k] >= 0 ? { kind: 'mod', a: dels[match[k]], b } : { kind: 'add', a: null, b }));
    dels.length = 0;
    adds.length = 0;
  };
  while (i < n && j < m) {
    if (A[i].text === B[j].text) { flush(); rows.push({ kind: 'same', a: A[i], b: B[j] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) dels.push(A[i++]);
    else adds.push(B[j++]);
  }
  while (i < n) dels.push(A[i++]);
  while (j < m) adds.push(B[j++]);
  flush();
  return rows;
}

async function versionHTML(n) {
  if (n === 'draft') return cleanHTML();
  if (ed.real.cache[n] == null) ed.real.cache[n] = (await API.version(ed.real.id, n)).html;
  return ed.real.cache[n];
}

async function realVersions() {
  const r = ed.real;
  crumbs(['Документы', r.title, 'История версий']);
  const dirty = isDirty();
  if (rcmp.b == null || (rcmp.b !== 'draft' && !r.versions.some((v) => v.number === rcmp.b))) rcmp.b = dirty ? 'draft' : r.current;
  if (rcmp.a == null || !r.versions.some((v) => v.number === rcmp.a)) rcmp.a = rcmp.b === 'draft' ? r.current : Math.max(1, r.current - 1);
  const SRC = { IMPORT: 'Импорт', MANUAL: 'Ручная правка', REVIEW: 'Принятые исправления', REVERT: 'Возврат' };
  const item = (num, name, meta, desc, current) => `<div class="ver ${current ? 'current' : ''} ${rcmp.a === num ? 'sel-a' : ''} ${rcmp.b === num ? 'sel-b' : ''}" data-rver="${num}">
    <span class="line"></span><span class="node"></span><div><div class="ver-name">${name}${current ? '<span class="tag ai">текущая</span>' : ''}${rcmp.a === num ? '<span class="ab a">БЫЛО</span>' : rcmp.b === num ? '<span class="ab b">СТАЛО</span>' : ''}</div>
    <div class="ver-meta">${meta}</div><div class="ver-desc">${esc(desc || '')}</div></div></div>`;
  $('#timeline').innerHTML = (dirty ? item('draft', 'Несохранённые изменения', 'черновик', 'То, что сейчас в редакторе', false) : '') +
    r.versions.map((v) => item(v.number, 'Версия ' + v.number, `${new Date(v.createdAt).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })} · ${SRC[v.source] || v.source}`, v.description, v.number === r.current)).join('');
  $('#ext-docs').innerHTML = `<div class="faint" style="font-size:12.5px;padding:0 4px">Сравнение с редакцией контрагента — загрузите её как отдельный документ.</div>`;

  const name = (n) => (n === 'draft' ? 'Несохранённые изменения' : 'Версия ' + n);
  $('#cmp-a').textContent = $('#col-a-name').textContent = name(rcmp.a);
  $('#cmp-b').textContent = $('#col-b-name').textContent = name(rcmp.b);
  $('#col-a').innerHTML = $('#col-b').innerHTML = '<div class="blk">Загрузка…</div>';
  const [ha, hb] = await Promise.all([versionHTML(rcmp.a), versionHTML(rcmp.b)]);
  const rows = alignBlocks(blocksOf(ha), blocksOf(hb));
  let la = '', lb = '';
  cmp.changed = [];
  const points = [];
  rows.forEach((row, k) => {
    const key = 'c' + k;
    const h = (row.a || row.b).h ? ' h' : '';
    if (row.kind === 'same') {
      la += `<div class="blk${h}" data-cb="${key}">${esc(row.a.text)}</div>`;
      lb += `<div class="blk${h}" data-cb="${key}">${esc(row.b.text)}</div>`;
      return;
    }
    cmp.changed.push(key);
    if (row.kind === 'mod') {
      const [x, y] = wordDiff(row.a.text, row.b.text);
      la += `<div class="blk changed${h}" data-cb="${key}">${x}</div>`;
      lb += `<div class="blk changed${h}" data-cb="${key}">${y}</div>`;
      const aw = row.a.text.split(' '), bw = row.b.text.split(' ');
      const rem = aw.filter((w) => !bw.includes(w)).join(' '), add = bw.filter((w) => !aw.includes(w)).join(' ');
      points.push(`«${row.b.text.slice(0, 40)}…»: ${rem ? `«${rem.slice(0, 60)}» → ` : 'добавлено '}«${add.slice(0, 60) || '—'}»`);
    } else if (row.kind === 'del') {
      la += `<div class="blk changed${h}" data-cb="${key}"><span class="d">${esc(row.a.text)}</span></div>`;
      lb += `<div class="blk changed${h}" data-cb="${key}">&nbsp;</div>`;
      points.push(`Удалён фрагмент: «${row.a.text.slice(0, 80)}${row.a.text.length > 80 ? '…' : ''}»`);
    } else {
      la += `<div class="blk changed${h}" data-cb="${key}">&nbsp;</div>`;
      lb += `<div class="blk changed${h}" data-cb="${key}"><span class="a">${esc(row.b.text)}</span></div>`;
      points.push(`Добавлен фрагмент: «${row.b.text.slice(0, 80)}${row.b.text.length > 80 ? '…' : ''}»`);
    }
  });
  $('#col-a').innerHTML = la || '<div class="blk faint">Пусто</div>';
  $('#col-b').innerHTML = lb || '<div class="blk faint">Пусто</div>';
  $('#ai-summary').innerHTML = `<div class="answer-head"><span class="ai-mark">${icon('history')}</span>Сводка изменений · ${cmp.changed.length} ${plural(cmp.changed.length, 'фрагмент', 'фрагмента', 'фрагментов')}</div>
    <ul>${(points.length ? points.slice(0, 6) : [rcmp.a === rcmp.b ? 'Выбрана одна и та же версия.' : 'Версии совпадают.']).map((p) => `<li>${esc(p)}</li>`).join('')}${points.length > 6 ? `<li>…и ещё ${points.length - 6}</li>` : ''}</ul>`;
  $('#revert-btn').disabled = rcmp.a === 'draft' || rcmp.a === rcmp.b;
  cmp.idx = 0;
  focusChange(0, false);
}

$('#screen-versions').addEventListener('click', (e) => {
  if (!ed.real) return;
  const v = e.target.closest('[data-rver]');
  if (!v) return;
  const id = v.dataset.rver === 'draft' ? 'draft' : +v.dataset.rver;
  if (e.shiftKey) { if (id !== 'draft') rcmp.a = id; } else rcmp.b = id;
  realVersions();
});

async function realRevert() {
  const n = rcmp.a;
  try {
    const html = await versionHTML(n);
    const meta = await API.saveVersion(ed.real.id, html, `Возврат к версии ${n}`, 'REVERT');
    ed.real.versions.unshift(meta);
    ed.real.current = meta.number;
    page.innerHTML = html;
    ed.real.baseHTML = cleanHTML();          // в том же виде, в каком редактор сериализует текст
    ed.real.cache[meta.number] = ed.real.baseHTML;
    setSaveState('Сохранено');
    rcmp.a = meta.number - 1; rcmp.b = meta.number;
    realVersions();
    toast(`Создана версия ${meta.number} — возврат к версии ${n}. Ничего не удалено.`);
  } catch (e) {
    toast('Не удалось вернуть версию: ' + e.message);
  }
}

/* -------------------------------------------------------------------------
   Экспорт
   ------------------------------------------------------------------------- */
function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function printableHTML(title, body) {
  return `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>${esc(title)}</title><style>
    @page { size: A4; margin: 20mm 15mm 20mm 30mm; }
    body { font: 12pt/1.4 "Times New Roman", serif; color: #000; margin: 0; text-align: justify; }
    h1 { font-size: 14pt; text-align: center; } h2, h3 { font-size: 12pt; text-align: center; }
    p { margin: 0 0 4pt; text-indent: 1.25cm; } li p { text-indent: 0; }
    table { border-collapse: collapse; width: 100%; } td, th { border: 1px solid #000; padding: 3pt 5pt; vertical-align: top; }
    .ocr-low { background: none; }
  </style></head><body>${body}</body></html>`;
}

async function realExport(fmt, name) {
  const html = cleanHTML();
  if (fmt === 'DOCX') {
    downloadBlob(await API.exportDocx(ed.real.id, html), name);
    return 'Файл сохранён';
  }
  if (fmt === 'TXT') {
    const text = blocksOf(html).map((b) => b.text).join('\r\n\r\n');
    downloadBlob(new Blob(['﻿' + text], { type: 'text/plain;charset=utf-8' }), name);
    return 'Файл сохранён';
  }
  if (fmt === 'PDF') {
    const doc = printableHTML(ed.real.title, html);
    if (window.api?.exportPdf) {
      const r = await window.api.exportPdf(doc, name);
      return r?.ok ? `PDF сохранён: ${r.path}` : null;
    }
    // В браузере — системная печать с сохранением в PDF
    const f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;width:0;height:0;border:0';
    document.body.appendChild(f);
    f.contentDocument.open(); f.contentDocument.write(doc); f.contentDocument.close();
    f.contentWindow.focus(); f.contentWindow.print();
    setTimeout(() => f.remove(), 2000);
    return null;
  }
  throw new Error(`Формат ${fmt} будет доступен позже`);
}

/* -------------------------------------------------------------------------
   Импорт настоящих файлов
   ------------------------------------------------------------------------- */
async function realImport(item) {
  const ticker = setInterval(() => { if (item.stage < 3) { item.stage++; renderQueue(); } }, 800);
  try {
    const doc = await API.importFile(item.file);
    item.realDoc = doc;
    item.type = doc.documentTypeName;
    item.warnings = doc.warnings || [];
    await refreshReal();
  } catch (e) {
    item.error = e.message;
  }
  clearInterval(ticker);
  item.stage = 5;
  item.done = true;
  renderQueue();
}

// Сведения о сервере для экрана «О программе»
async function serverStatusHTML() {
  const ok = await API.check();
  return `<span class="k">Сервер документов</span><span class="svc"><span class="sev-dot ${ok ? 'ok' : 'critical'}"></span>${ok ? 'работает' : API.outdated ? 'старая версия — нужно обновление' : 'не запущен'} · ${esc(API.base)}</span>
    <span class="k">Документов в базе</span><span>${ok ? REAL.docs.length : '—'}</span>`;
}

refreshReal();

/* -------------------------------------------------------------------------
   Ассистент по настоящей базе: сервер отбирает документы и считает суммы,
   здесь — только показ. Каждая строка и ссылка [n] открывает документ на месте цитаты.
   ------------------------------------------------------------------------- */
async function realPlan(q) {
  if (!REAL.loaded) await refreshReal();
  if (!API.online || !REAL.docs.length) return null;
  let res;
  try { res = await API.assistant(q, chat.rctx || null); } catch (e) { console.warn(e); return null; }
  // в настоящей базе ответа нет — пусть ответит демо-сценарий, если демо-данные включены
  if (!res.found && showDemo()) return null;
  if (res.context) chat.rctx = res.context;
  return { real: true, miss: !res.found, steps: res.steps || [], render: (el, scroll) => renderRealAnswer(res, el, scroll) };
}

const ruDate = (iso) => (iso ? iso.slice(0, 10).split('-').reverse().join('.') : '—');

function realAnswerCell(key, r) {
  if (key === 'title') {
    const sub = r.snippet && r.quote ? r.quote : [r.typeName, r.number ? '№ ' + r.number : ''].filter(Boolean).join(' · ');
    return `<td><span class="doc-link" data-rn="${r.n}">${esc(r.title)}</span>${sub ? `<div class="faint" style="font-size:12px">${esc(sub)}</div>` : ''}</td>`;
  }
  if (key === 'date') return `<td>${ruDate(r.date)}</td>`;
  if (key === 'party') return `<td>${esc(r.party || '—')}</td>`;
  if (key === 'validUntil') {
    const left = r.daysLeft;
    const when = left == null ? '' : left < 0 ? 'срок прошёл' : left === 0 ? 'сегодня' : `через ${left} ${plural(left, 'день', 'дня', 'дней')}`;
    return `<td>${ruDate(r.validUntil)}${when ? `<div class="faint" style="font-size:12px">${when}</div>` : ''}</td>`;
  }
  if (key === 'check') {
    const sev = r.critical ? 'critical' : r.warning ? 'warning' : 'ok';
    const text = r.critical ? `${r.critical} критичных` : r.warning ? `${r.warning} ${plural(r.warning, 'замечание', 'замечания', 'замечаний')}` : 'Без замечаний';
    return `<td><span class="tag ${sev}"><span class="sev-dot ${sev}"></span>${text}</span></td>`;
  }
  if (key === 'amount') return `<td class="num"${r.quote && !r.snippet ? ` title="${esc(r.quote)}"` : ''}>${r.amount ? rub(Math.round(r.amount)) : '—'}</td>`;
  return '<td></td>';
}

async function renderRealAnswer(res, el, scroll) {
  const ans = el.closest('.answer');
  const rows = res.table?.rows || [];
  ans._rows = Object.fromEntries(rows.map((r) => [r.n, r]));
  const mark = (s) => esc(s).replace(/\{([^}]*)\}/g, '<span class="num">$1</span>');
  const withRefs = (s) => esc(s).replace(/\[(\d+)\]/g, (m, n) => (ans._rows[n] ? `<span class="ref" data-rn="${n}">${n}</span>` : ''));
  const LABEL = { title: 'Документ', date: 'Дата', party: 'Контрагент', validUntil: 'Действует до', check: 'Проверка', amount: 'Сумма' };
  let html = '';
  if (res.headline) html += `<div class="headline">${mark(res.headline)}</div>`;
  if (res.filters?.length) html += `<div class="scope-chips">${res.filters.map((f) => `<span class="chip filter">${esc(f)}</span>`).join('')}</div>`;

  if (res.kind === 'brief' && res.card) {
    html += `<div class="box"><div class="box-head"><span>Карточка документа</span><span class="doc-link" data-rn="1">Открыть в редакторе</span></div>
      <table class="data"><tbody>${res.card.map(([k, v]) => `<tr><td class="faint" style="width:160px">${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>`;
  } else if (res.groups) {
    const total = res.table.total;
    html += `<div class="box"><div class="box-head"><span>По контрагентам</span><span>${total ? rub(Math.round(total)) : ''}</span></div>
      <table class="data"><thead><tr><th>Контрагент</th><th class="num">Документов</th>${total ? '<th class="num">Доля</th><th class="num">Сумма</th>' : ''}</tr></thead><tbody>
      ${res.groups.map((g) => `<tr><td>${esc(g.group)} ${g.refs.map((n) => `<span class="ref" data-rn="${n}">${n}</span>`).join('')}</td><td class="num">${g.count}</td>
        ${total ? `<td class="num">${g.share ?? 0} %</td><td class="num">${g.amount ? rub(Math.round(g.amount)) : '—'}</td>` : ''}</tr>`).join('')}
      </tbody></table></div>`;
  } else if (rows.length) {
    const cols = res.table.columns;
    html += `<div class="box"><div class="box-head"><span>Документы-источники</span><span>Нажмите на документ — он откроется на нужном месте</span></div>
      <table class="data"><thead><tr><th>#</th>${cols.map((c) => `<th${c === 'amount' ? ' class="num"' : ''}>${LABEL[c]}</th>`).join('')}</tr></thead><tbody>
      ${rows.map((r) => `<tr><td><span class="ref" data-rn="${r.n}">${r.n}</span></td>${cols.map((c) => realAnswerCell(c, r)).join('')}</tr>`).join('')}
      ${res.table.total ? `<tr class="total"><td></td><td>Итого</td>${cols.slice(1, -1).map(() => '<td></td>').join('')}<td class="num">${rub(Math.round(res.table.total))}</td></tr>` : ''}
      </tbody></table></div>`;
  }
  html += '<div class="summary"></div>';
  el.innerHTML = html;
  scroll();

  const sum = $('.summary', el);
  await typeInto(sum, res.summary || '', 10);
  sum.innerHTML = withRefs(res.summary || '');

  const note = res.generated
    ? `Вывод сформулирован языковой моделью${res.llm?.model ? ' ' + esc(res.llm.model) : ''}. Список документов и суммы взяты из самих документов.`
    : (res.found ? 'Список документов и суммы взяты из самих документов. Языковая модель не подключена — вывод составлен по шаблону.' : '');
  ans._copy = [res.headline ? res.headline.replace(/[{}]/g, '') : '', ...rows.map((r) => `${r.n}. ${r.title}${r.amount ? ' — ' + rub(Math.round(r.amount)) : ''}`), res.summary || ''].filter(Boolean).join('\n');
  el.insertAdjacentHTML('beforeend',
    (res.alerts?.length ? `<div class="alerts">${res.alerts.map((a) => `<div class="alert">${icon('alert')}<span>${withRefs(a)}</span></div>`).join('')}</div>` : '')
    + (res.followups?.length ? `<div class="followups">${res.followups.map((f) => `<button class="chip ai" data-ask="${esc(f)}">${esc(f)}</button>`).join('')}</div>` : '')
    + (res.found ? `<div class="actions-row"><button class="btn small" data-copy-answer>${icon('copy')}Копировать</button></div>` : '')
    + (note ? `<div class="faint" style="font-size:12px">${note}</div>` : ''));
  scroll();
}

$('#chat').addEventListener('click', (e) => {
  const ans = e.target.closest('.answer');
  if (!ans) return;
  if (e.target.closest('[data-copy-answer]')) {
    navigator.clipboard?.writeText(ans._copy || '').then(() => toast('Ответ скопирован'), () => toast('Не удалось скопировать'));
    return;
  }
  const link = e.target.closest('[data-rn]');
  const r = link && ans._rows?.[link.dataset.rn];
  if (r) openRealDoc(r.id, r.block != null ? { block: r.block, start: r.start, end: r.end } : null);
});
