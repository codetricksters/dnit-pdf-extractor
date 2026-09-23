const zone = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const submitBtn = document.getElementById('submit-btn');
const status = document.getElementById('status');
const progressSection = document.getElementById('progress-section');
const fileProgress = document.getElementById('file-progress');
const downloadAllBtn = document.getElementById('download-all-btn');
const fileCountEl = document.getElementById('file-count');
const fileSizeEl = document.getElementById('file-size');
const selectFilesBtn = document.getElementById('select-files-btn');
const progressCount = document.getElementById('progress-count');

let selectedFiles = [];
let currentJobId = null;
let jobFinished = false;
let eventSource = null;

document.getElementById('reset-btn').addEventListener('click', () => {
  resetState();
  submitBtn.disabled = true;
});

selectFilesBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  input.click();
});

zone.addEventListener('click', (e) => {
  if (e.target === selectFilesBtn || selectFilesBtn.contains(e.target)) return;
  input.click();
});

zone.addEventListener('dragover', e => {
  e.preventDefault();
  zone.classList.add('over');
});

zone.addEventListener('dragleave', () => zone.classList.remove('over'));

zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('over');
  addFiles([...e.dataTransfer.files].filter(f => f.name.endsWith('.pdf')));
});

input.addEventListener('change', () => addFiles([...input.files]));

function addFiles(files) {
  if (jobFinished) resetState();
  selectedFiles = [...selectedFiles, ...files];
  renderStats();
}

function resetState() {
  selectedFiles = [];
  currentJobId = null;
  jobFinished = false;
  fileProgress.innerHTML = '';
  progressSection.classList.add('hidden');
  downloadAllBtn.classList.add('hidden');
  document.getElementById('reset-btn').classList.add('hidden');
  status.textContent = '';
  status.className = 'status-message';
  input.value = '';
  renderStats();
  localStorage.removeItem('dnit_job_id');
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function formatSize(bytes) {
  if (bytes === 0) return '0 KB';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function renderStats() {
  const count = selectedFiles.length;
  const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
  fileCountEl.textContent = count
    ? `${count} arquivo${count !== 1 ? 's' : ''} selecionado${count !== 1 ? 's' : ''}`
    : 'Nenhum arquivo selecionado';
  fileSizeEl.textContent = formatSize(totalSize);
  submitBtn.disabled = count === 0;
  status.textContent = '';
  status.className = 'status-message';
}

document.getElementById('upload-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedFiles.length) return;

  submitBtn.disabled = true;
  status.textContent = 'Enviando arquivos…';
  status.className = 'status-message';
  progressSection.classList.add('hidden');
  downloadAllBtn.classList.add('hidden');
  fileProgress.innerHTML = '';

  const fd = new FormData();
  selectedFiles.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    currentJobId = data.job_id;
    localStorage.setItem('dnit_job_id', currentJobId);

    status.textContent = 'Processando…';
    progressSection.classList.remove('hidden');
    initFileProgress(selectedFiles.map(f => f.name));
    connectSSE(currentJobId);
  } catch (err) {
    status.textContent = 'Erro: ' + err.message;
    status.className = 'status-message error';
    submitBtn.disabled = false;
  }
});

// Cada arquivo do lote é uma linha da tabela "Arquivos no Lote Atual": nome,
// estado da leitura e resultado (baixar, ou o erro com a ação de repetir).
const ESTADO = {
  pending: { rotulo: 'Na fila', classe: 'badge-pending', icone: 'schedule' },
  processing: { rotulo: 'Processando', classe: 'badge-processing', icone: 'sync' },
  completed: { rotulo: 'Concluído', classe: 'badge-ok', icone: 'check_circle' },
  failed: { rotulo: 'Falha', classe: 'badge-danger', icone: 'error' },
};

function fileRow(name) {
  const tr = document.createElement('tr');
  tr.className = 'file-row status-pending';
  tr.dataset.filename = name;
  tr.innerHTML = `<td class="left"><span class="file-row-name">${escapeHtml(name)}</span></td>`
    + '<td class="left file-status"></td>'
    + '<td class="left file-action"></td>';
  setRowStatus(tr, 'pending');
  fileProgress.appendChild(tr);
  return tr;
}

