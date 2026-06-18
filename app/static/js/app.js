const form = document.querySelector('#analyze-form');
const imageInput = document.querySelector('#image-input');
const dropzone = document.querySelector('.dropzone');
const preview = document.querySelector('#preview');
const previewImage = document.querySelector('#preview-image');
const button = document.querySelector('#analyze-button');
const debugList = document.querySelector('#debug-list');

const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function setText(id, value) {
  const element = byId(id);
  element.textContent = value === null || value === undefined || value === '' ? 'null' : String(value);
  element.classList.toggle('null', value === null || value === undefined || value === '');
}

function setPill(id, value) {
  const element = byId(id);
  if (value === null || value === undefined || value === '') {
    element.innerHTML = 'null';
    element.classList.add('null');
    return;
  }
  element.innerHTML = `<span class="pill">${escapeHtml(value)}</span>`;
  element.classList.remove('null');
}

function setGuard(id, label, value) {
  const element = byId(id);
  element.classList.remove('ok', 'no');
  element.classList.add(value ? 'ok' : 'no');
  element.innerHTML = `<span class="d"></span>${escapeHtml(label)} · ${escapeHtml(value)}`;
}

function renderDebugSteps(steps, totalMs) {
  if (!steps || steps.length === 0) {
    debugList.innerHTML = '<div class="empty">분석 전입니다.</div>';
    return;
  }
  const maxMs = Math.max(...steps.map((step) => step.elapsed_ms), 1);
  const rows = steps.map((step) => {
    const width = Math.max(1, Math.round((step.elapsed_ms / maxMs) * 100));
    return `
      <div class="debug-row">
        <div class="debug-main">
          <div class="debug-label">${escapeHtml(step.label)}</div>
          <div class="debug-meta">runtime checkpoint</div>
        </div>
        <div class="debug-ms">${escapeHtml(step.elapsed_ms)}ms</div>
        <div class="debug-track"><div class="debug-fill" style="width: ${width}%;"></div></div>
      </div>
    `;
  }).join('');
  debugList.innerHTML = `${rows}
    <div class="debug-row total">
      <div class="debug-main">
        <div class="debug-label">총 처리 시간</div>
        <div class="debug-meta">업로드 후 결과 표시까지</div>
      </div>
      <div class="debug-ms">${escapeHtml(totalMs)}ms</div>
    </div>`;
}

function renderResult(result) {
  byId('identification').textContent = result.identification || '식별 불가';
  byId('identification-reason').textContent = result.identification_reason || '-';
  setGuard('is-whisky', 'is_whisky', result.is_whisky);
  setGuard('label-legible', 'label_legible', result.label_legible);
  setText('eng-name', result.eng_name);
  setText('kor-name', result.kor_name);
  setPill('type', result.type);
  setPill('category-group', result.category_group);
  setText('abv', result.abv);
  setText('age', result.age);
  setText('volume-ml', result.volume_ml);
  setText('cask', result.cask);
  setText('country', result.country);
  setText('distillery', result.distillery);
  byId('description').textContent = result.description || '-';
  byId('visible-text-raw').innerHTML = `<span class="tag">visible_text_raw ▸</span>\n${escapeHtml(result.visible_text_raw || '-')}`;
}

function renderPreview(file) {
  previewImage.src = URL.createObjectURL(file);
  preview.classList.remove('hidden');
}

imageInput.addEventListener('change', () => {
  const file = imageInput.files?.[0];
  if (!file) return;
  renderPreview(file);
});

dropzone.addEventListener('dragover', (event) => {
  event.preventDefault();
  dropzone.classList.add('active');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('active');
});

dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  dropzone.classList.remove('active');
  const file = event.dataTransfer.files?.[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  imageInput.files = transfer.files;
  renderPreview(file);
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = imageInput.files?.[0];
  if (!file) {
    debugList.innerHTML = '<div class="empty">이미지를 먼저 선택하세요.</div>';
    return;
  }
  button.disabled = true;
  button.textContent = '분석 중...';
  debugList.innerHTML = '<div class="empty">분석 요청을 처리하고 있습니다.</div>';
  const formData = new FormData(form);

  try {
    const response = await fetch('/api/analyze', { method: 'POST', body: formData });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message);
    }
    const payload = await response.json();
    renderDebugSteps(payload.debug_steps, payload.total_ms);
    renderResult(payload.result);
  } catch (error) {
    debugList.innerHTML = `<div class="empty">분석 실패: ${escapeHtml(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = '분석 ▶';
  }
});
