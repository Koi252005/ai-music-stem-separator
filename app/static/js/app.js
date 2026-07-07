/**
 * StemAI — app.js
 * Professional multi-stem audio player using Web Audio API.
 * Features: synchronized playback, mute/solo, waveform canvas, SSE job tracking.
 */

'use strict';

// ── Constants ──────────────────────────────────────────────────────────────────
const MAX_UPLOAD_MB = 200;
const SPEED_STEPS   = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

const STEM_META = {
  vocals:             { icon: '🎤', color: '#60a5fa', label: 'Vocals' },
  drums:              { icon: '🥁', color: '#f87171', label: 'Drums' },
  bass:               { icon: '🎸', color: '#a78bfa', label: 'Bass' },
  guitar:             { icon: '🎸', color: '#fb923c', label: 'Guitar' },
  piano:              { icon: '🎹', color: '#34d399', label: 'Piano' },
  other:              { icon: '🎼', color: '#94a3b8', label: 'Other' },
  electric_guitar:    { icon: '⚡', color: '#fbbf24', label: 'Electric Guitar' },
  no_electric_guitar: { icon: '🎵', color: '#6ee7b7', label: 'No Guitar' },
  backing_track:      { icon: '🎶', color: '#c084fc', label: 'Backing Track' },
  instrumental:       { icon: '🎵', color: '#c084fc', label: 'Instrumental' },
};

const STAGE_ORDER = ['preprocessing', 'loading_model', 'separating', 'postprocessing'];

// ── State ─────────────────────────────────────────────────────────────────────
let selectedFile   = null;
let selectedModel  = null;
let activeEventSource = null;   // SSE connection
const studios = {};             // jobId → StudioPlayer instance

// ── DOM ───────────────────────────────────────────────────────────────────────
const dropZone      = document.getElementById('drop-zone');
const fileInput     = document.getElementById('file-input');
const filePreview   = document.getElementById('file-preview');
const fpName        = document.getElementById('fp-name');
const fpMeta        = document.getElementById('fp-meta');
const fpRemove      = document.getElementById('fp-remove');
const startBtn      = document.getElementById('start-btn');
const modelGrid     = document.getElementById('model-grid');
const uploadWrap    = document.getElementById('upload-progress-wrap');
const uploadBar     = document.getElementById('upload-progress-bar');
const uploadPct     = document.getElementById('upload-pct');
const jobsSection   = document.getElementById('jobs-section');
const jobsList      = document.getElementById('jobs-list');
const newJobBtn     = document.getElementById('new-job-btn');
const toastCon      = document.getElementById('toast-container');

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupDropZone();
  setupFileInput();
  setupStartButton();
  fpRemove.addEventListener('click', clearFile);
  newJobBtn.addEventListener('click', () => {
    jobsSection.classList.add('hidden');
    document.getElementById('upload-section').scrollIntoView({ behavior: 'smooth' });
  });

  // Space bar = play/pause active studio
  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON') {
      e.preventDefault();
      const s = Object.values(studios).find(s => s.isActive());
      if (s) s.togglePlay();
    }
  });

  loadModels();
});

// ── Models ─────────────────────────────────────────────────────────────────────
async function loadModels() {
  try {
    const res  = await fetch('/api/models');
    const data = await res.json();
    renderModelPicker(data.models);
  } catch {
    modelGrid.innerHTML = '<p style="color:var(--t3);font-size:.82rem">Không thể tải danh sách model.</p>';
  }
}

function renderModelPicker(models) {
  modelGrid.innerHTML = '';
  models.forEach((m, i) => {
    const opt = document.createElement('label');
    opt.className = 'model-opt' + (i === 0 ? ' selected' : '');
    opt.innerHTML = `
      <input type="radio" name="model" value="${m.id}" ${i === 0 ? 'checked' : ''} />
      <div class="model-opt-name">${m.name}</div>
      <div class="model-opt-label">${m.label}</div>
      <div class="model-opt-dot"></div>
    `;
    opt.querySelector('input').addEventListener('change', () => {
      document.querySelectorAll('.model-opt').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      selectedModel = m.id;
    });
    modelGrid.appendChild(opt);
  });
  selectedModel = models[0]?.id || 'htdemucs_ft';
}