function setRowStatus(tr, estado) {
  const e = ESTADO[estado] || ESTADO.pending;
  tr.className = `file-row status-${estado}`;
  tr.querySelector('.file-status').innerHTML =
    `<span class="badge ${e.classe}"><span class="material-symbols-outlined">${e.icone}</span>${e.rotulo}</span>`;
}

function initFileProgress(filenames) {
  fileProgress.innerHTML = '';
  filenames.forEach(fileRow);
}

function connectSSE(jobId) {
  if (eventSource) {
    eventSource.close();
  }
  eventSource = new EventSource(`/jobs/${jobId}/events`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgress(data);
    if (data.completed) {
      eventSource.close();
      eventSource = null;
      onJobComplete(jobId);
    }
  };

  eventSource.addEventListener('complete', () => {
    eventSource.close();
    eventSource = null;
    onJobComplete(jobId);
  });

  eventSource.onerror = async () => {
    eventSource.close();
    eventSource = null;
    const res = await fetch(`/jobs/${jobId}/status`).catch(() => null);
    if (res && res.ok) {
      const data = await res.json();
      updateProgress(data);
      if (data.completed) {
        onJobComplete(jobId);
        return;
      }
    }
    startPolling(jobId);
  };
}

function updateProgress(data) {
  for (const [filename, info] of Object.entries(data.files)) {
    const tr = fileProgress.querySelector(`[data-filename="${CSS.escape(filename)}"]`)
      || fileRow(filename);
    setRowStatus(tr, info.status);
    const action = tr.querySelector('.file-action');

    if (info.status === 'completed') {
      action.innerHTML = `<a class="btn btn-sm" href="/jobs/${currentJobId}/download/${encodeURIComponent(filename)}">`
        + '<span class="material-symbols-outlined">download</span>Baixar JSON</a>';
    } else if (info.status === 'failed') {
      action.innerHTML = `<span class="file-row-note">${escapeHtml(info.error || 'Erro na leitura')}</span>`
        + `<button class="btn btn-sm mt-sm" onclick="retryFile('${escapeHtml(filename)}')">`
        + '<span class="material-symbols-outlined">refresh</span>Reprocessar</button>';
    } else {
      action.innerHTML = '';
    }
  }
  const total = Object.keys(data.files).length;
  const prontos = Object.values(data.files).filter(f => f.status === 'completed').length;
  progressCount.textContent = `${prontos} / ${total} concluídos`;
}

async function retryFile(filename) {
  const res = await fetch(`/jobs/${currentJobId}/retry/${encodeURIComponent(filename)}`, { method: 'POST' });
  if (res.ok) {
    const tr = fileProgress.querySelector(`[data-filename="${CSS.escape(filename)}"]`);
    if (tr) {
      setRowStatus(tr, 'pending');
      tr.querySelector('.file-action').innerHTML = '';
    }
    status.textContent = 'Processando…';
    status.className = 'status-message';
    downloadAllBtn.classList.add('hidden');
    jobFinished = false;
    connectSSE(currentJobId);
  } else {
    const err = await res.json().catch(() => ({ detail: 'Erro ao tentar novamente' }));
    status.textContent = 'Erro: ' + (err.detail || 'Falha ao reprocessar');
    status.className = 'status-message error';
  }
}

function onJobComplete(jobId) {
  status.textContent = 'Processamento concluído!';
  status.className = 'status-message success';
  downloadAllBtn.href = `/jobs/${jobId}/download`;
  downloadAllBtn.classList.remove('hidden');
  submitBtn.disabled = false;
  jobFinished = true;
  document.getElementById('reset-btn').classList.remove('hidden');
}

