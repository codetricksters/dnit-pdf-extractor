const zone = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const submitBtn = document.getElementById('submit-btn');
const status = document.getElementById('status');
const progressSection = document.getElementById('progress-section');
const fileProgress = document.getElementById('file-progress');
const downloadSection = document.getElementById('download-section');
const downloadAllBtn = document.getElementById('download-all-btn');

let selectedFiles = [];
let currentJobId = null;
let jobFinished = false;
let eventSource = null;

document.getElementById('reset-btn').addEventListener('click', () => {
  resetState();
  submitBtn.disabled = true;
});

zone.addEventListener('click', () => input.click());

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
  renderList();
}

function resetState() {
  selectedFiles = [];
  currentJobId = null;
  jobFinished = false;
  fileList.textContent = '';
  fileProgress.innerHTML = '';
  progressSection.classList.add('hidden');
  downloadSection.classList.add('hidden');
  document.getElementById('reset-btn').classList.add('hidden');
  status.textContent = '';
  status.className = '';
  input.value = '';
  localStorage.removeItem('dnit_job_id');
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function renderList() {
  fileList.textContent = selectedFiles.length
    ? selectedFiles.map(f => f.name).join(', ')
    : '';
  submitBtn.disabled = selectedFiles.length === 0;
  status.textContent = '';
}

document.getElementById('upload-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedFiles.length) return;

  submitBtn.disabled = true;
  status.textContent = 'Enviando arquivos…';
  status.className = '';
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
    status.className = 'error';
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
      action.innerHTML = `<a href="/jobs/${currentJobId}/download/${encodeURIComponent(filename)}" class="btn-download-sm">Baixar</a>`;
    } else if (info.status === 'failed') {
      action.innerHTML = `<span class="error-msg">${escapeHtml(info.error || 'Erro')}</span><button class="btn-retry-sm" onclick="retryFile('${escapeHtml(filename)}')">Tentar Novamente</button>`;
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
    status.className = '';
    downloadSection.classList.add('hidden');
    jobFinished = false;
    connectSSE(currentJobId);
  } else {
    const err = await res.json().catch(() => ({ detail: 'Erro ao tentar novamente' }));
    status.textContent = 'Erro: ' + (err.detail || 'Falha ao reprocessar');
    status.className = 'error';
  }
}

function onJobComplete(jobId) {
  status.textContent = 'Processamento concluído!';
  status.className = 'success';
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

window.addEventListener('DOMContentLoaded', () => {
  const savedJobId = localStorage.getItem('dnit_job_id');
  if (savedJobId) {
    reconnectToJob(savedJobId);
  }
});