// ── Drop zone ──────────────────────────────────────────────────────────────────
function setupDropZone() {
  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const f = e.dataTransfer?.files?.[0];
    if (f) handleFile(f);
  });
  dropZone.addEventListener('click', e => {
    if (e.target.tagName !== 'LABEL' && e.target.tagName !== 'INPUT') fileInput.click();
  });
  dropZone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') fileInput.click();
  });
}

function setupFileInput() {
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
  });
}

function handleFile(file) {
  const mb = file.size / 1048576;
  if (mb > MAX_UPLOAD_MB) {
    showToast(`File quá lớn (${mb.toFixed(1)} MB). Tối đa ${MAX_UPLOAD_MB} MB.`, 'err');
    return;
  }
  selectedFile = file;
  fpName.textContent = file.name;
  fpMeta.textContent = `${fmtBytes(file.size)} · ${file.type || 'audio'}`;
  dropZone.classList.add('hidden');
  filePreview.classList.remove('hidden');
  startBtn.disabled = false;
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  filePreview.classList.add('hidden');
  dropZone.classList.remove('hidden');
  startBtn.disabled = true;
}

// ── Upload & create job ────────────────────────────────────────────────────────
function setupStartButton() {
  startBtn.addEventListener('click', async () => {
    if (!selectedFile || !selectedModel) return;

    startBtn.disabled = true;
    uploadWrap.classList.remove('hidden');
    uploadBar.style.width = '0%';
    uploadPct.textContent = '0%';

    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('model_id', selectedModel);
    fd.append('device', 'auto');

    try {
      const job = await xhrUpload('/api/jobs', fd, (pct) => {
        uploadBar.style.width = pct + '%';
        uploadPct.textContent = pct + '%';
      });

      uploadWrap.classList.add('hidden');
      uploadBar.style.width = '0%';
      clearFile();
      startBtn.innerHTML = '<svg class="btn-icon" viewBox="0 0 20 20" fill="currentColor" width="18"><path d="M8 5l8 5-8 5V5z"/></svg> Bắt đầu tách stem';
      startBtn.disabled = true;

      jobsSection.classList.remove('hidden');
      showJobCard(job);
      connectSSE(job.id);
      jobsSection.scrollIntoView({ behavior: 'smooth' });

    } catch (err) {
      uploadWrap.classList.add('hidden');
      startBtn.disabled = false;
      startBtn.innerHTML = '<svg class="btn-icon" viewBox="0 0 20 20" fill="currentColor" width="18"><path d="M8 5l8 5-8 5V5z"/></svg> Bắt đầu tách stem';
      showToast(`Lỗi upload: ${err.message}`, 'err');
    }
  });
}

function xhrUpload(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });
    xhr.addEventListener('load', () => {
      const data = JSON.parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error(data.detail || `HTTP ${xhr.status}`));
    });
    xhr.addEventListener('error', () => reject(new Error('Lỗi kết nối mạng')));
    xhr.send(formData);
  });
}

// ── Job card ───────────────────────────────────────────────────────────────────
function showJobCard(job) {
  const tpl  = document.getElementById('job-card-tpl');
  const node = tpl.content.cloneNode(true);
  const card = node.querySelector('.job-card');
  card.dataset.jobId = job.id;

  // Find sub-sections
  const procEl   = card.querySelector('.job-processing');
  const failEl   = card.querySelector('.job-failed');
  const studioEl = card.querySelector('.job-studio');

  // ── Processing state ──
  procEl.querySelector('.jp-filename').textContent = job.input_filename || 'audio';
  const cancelBtn = procEl.querySelector('.jp-cancel');
  cancelBtn.addEventListener('click', () => cancelJob(job.id));
  procEl.classList.remove('hidden');

  // ── Failed delete/retry ──
  failEl.querySelector('.jf-delete').addEventListener('click', () => {
    deleteJob(job.id, card);
  });
  failEl.querySelector('.jf-retry').addEventListener('click', () => {
    card.remove();
    startBtn.disabled = false;
    document.getElementById('upload-section').scrollIntoView({ behavior: 'smooth' });
  });

  // ── Studio delete ──
  studioEl.querySelector('.studio-delete').addEventListener('click', () => {
    deleteJob(job.id, card);
  });

  jobsList.prepend(card);
  updateJobCard(job);
}

