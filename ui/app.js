/* ── State ── */
let selectedFile = null;
let selectedModel = null;
let isRunning = false;

/* ── DOM refs ── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropzone = $('#dropzone');
const fileLoaded = $('#fileLoaded');
const fileName = $('#fileName');
const fileMeta = $('#fileMeta');
const fileRemove = $('#fileRemove');
const modelList = $('#modelList');
const btnGenerate = $('#btnGenerate');
const progressCard = $('#progressCard');
const pcTitle = $('#pcTitle');
const pcPercent = $('#pcPercent');
const pcBarFill = $('#pcBarFill');
const emptyState = $('#emptyState');
const srtViewer = $('#srtViewer');
const srtFilename = $('#srtFilename');
const srtBody = $('#srtBody');
const logViewer = $('#logViewer');
const btnCopy = $('#btnCopy');
const btnSave = $('#btnSave');
const themeToggle = $('#themeToggle');

/* ── pywebview API bridge ── */
function api() {
  return window.pywebview ? window.pywebview.api : null;
}

function waitForApi() {
  return new Promise((resolve) => {
    if (window.pywebview) return resolve();
    window.addEventListener('pywebviewready', resolve);
  });
}

/* ── Theme ── */
themeToggle.addEventListener('click', () => {
  const html = document.documentElement;
  const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
  html.dataset.theme = next;
  localStorage.setItem('theme', next);
});
const saved = localStorage.getItem('theme');
if (saved) document.documentElement.dataset.theme = saved;

/* ── Tabs ── */
$$('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach((t) => t.classList.remove('active'));
    $$('.tab-content').forEach((c) => c.classList.remove('active'));
    tab.classList.add('active');
    $(`.tab-content[data-tab="${tab.dataset.tab}"]`).classList.add('active');
  });
});

/* ── File Selection ── */
dropzone.addEventListener('click', async () => {
  if (!api()) return;
  const result = await api().select_file();
  if (result) setFile(result);
});

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});
dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('dragover');
});
dropzone.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) {
    const f = e.dataTransfer.files[0];
    if (!api()) return;
    const result = await api().handle_drop(f.name);
    if (result) setFile(result);
  }
});

function setFile(info) {
  selectedFile = info.path;
  fileName.textContent = info.name;
  fileMeta.textContent = info.meta || '';
  dropzone.classList.add('hidden');
  fileLoaded.classList.remove('hidden');
  updateGenerateBtn();
}

fileRemove.addEventListener('click', () => {
  selectedFile = null;
  dropzone.classList.remove('hidden');
  fileLoaded.classList.add('hidden');
  updateGenerateBtn();
});

/* ── Models ── */
async function loadModels() {
  if (!api()) return;
  const models = await api().get_models();
  modelList.innerHTML = '';
  models.forEach((m, i) => {
    const card = document.createElement('div');
    card.className = 'model-card' + (i === 0 && m.ready ? ' selected' : '') + (!m.ready ? '' : '');
    card.dataset.name = m.name;
    card.innerHTML = `
      <div class="mc-header">
        <span class="mc-name">${m.label}</span>
        <span class="mc-badge ${m.ready ? 'badge-ok' : 'badge-need'}">${m.ready ? 'Ready' : 'Download'}</span>
      </div>
      <div class="mc-desc">${m.desc}</div>
      <div class="mc-tags">
        ${m.tags.map((t) => `<span class="mc-tag${t.includes('GPU') ? ' gpu' : ''}">${t}</span>`).join('')}
      </div>
      ${!m.ready ? `<button class="mc-download-btn" data-model="${m.name}">다운로드</button>
        <div class="mc-dl-bar hidden"><div class="mc-dl-bar-fill"></div></div>
        <div class="mc-dl-text hidden"></div>` : ''}
    `;

    if (m.ready) {
      card.addEventListener('click', () => selectModel(m.name));
    }

    modelList.appendChild(card);

    if (i === 0 && m.ready) selectedModel = m.name;
  });

  // Download buttons
  modelList.querySelectorAll('.mc-download-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      downloadModel(btn.dataset.model);
    });
  });

  updateGenerateBtn();
}

function selectModel(name) {
  if (isRunning) return;
  selectedModel = name;
  modelList.querySelectorAll('.model-card').forEach((c) => {
    c.classList.toggle('selected', c.dataset.name === name);
  });
  updateGenerateBtn();
}

async function downloadModel(name) {
  if (!api()) return;
  const card = modelList.querySelector(`.model-card[data-name="${name}"]`);
  const btn = card.querySelector('.mc-download-btn');
  const bar = card.querySelector('.mc-dl-bar');
  const barFill = card.querySelector('.mc-dl-bar-fill');
  const text = card.querySelector('.mc-dl-text');

  btn.disabled = true;
  btn.textContent = '다운로드 중...';
  bar.classList.remove('hidden');
  text.classList.remove('hidden');

  const result = await api().download_model(name);

  if (result.success) {
    addLog(`[OK] ${name} 모델 다운로드 완료`);
    await loadModels();
    await loadStatus();
  } else {
    btn.disabled = false;
    btn.textContent = '다운로드';
    bar.classList.add('hidden');
    text.classList.add('hidden');
    addLog(`[ERR] ${result.message}`);
  }
}

