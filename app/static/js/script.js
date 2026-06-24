const zone = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const submitBtn = document.getElementById('submit-btn');
const status = document.getElementById('status');
const progressSection = document.getElementById('progress-section');
const fileProgress = document.getElementById('file-progress');
const downloadSection = document.getElementById('download-section');
const downloadAllBtn = document.getElementById('download-all-btn');
const fileCountEl = document.getElementById('file-count');
const fileSizeEl = document.getElementById('file-size');
const selectFilesBtn = document.getElementById('select-files-btn');

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
  downloadSection.classList.add('hidden');
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
  fileCountEl.textContent = `SELECIONADOS: ${count} ARQUIVO${count !== 1 ? 'S' : ''}`;
  fileSizeEl.textContent = `TAMANHO TOTAL: ${formatSize(totalSize)}`;
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
  downloadSection.classList.add('hidden');
  fileProgress.innerHTML = '';

  const fd = new FormData();
  selectedFiles.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json();
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

function initFileProgress(filenames) {
  fileProgress.innerHTML = '';
  filenames.forEach(name => {
    const li = document.createElement('li');
    li.className = 'file-item status-pending';
    li.dataset.filename = name;
    li.innerHTML = `<span class="file-indicator"></span><span class="file-name">${escapeHtml(name)}</span><span class="file-action"></span>`;
    fileProgress.appendChild(li);
  });
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
    let li = fileProgress.querySelector(`[data-filename="${CSS.escape(filename)}"]`);
    if (!li) {
      li = document.createElement('li');
      li.className = 'file-item status-pending';
      li.dataset.filename = filename;
      li.innerHTML = `<span class="file-indicator"></span><span class="file-name">${escapeHtml(filename)}</span><span class="file-action"></span>`;
      fileProgress.appendChild(li);
    }

    li.className = `file-item status-${info.status}`;
    const action = li.querySelector('.file-action');

    if (info.status === 'completed') {
      action.innerHTML = `<a href="/jobs/${currentJobId}/download/${encodeURIComponent(filename)}" class="btn-download-sm">BAIXAR</a>`;
    } else if (info.status === 'failed') {
      action.innerHTML = `<span class="error-msg">${escapeHtml(info.error || 'Erro')}</span><button class="btn-retry-sm" onclick="retryFile('${escapeHtml(filename)}')">Retry</button>`;
    } else {
      action.innerHTML = '';
    }
  }
}

async function retryFile(filename) {
  const res = await fetch(`/jobs/${currentJobId}/retry/${encodeURIComponent(filename)}`, { method: 'POST' });
  if (res.ok) {
    const li = fileProgress.querySelector(`[data-filename="${CSS.escape(filename)}"]`);
    if (li) {
      li.className = 'file-item status-pending';
      li.querySelector('.file-action').innerHTML = '';
    }
    status.textContent = 'Processando…';
    status.className = 'status-message';
    downloadSection.classList.add('hidden');
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
  downloadSection.classList.remove('hidden');
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

  const actions = showDownload
    ? `<a href="/jobs/${job.job_id}/download" class="btn-download-sm">BAIXAR ZIP</a>`
    : badges.join(' ');

  return `<li class="job-item">
    <div class="job-info">
      <span class="job-id">${job.job_id}</span>
      <span class="job-meta"><span>${date}</span><span>${job.file_count} arquivo${job.file_count !== 1 ? 's' : ''}</span></span>
    </div>
    <div class="job-actions">${showDownload ? badges.join(' ') + ' ' + actions : actions}</div>
  </li>`;
}

window.addEventListener('DOMContentLoaded', () => {
  const savedJobId = localStorage.getItem('dnit_job_id');
  if (savedJobId) {
    reconnectToJob(savedJobId);
  }
});