function updateJobCard(job) {
  const card = document.querySelector(`.job-card[data-job-id="${job.id}"]`);
  if (!card) return;

  const procEl   = card.querySelector('.job-processing');
  const failEl   = card.querySelector('.job-failed');
  const studioEl = card.querySelector('.job-studio');

  if (job.status === 'completed') {
    procEl.classList.add('hidden');
    failEl.classList.add('hidden');
    studioEl.classList.remove('hidden');
    card.classList.add('completed');
    if (!studios[job.id]) {
      const studio = new StudioPlayer(job, studioEl);
      studios[job.id] = studio;
    }
    return;
  }

  if (job.status === 'failed') {
    procEl.classList.add('hidden');
    studioEl.classList.add('hidden');
    failEl.classList.remove('hidden');
    failEl.querySelector('.jf-error').textContent = job.error || 'Lỗi không xác định.';
    return;
  }

  // Processing states
  procEl.classList.remove('hidden');
  failEl.classList.add('hidden');
  studioEl.classList.add('hidden');

  // Update stage dots
  const stages = procEl.querySelectorAll('.jp-stage');
  const stageIdx = STAGE_ORDER.indexOf(job.status);
  stages.forEach((el, i) => {
    el.classList.remove('active', 'done');
    if (i < stageIdx) el.classList.add('done');
    else if (i === stageIdx) el.classList.add('active');
  });

  // Detail + elapsed
  procEl.querySelector('.jp-detail').textContent = job.stage_detail || '';
  if (job.elapsed_seconds != null) {
    procEl.querySelector('.jp-elapsed').textContent = fmtDuration(job.elapsed_seconds);
  }
}

// ── SSE ────────────────────────────────────────────────────────────────────────
function connectSSE(jobId) {
  if (activeEventSource) activeEventSource.close();
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  activeEventSource = es;

  es.addEventListener('message', e => {
    try {
      const job = JSON.parse(e.data);
      updateJobCard(job);
      if (job.status === 'completed') {
        showToast('Tách stem hoàn thành! 🎉', 'ok');
        es.close();
        activeEventSource = null;
      }
      if (job.status === 'failed') {
        showToast(`Lỗi: ${job.error}`, 'err');
        es.close();
        activeEventSource = null;
      }
    } catch {}
  });

  es.addEventListener('error', () => {
    // SSE closed (normal for completed jobs), ignore.
    es.close();
  });
}

// ── Cancel / Delete ────────────────────────────────────────────────────────────
async function cancelJob(jobId) {
  try {
    await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
    showToast('Đã hủy job.', 'ok');
    if (activeEventSource) { activeEventSource.close(); activeEventSource = null; }
    const job = await (await fetch(`/api/jobs/${jobId}`)).json();
    updateJobCard(job);
  } catch (err) {
    showToast(`Lỗi hủy: ${err.message}`, 'err');
  }
}

