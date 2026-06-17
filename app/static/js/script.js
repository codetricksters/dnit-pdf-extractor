const zone = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const submitBtn = document.getElementById('submit-btn');
const status = document.getElementById('status');
let selectedFiles = [];

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
  selectedFiles = [...selectedFiles, ...files];
  renderList();
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
  status.textContent = 'Processando…';
  status.style.color = '#555';

  const fd = new FormData();
  selectedFiles.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || res.statusText);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'medicao.xlsx';
    a.click();
    URL.revokeObjectURL(url);
    status.textContent = 'Download iniciado!';
    status.style.color = '#27ae60';
  } catch (err) {
    status.textContent = 'Erro: ' + err.message;
    status.style.color = '#c0392b';
  } finally {
    submitBtn.disabled = false;
  }
});