/* ── Generate ── */
function updateGenerateBtn() {
  btnGenerate.disabled = !selectedFile || !selectedModel || isRunning;
}

btnGenerate.addEventListener('click', async () => {
  if (!api() || !selectedFile || !selectedModel || isRunning) return;
  isRunning = true;
  updateGenerateBtn();
  btnGenerate.textContent = '변환 중...';

  // Show progress
  progressCard.classList.remove('hidden');
  emptyState.classList.add('hidden');
  srtViewer.classList.add('hidden');
  setProgress(0, '시작 중...');

  addLog(`[START] ${selectedFile} → ${selectedModel}`);

  const result = await api().transcribe(selectedFile, selectedModel);

  if (result.success) {
    showSrt(result.srt_text, result.srt_path);
    addLog(`[DONE] 자막 생성 완료: ${result.srt_path}`);
  } else {
    addLog(`[ERR] ${result.message}`);
  }

  progressCard.classList.add('hidden');
  isRunning = false;
  btnGenerate.textContent = '자막 생성';
  updateGenerateBtn();
});

/* ── Progress ── */
function setProgress(percent, title, step) {
  pcBarFill.style.width = percent + '%';
  pcPercent.textContent = percent + '%';
  if (title) pcTitle.textContent = title;

  const steps = ['extract', 'load', 'transcribe', 'srt'];
  const activeIdx = steps.indexOf(step);
  $$('.pc-step').forEach((el, i) => {
    el.classList.remove('done', 'active');
    if (i < activeIdx) el.classList.add('done');
    else if (i === activeIdx) el.classList.add('active');
  });
}

// Called from Python
window.updateProgress = function (percent, title, step) {
  setProgress(percent, title, step);
};

/* ── SRT Display ── */
function showSrt(srtText, srtPath) {
  emptyState.classList.add('hidden');
  srtViewer.classList.remove('hidden');

  const pathParts = srtPath.replace(/\\/g, '/').split('/');
  srtFilename.textContent = pathParts[pathParts.length - 1];

  srtBody.innerHTML = '';
  const blocks = srtText.trim().split(/\n\n+/);
  blocks.forEach((block) => {
    const lines = block.split('\n');
    if (lines.length < 2) return;
    const div = document.createElement('div');
    div.className = 'srt-block';
    div.innerHTML = `
      <div class="idx">${lines[0]}</div>
      <div class="time">${lines[1] || ''}</div>
      <div class="text">${lines.slice(2).join('<br>')}</div>
    `;
    srtBody.appendChild(div);
  });

  window._srtText = srtText;
  window._srtPath = srtPath;
}

btnCopy.addEventListener('click', () => {
  if (window._srtText) {
    navigator.clipboard.writeText(window._srtText);
    btnCopy.textContent = '복사됨!';
    setTimeout(() => (btnCopy.textContent = '복사'), 1500);
  }
});

btnSave.addEventListener('click', async () => {
  if (!api() || !window._srtPath) return;
  await api().save_srt_dialog(window._srtPath);
});

/* ── Log ── */
function addLog(msg) {
  const time = new Date().toLocaleTimeString();
  logViewer.textContent += `[${time}] ${msg}\n`;
  logViewer.scrollTop = logViewer.scrollHeight;
}

// Called from Python
window.addLog = addLog;

/* ── Status Bar ── */
async function loadStatus() {
  if (!api()) return;
  const s = await api().get_system_status();

  $('#sysGpu').textContent = s.gpu_name || 'Not available';
  $('#sysGpu').className = 'sys-val ' + (s.gpu_available ? 'ok' : 'warn');

  $('#sysVram').textContent = s.vram || '-';
  $('#sysVram').className = 'sys-val';

  $('#sysFfmpeg').textContent = s.ffmpeg ? 'Installed' : 'Missing';
  $('#sysFfmpeg').className = 'sys-val ' + (s.ffmpeg ? 'ok' : 'err');

  $('#stFfmpeg').className = 'st-dot ' + (s.ffmpeg ? 'ok' : 'err');
  $('#stCuda').className = 'st-dot ' + (s.gpu_available ? 'ok' : 'warn');
  $('#stMoonshine').className = 'st-dot ' + (s.moonshine_ready ? 'ok' : 'warn');
  $('#stQwen').className = 'st-dot ' + (s.qwen_ready ? 'ok' : 'warn');
}

/* ── Init ── */
async function init() {
  await waitForApi();
  addLog('[INIT] 시스템 상태 확인 중...');
  await loadStatus();
  await loadModels();
  addLog('[INIT] 준비 완료');
}

init();