async function deleteJob(jobId, card) {
  if (!confirm('Xóa job và tất cả file liên quan?')) return;
  try {
    await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
    if (studios[jobId]) { studios[jobId].destroy(); delete studios[jobId]; }
    card.style.animation = 'toast-out .25s ease forwards';
    setTimeout(() => card.remove(), 260);
    const remaining = document.querySelectorAll('.job-card');
    if (!remaining.length) jobsSection.classList.add('hidden');
  } catch (err) {
    showToast(`Lỗi xóa: ${err.message}`, 'err');
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// StudioPlayer — Web Audio API synchronized multi-stem player
// ═══════════════════════════════════════════════════════════════════════════════
class StudioPlayer {
  constructor(job, containerEl) {
    this.job     = job;
    this.el      = containerEl;
    this.ctx     = new (window.AudioContext || window.webkitAudioContext)();
    this.tracks  = {};    // stemName → TrackNode
    this.startAt = 0;     // AudioContext time when we hit play
    this.pausedAt= 0;     // elapsed seconds when paused
    this.playing = false;
    this.loop    = false;
    this.speed   = 1.0;
    this.duration= 0;
    this.soloSet = new Set();
    this.masterGain = this.ctx.createGain();
    this.masterGain.connect(this.ctx.destination);

    this._raf = null;      // requestAnimationFrame id
    this._ready = false;

    this._render();
    this._loadStems();
  }

  isActive() { return this._ready; }

  // ── Render static parts ──────────────────────────────────────────────────────
  _render() {
    const el = this.el;

    // Header
    el.querySelector('.studio-filename').textContent = this.job.input_filename || 'audio';
    el.querySelector('.studio-model-badge').textContent = this.job.model_id;

    // ZIP download
    const dlBtn = el.querySelector('.studio-download-zip');
    if (this.job.download_url) {
      dlBtn.href = this.job.download_url;
    } else {
      dlBtn.classList.add('hidden');
    }

    // Elapsed
    if (this.job.elapsed_seconds) {
      el.querySelector('.studio-elapsed-note').textContent =
        `⏱ Thời gian tách: ${fmtDuration(this.job.elapsed_seconds)}`;
    }

    // Master controls
    const playBtn   = el.querySelector('.mc-play');
    const restartBtn= el.querySelector('.mc-restart');
    const loopBtn   = el.querySelector('.mc-loop-btn');
    const speedBtn  = el.querySelector('.mc-speed-btn');
    const volSlider = el.querySelector('.mc-vol');
    this._playBtn   = playBtn;
    this._timeline  = el.querySelector('.timeline-waveform');
    this._progress  = el.querySelector('.waveform-progress');
    this._playhead  = el.querySelector('.waveform-playhead');
    this._curTime   = el.querySelector('.mc-current');
    this._totTime   = el.querySelector('.mc-total');

    playBtn.addEventListener('click', () => this.togglePlay());
    restartBtn.addEventListener('click', () => this.seek(0));
    loopBtn.addEventListener('click', () => {
      this.loop = !this.loop;
      loopBtn.classList.toggle('active', this.loop);
    });
    speedBtn.addEventListener('click', () => {
      const i  = SPEED_STEPS.indexOf(this.speed);
      this.speed = SPEED_STEPS[(i + 1) % SPEED_STEPS.length];
      speedBtn.textContent = this.speed + '×';
      this._applySpeed();
    });
    volSlider.addEventListener('input', () => {
      this.masterGain.gain.value = parseFloat(volSlider.value);
    });
    this._timeline.addEventListener('click', e => {
      const rect = this._timeline.getBoundingClientRect();
      const pct  = (e.clientX - rect.left) / rect.width;
      this.seek(pct * this.duration);
    });

    // Stem tracks container
    this._tracksEl = el.querySelector('.stem-tracks');
  }

  // ── Load all stems via Web Audio API ─────────────────────────────────────────
  async _loadStems() {
    const stemEntries = Object.entries(this.job.stems || {});
    if (!stemEntries.length) return;

    // Create GainNodes first so UI is ready
    for (const [name, url] of stemEntries) {
      const gain = this.ctx.createGain();
      gain.connect(this.masterGain);
      this.tracks[name] = { gain, buffer: null, source: null, url, loaded: false };
      this._addStemTrack(name);
    }

    // Load all buffers in parallel
    const loads = stemEntries.map(([name, url]) => this._loadBuffer(name, url));
    await Promise.all(loads);

    // Calculate real duration
    this.duration = Math.max(...Object.values(this.tracks).map(t => t.buffer?.duration || 0));
    this._totTime.textContent = fmtTime(this.duration);
    this.el.querySelector('.time-total').textContent = fmtTime(this.duration);
    this._ready = true;

    // Draw master waveform (first stem)
    const [firstName] = Object.keys(this.tracks);
    if (firstName && this.tracks[firstName].buffer) {
      this._drawWaveform(this._timeline.querySelector('.waveform-canvas'), this.tracks[firstName].buffer, STEM_META[firstName]?.color);
    }
  }

  async _loadBuffer(name, url) {
    try {
      const res = await fetch(url);
      const ab  = await res.arrayBuffer();
      const buf = await this.ctx.decodeAudioData(ab);
      this.tracks[name].buffer = buf;
      this.tracks[name].loaded = true;
      // Draw waveform on stem track canvas
      const trackEl = this._tracksEl.querySelector(`.stem-track[data-stem="${name}"]`);
      if (trackEl) {
        const canvas = trackEl.querySelector('.stem-waveform-canvas');
        if (canvas) this._drawWaveform(canvas, buf, STEM_META[name]?.color);
      }
    } catch (e) {
      console.warn('Failed to load stem:', name, e);
    }
  }

  // ── Waveform drawing ─────────────────────────────────────────────────────────
  _drawWaveform(canvas, buffer, color = '#6366f1') {
    if (!canvas) return;
    const dpr  = window.devicePixelRatio || 1;
    const W    = canvas.parentElement.clientWidth || 600;
    const H    = canvas.parentElement.clientHeight || 64;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const data   = buffer.getChannelData(0);
    const step   = Math.ceil(data.length / W);
    const halfH  = H / 2;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = color + '60';

    for (let x = 0; x < W; x++) {
      let max = 0;
      for (let j = 0; j < step; j++) {
        const v = Math.abs(data[x * step + j] || 0);
        if (v > max) max = v;
      }
      const barH = max * halfH * 0.95;
      ctx.fillRect(x, halfH - barH, 1, barH * 2);
    }
  }

  // ── Stem track UI ─────────────────────────────────────────────────────────────
  _addStemTrack(name) {
    const meta = STEM_META[name] || { icon: '🎵', color: '#6366f1', label: name };
    const tpl  = document.getElementById('stem-track-tpl');
    const node = tpl.content.cloneNode(true);
    const el   = node.querySelector('.stem-track');
    el.dataset.stem = name;

    el.querySelector('.st-icon').textContent = meta.icon;
    el.querySelector('.st-name').textContent = meta.label;

    // Add small waveform canvas inside track (optional)
    // (we keep it lightweight — just a colored line)

    const muteBtn = el.querySelector('.st-mute');
    const soloBtn = el.querySelector('.st-solo');
    const volSlider = el.querySelector('.st-vol');
    const dlBtn  = el.querySelector('.st-download');

    // Volume
    volSlider.style.setProperty('accent-color', meta.color);
    volSlider.addEventListener('input', () => {
      const track = this.tracks[name];
      if (track?.gain) track.gain.gain.value = parseFloat(volSlider.value);
    });

    // Mute
    muteBtn.addEventListener('click', () => {
      const track = this.tracks[name];
      if (!track) return;
      track.muted = !track.muted;
      muteBtn.classList.toggle('active', track.muted);
      el.classList.toggle('muted', track.muted);
      this._updateGains();
    });

    // Solo
    soloBtn.addEventListener('click', () => {
      if (this.soloSet.has(name)) {
        this.soloSet.delete(name);
        soloBtn.classList.remove('active');
        el.classList.remove('soloed');
      } else {
        this.soloSet.add(name);
        soloBtn.classList.add('active');
        el.classList.add('soloed');
      }
      this._updateGains();
    });

    // Download
    dlBtn.href = this.job.stems[name];
    dlBtn.download = `${this.job.input_filename}_${name}.wav`;

    this._tracksEl.appendChild(el);
  }

  _updateGains() {
    const hasSolo = this.soloSet.size > 0;
    for (const [name, track] of Object.entries(this.tracks)) {
      if (!track.gain) continue;
      const el = this._tracksEl.querySelector(`.stem-track[data-stem="${name}"]`);
      const volEl = el?.querySelector('.st-vol');
      const vol   = parseFloat(volEl?.value || '1');
      let finalGain = vol;
      if (track.muted) finalGain = 0;
      else if (hasSolo && !this.soloSet.has(name)) finalGain = 0;
      track.gain.gain.value = finalGain;
    }
  }

  // ── Playback ──────────────────────────────────────────────────────────────────
  togglePlay() {
    if (this.playing) this.pause();
    else this.play();
  }

  play() {
    if (!this._ready || this.playing) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    // Safety: ensure any old sources are stopped before creating new ones
    for (const [, track] of Object.entries(this.tracks)) {
      try { track.source?.stop(); } catch {}
      track.source = null;
    }

    const offset = this.pausedAt;
    this.startAt = this.ctx.currentTime - offset / this.speed;

    for (const [, track] of Object.entries(this.tracks)) {
      if (!track.buffer) continue;
      const src = this.ctx.createBufferSource();
      src.buffer = track.buffer;
      src.playbackRate.value = this.speed;
      src.loop = this.loop;
      src.connect(track.gain);
      src.start(0, offset);
      track.source = src;
      // We do not use src.onended because it fires asynchronously and inconsistently
      // across different tracks. _startRaf handles the song ending perfectly.
    }

    this.playing = true;
    this._updatePlayBtn();
    this._startRaf();
  }

  pause() {
    if (!this.playing) return;
    this.pausedAt = (this.ctx.currentTime - this.startAt) * this.speed;
    for (const [, track] of Object.entries(this.tracks)) {
      try { track.source?.stop(); } catch {}
      track.source = null;
    }
    this.playing = false;
    this._updatePlayBtn();
    this._stopRaf();
  }

  seek(seconds) {
    const wasPlaying = this.playing;
    if (this.playing) this.pause();
    this.pausedAt = Math.max(0, Math.min(seconds, this.duration));
    this._updateTimeline(this.pausedAt);
    if (wasPlaying) this.play();
  }

  _applySpeed() {
    if (!this.playing) return;
    const pos = (this.ctx.currentTime - this.startAt) * this.speed;
    this.pause();
    this.pausedAt = pos;
    this.play();
  }

  _updatePlayBtn() {
    const iconPlay  = this._playBtn.querySelector('.icon-play');
    const iconPause = this._playBtn.querySelector('.icon-pause');
    iconPlay.classList.toggle('hidden', this.playing);
    iconPause.classList.toggle('hidden', !this.playing);
  }

  _startRaf() {
    const tick = () => {
      if (!this.playing) return;
      const elapsed = (this.ctx.currentTime - this.startAt) * this.speed;
      this._updateTimeline(elapsed);
      if (!this.loop && elapsed >= this.duration) {
        this.pause();
        this.pausedAt = 0;
        this._updateTimeline(0);
        return;
      }
      this._raf = requestAnimationFrame(tick);
    };
    this._raf = requestAnimationFrame(tick);
  }

  _stopRaf() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  _updateTimeline(elapsed) {
    if (this.duration <= 0) return;
    let current = elapsed;
    if (this.loop && this.playing) {
      current = current % this.duration;
    }
    const pct = Math.min(current / this.duration, 1);
    this._progress.style.width = (pct * 100) + '%';
    this._playhead.style.left  = (pct * 100) + '%';
    this._curTime.textContent  = fmtTime(current);
    this.el.querySelector('.time-current').textContent = fmtTime(current);
  }

  destroy() {
    this.pause();
    try { this.ctx.close(); } catch {}
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'ok') {
  const icon = type === 'ok' ? '✓' : '✕';
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-msg">${msg}</span>
    <button class="toast-close btn-icon" onclick="this.closest('.toast').remove()">✕</button>
  `;
  toastCon.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toast-out .25s ease forwards';
    setTimeout(() => el.remove(), 260);
  }, 4000);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function fmtTime(sec) {
  sec = Math.max(0, sec || 0);
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function fmtDuration(sec) {
  if (sec < 60) return Math.round(sec) + 's';
  return Math.floor(sec / 60) + 'm ' + Math.round(sec % 60) + 's';
}
