const form = document.querySelector('#analyze-form');
const imageInput = document.querySelector('#image-input');
const dropzone = document.querySelector('#analysis-dropzone');
const uploadEmpty = document.querySelector('#analysis-upload-empty');
const preview = document.querySelector('#preview');
const previewImage = document.querySelector('#preview-image');
const button = document.querySelector('#analyze-button');
const debugList = document.querySelector('#debug-list');

const byId = (id) => document.getElementById(id);
const DEBUG_STEP_FLOW = ['이미지 업로드', '이미지 전처리', '프롬프트 구성', 'GPT 분석', '결과 파싱'];

let debugProgressTimer = null;
let previewUrl = null;

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

function debugMeta(label) {
  return {
    '이미지 업로드': '원본 bytes 수신',
    '이미지 전처리': '저장, 표준화, 썸네일 생성',
    '프롬프트 구성': '분석 요청 구성',
    'GPT 분석': '모델 호출',
    '결과 파싱': '응답 구조화',
  }[label] || 'runtime checkpoint';
}

function formatDuration(ms) {
  const numericMs = Number(ms);
  if (!Number.isFinite(numericMs)) return '-';
  const roundedMs = Math.max(0, Math.round(numericMs));
  return `${(roundedMs / 1000).toFixed(1)}초 (${roundedMs}ms)`;
}

function progressTimeLabel(state, step = null) {
  if (step) return formatDuration(step.elapsed_ms);
  if (state === 'running') return '진행 중';
  if (state === 'completed') return '완료';
  return '대기';
}

function stopDebugProgress() {
  window.clearInterval(debugProgressTimer);
  debugProgressTimer = null;
}

function renderDebugProgress(activeIndex) {
  const rows = DEBUG_STEP_FLOW.map((label, index) => {
    const state = index < activeIndex ? 'completed' : index === activeIndex ? 'running' : 'pending';
    return `
      <div class="debug-row ${state}">
        <div class="debug-main">
          <div class="debug-label">${escapeHtml(label)}</div>
          <div class="debug-meta">${escapeHtml(debugMeta(label))}</div>
        </div>
        <div class="debug-ms">${escapeHtml(progressTimeLabel(state))}</div>
      </div>
    `;
  }).join('');
  debugList.innerHTML = rows;
}

function renderLiveDebugSteps(steps, activeLabel = null) {
  if (!steps.length) {
    renderDebugProgress(0);
    return;
  }
  const seenLabels = new Set(steps.map((step) => step.label));
  const rows = DEBUG_STEP_FLOW.map((label) => {
    const step = steps.find((item) => item.label === label);
    const state = activeLabel === label ? 'running' : seenLabels.has(label) ? 'completed' : 'pending';
    return `
      <div class="debug-row ${state}">
        <div class="debug-main">
          <div class="debug-label">${escapeHtml(label)}</div>
          <div class="debug-meta">${escapeHtml(debugMeta(label))}</div>
        </div>
        <div class="debug-ms">${escapeHtml(progressTimeLabel(state, step))}</div>
      </div>
    `;
  }).join('');
  debugList.innerHTML = rows;
}

function playDebugProgress() {
  stopDebugProgress();
  renderDebugProgress(0);
}

function renderDebugSteps(steps, totalMs) {
  stopDebugProgress();
  if (!steps || steps.length === 0) {
    debugList.innerHTML = '<div class="empty">분석 전입니다.</div>';
    return;
  }
  const rows = steps.map((step) => {
    return `
      <div class="debug-row completed">
        <div class="debug-main">
          <div class="debug-label">${escapeHtml(step.label)}</div>
          <div class="debug-meta">${escapeHtml(debugMeta(step.label))}</div>
        </div>
        <div class="debug-ms">${escapeHtml(formatDuration(step.elapsed_ms))}</div>
      </div>
    `;
  }).join('');
  debugList.innerHTML = `${rows}
    <div class="debug-row total">
      <div class="debug-main">
        <div class="debug-label">총 처리 시간</div>
        <div class="debug-meta">업로드 후 결과 표시까지</div>
      </div>
      <div class="debug-ms">${escapeHtml(formatDuration(totalMs))}</div>
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
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
  }
  previewUrl = URL.createObjectURL(file);
  previewImage.src = previewUrl;
  preview.classList.remove('hidden');
  uploadEmpty.hidden = true;
  dropzone.classList.add('has-preview');
}

async function readAnalysisStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const steps = [];

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === 'step') {
        steps.push(event.step);
        const nextLabel = DEBUG_STEP_FLOW[DEBUG_STEP_FLOW.indexOf(event.step.label) + 1] || null;
        renderLiveDebugSteps(steps, nextLabel);
      } else if (event.type === 'result') {
        renderDebugSteps(event.payload.debug_steps, event.payload.total_ms);
        renderResult(event.payload.result);
        return event.payload;
      } else if (event.type === 'error') {
        throw new Error(event.message || '분석 실패');
      }
    }
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer);
    if (event.type === 'result') {
      renderDebugSteps(event.payload.debug_steps, event.payload.total_ms);
      renderResult(event.payload.result);
      return event.payload;
    }
  }

  throw new Error('분석 스트림이 완료되지 않았습니다.');
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
  playDebugProgress();
  const formData = new FormData(form);

  try {
    const response = await fetch('/api/analyze/stream', { method: 'POST', body: formData });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message);
    }
    await readAnalysisStream(response);
  } catch (error) {
    stopDebugProgress();
    debugList.innerHTML = `<div class="empty">분석 실패: ${escapeHtml(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = '분석 ▶';
  }
});