function startPolling(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/jobs/${jobId}/status`);
      if (!res.ok) { clearInterval(interval); return; }
      const data = await res.json();
      updateProgress(data);
      if (data.completed) {
        clearInterval(interval);
        onJobComplete(jobId);
      }
    } catch {
      clearInterval(interval);
    }
  }, 2000);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function reconnectToJob(jobId) {
  const res = await fetch(`/jobs/${jobId}/status`);
  if (!res.ok) {
    localStorage.removeItem('dnit_job_id');
    return;
  }
  const data = await res.json();
  currentJobId = jobId;

  progressSection.classList.remove('hidden');
  initFileProgress(Object.keys(data.files));
  updateProgress(data);
  document.getElementById('reset-btn').classList.remove('hidden');

  if (data.completed) {
    onJobComplete(jobId);
  } else {
    status.textContent = 'Processando…';
    connectSSE(jobId);
  }
}

// Navigation
const navItems = document.querySelectorAll('.nav-item[data-view]');
const viewSections = {
  upload: document.getElementById('view-upload'),
  queue: document.getElementById('view-queue'),
  files: document.getElementById('view-files'),
};
const pageTitle = document.querySelector('.page-title');
const pageSubtitle = document.querySelector('.page-subtitle');

const viewMeta = {
  upload: { title: 'Processador de Medições', subtitle: 'Upload de PDFs DNIT para extração de dados tabulares' },
  queue: { title: 'Fila de Processamento', subtitle: 'Jobs ativos e em andamento' },
  files: { title: 'Arquivos Processados', subtitle: 'Jobs concluídos disponíveis para download' },
};

let queuePollInterval = null;

navItems.forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const view = item.dataset.view;
    switchView(view);
  });
});

function switchView(view) {
  navItems.forEach(n => n.classList.toggle('active', n.dataset.view === view));
  Object.entries(viewSections).forEach(([key, el]) => {
    if (el) el.classList.toggle('hidden', key !== view);
  });
  if (viewMeta[view]) {
    pageTitle.textContent = viewMeta[view].title;
    pageSubtitle.textContent = viewMeta[view].subtitle;
  }
  if (queuePollInterval) {
    clearInterval(queuePollInterval);
    queuePollInterval = null;
  }
  if (view === 'queue') {
    loadQueueView();
    queuePollInterval = setInterval(loadQueueView, 3000);
  } else if (view === 'files') {
    loadFilesView();
  }
}

async function loadQueueView() {
  try {
    const res = await fetch('/jobs?status=active');
    if (!res.ok) return;
    const jobs = await res.json();
    const list = document.getElementById('queue-list');
    const empty = document.getElementById('queue-empty');
    if (!jobs.length) {
      list.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    list.innerHTML = jobs.map(j => renderJobItem(j, false)).join('');
  } catch {}
}

async function loadFilesView() {
  try {
    const res = await fetch('/jobs?status=completed');
    if (!res.ok) return;
    const jobs = await res.json();
    const list = document.getElementById('files-list');
    const empty = document.getElementById('files-empty');
    if (!jobs.length) {
      list.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    list.innerHTML = jobs.map(j => renderJobItem(j, true)).join('');
  } catch {}
}

function renderJobItem(job, showDownload) {
  const date = new Date(job.created_at).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  const badges = [];
  if (job.processing_count > 0) badges.push(`<span class="badge badge-processing">${job.processing_count} processando</span>`);
  if (job.pending_count > 0) badges.push(`<span class="badge badge-pending">${job.pending_count} pendente</span>`);
  if (job.completed_count > 0) badges.push(`<span class="badge badge-completed">${job.completed_count} concluído</span>`);
  if (job.failed_count > 0) badges.push(`<span class="badge badge-failed">${job.failed_count} falha</span>`);

  const baixar = showDownload
    ? `<a class="btn btn-sm" href="/jobs/${job.job_id}/download">`
      + '<span class="material-symbols-outlined">folder_zip</span>Baixar .zip</a>'
    : '';

  return `<tr>
    <td class="left">
      <span class="file-row-name">${job.job_id}</span>
      <span class="file-row-note">${date}</span>
    </td>
    <td class="left">${job.file_count} arquivo${job.file_count !== 1 ? 's' : ''}</td>
    <td class="left">${badges.join(' ')} ${baixar}</td>
  </tr>`;
}

window.addEventListener('DOMContentLoaded', () => {
  const savedJobId = localStorage.getItem('dnit_job_id');
  if (savedJobId) {
    reconnectToJob(savedJobId);
  }
});
