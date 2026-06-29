/**
 * StemAI — app.js
 * Handles file upload, job polling, stem rendering and downloads.
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const POLL_INTERVAL_MS = 2500;
const MAX_UPLOAD_MB    = 200;

const MODEL_DESCRIPTIONS = {
  guitar:        "Tách electric guitar chuyên dụng bằng MelBand-Roformer Guitar (becruily). Output: electric_guitar + no_electric_guitar.",
  htdemucs_ft:   "4-stem separation: vocals, drums, bass, other. 'other' chứa keys, synth và mọi thứ không được tách riêng.",
  htdemucs_6s:   "6-stem: vocals, drums, bass, guitar, piano, other. Thêm guitar và piano so với Stem Basic.",
  vocal_hq:      "Vocal chất lượng cao dùng htdemucs_ft. Cùng model với Stem Basic nhưng ưu tiên vocal.",
};

const STEM_ICONS = {
  vocals:             "🎤",
  electric_guitar:    "🎸",
  no_electric_guitar: "🎵",
  drums:              "🥁",
  bass:               "🎸",
  guitar:             "🎸",
  piano:              "🎹",
  other:              "🎼",
  backing_track:      "🎶",
  instrumental:       "🎵",
};

const STATUS_LABELS = {
  queued:          "Đang chờ trong hàng…",
  preprocessing:   "Đang chuẩn bị file…",
  loading_model:   "Đang tải model AI…",
  separating:      "Đang tách stem…",
  postprocessing:  "Đang xử lý kết quả…",
  mixing:          "Đang tạo backing track…",
  completed:       "Hoàn thành ✓",
  failed:          "Thất bại ✗",
};

const PROCESSING_STATUSES = new Set([
  "queued", "preprocessing", "loading_model", "separating", "postprocessing", "mixing"
]);

// ── State ─────────────────────────────────────────────────────────────────────
let selectedFile   = null;
const activePollers = {}; // job_id → intervalId

// ── DOM refs ──────────────────────────────────────────────────────────────────
const dropZone       = document.getElementById("drop-zone");
const fileInput      = document.getElementById("file-input");
const filePreview    = document.getElementById("file-preview");
const fileName       = document.getElementById("file-name");
const fileSize       = document.getElementById("file-size");
const removeFileBtn  = document.getElementById("remove-file-btn");
const startBtn       = document.getElementById("start-btn");
const modelSelect    = document.getElementById("model-select");
const deviceSelect   = document.getElementById("device-select");
const modelDesc      = document.getElementById("model-desc");
const jobsSection    = document.getElementById("jobs-section");
const jobsList       = document.getElementById("jobs-list");
const modelsGrid     = document.getElementById("models-grid");

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  updateModelDesc();
  loadModelsGrid();
  setupDropZone();
  setupFileInput();
  setupStartButton();
  modelSelect.addEventListener("change", updateModelDesc);
  removeFileBtn.addEventListener("click", clearFile);
});

// ── Model description ─────────────────────────────────────────────────────────
function updateModelDesc() {
  modelDesc.textContent = MODEL_DESCRIPTIONS[modelSelect.value] || "";
}

// ── Models grid ───────────────────────────────────────────────────────────────
async function loadModelsGrid() {
  try {
    const res = await fetch("/api/models");
    const { models } = await res.json();
    modelsGrid.innerHTML = "";
    models.forEach(m => {
      const card = document.createElement("div");
      card.className = "model-card";
      card.innerHTML = `
        <div class="model-card-name">${m.name}</div>
        <div class="model-card-desc">${m.description}</div>
        <div class="model-card-stems">
          ${m.stems.map(s => `<span>${s}</span>`).join("")}
        </div>
        ${m.note ? `<div class="model-card-note">ℹ️ ${m.note}</div>` : ""}
      `;
      modelsGrid.appendChild(card);
    });
  } catch {
    modelsGrid.innerHTML = "<p style='color:var(--text-muted)'>Không thể tải danh sách model.</p>";
  }
}

// ── Drop zone ─────────────────────────────────────────────────────────────────
function setupDropZone() {
  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  });
  dropZone.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });
  dropZone.addEventListener("click", e => {
    if (e.target.tagName !== "LABEL" && e.target.tagName !== "INPUT") {
      fileInput.click();
    }
  });
}

function setupFileInput() {
  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
  });
}

function handleFile(file) {
  const maxBytes = MAX_UPLOAD_MB * 1024 * 1024;
  if (file.size > maxBytes) {
    alert(`File quá lớn (${(file.size / 1024 / 1024).toFixed(1)} MB). Tối đa ${MAX_UPLOAD_MB} MB.`);
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  dropZone.classList.add("hidden");
  filePreview.classList.remove("hidden");
  startBtn.disabled = false;
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  filePreview.classList.add("hidden");
  dropZone.classList.remove("hidden");
  startBtn.disabled = true;
}

// ── Upload & create job ───────────────────────────────────────────────────────
function setupStartButton() {
  startBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    startBtn.disabled = true;
    startBtn.textContent = "Đang upload…";

    const fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("model_id", modelSelect.value);
    fd.append("device", deviceSelect.value);

    try {
      const res = await fetch("/api/jobs", { method: "POST", body: fd });
      const job = await res.json();
      if (!res.ok) {
        alert(`Lỗi: ${job.detail || "Upload thất bại"}`);
        startBtn.disabled = false;
        startBtn.innerHTML = '<span class="btn-icon-left">🚀</span> Bắt đầu tách stem';
        return;
      }
      // Success: clear file, show jobs section, render card
      clearFile();
      startBtn.innerHTML = '<span class="btn-icon-left">🚀</span> Bắt đầu tách stem';
      jobsSection.classList.remove("hidden");
      prependJobCard(job);
      startPolling(job.id);

      // Smooth scroll to jobs
      document.getElementById("jobs-section").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      alert(`Lỗi kết nối: ${err.message}`);
      startBtn.disabled = false;
      startBtn.innerHTML = '<span class="btn-icon-left">🚀</span> Bắt đầu tách stem';
    }
  });
}

// ── Job card rendering ────────────────────────────────────────────────────────
function prependJobCard(job) {
  const tmpl = document.getElementById("job-card-template").content.cloneNode(true);
  const card = tmpl.querySelector(".job-card");
  card.dataset.jobId = job.id;
  card.querySelector(".job-filename").textContent = job.input_filename || "audio";
  card.querySelector(".job-model-badge").textContent = job.model_id;

  const deleteBtn = card.querySelector(".job-delete-btn");
  deleteBtn.addEventListener("click", () => deleteJob(job.id));

  jobsList.prepend(card);
  updateJobCard(job);
}

function updateJobCard(job) {
  const card = document.querySelector(`.job-card[data-job-id="${job.id}"]`);
  if (!card) return;

  // Status dot
  const dot = card.querySelector(".job-status-dot");
  dot.className = "job-status-dot " + (
    PROCESSING_STATUSES.has(job.status) ? "processing" : job.status
  );

  // Status text
  card.querySelector(".job-status-text").textContent =
    (STATUS_LABELS[job.status] || job.status) +
    (job.stage_detail && job.status !== "completed" && job.status !== "failed"
      ? ` — ${job.stage_detail}` : "");

  // Elapsed
  if (job.elapsed_seconds != null) {
    card.querySelector(".job-elapsed").textContent = formatDuration(job.elapsed_seconds);
  }

  // Progress bar
  const progressWrap = card.querySelector(".job-progress-bar-wrap");
  if (PROCESSING_STATUSES.has(job.status)) {
    progressWrap.classList.remove("hidden");
  } else {
    progressWrap.classList.add("hidden");
  }

  // Error
  const errorBox = card.querySelector(".job-error-box");
  if (job.status === "failed" && job.error) {
    errorBox.classList.remove("hidden");
    errorBox.textContent = job.error;
  } else {
    errorBox.classList.add("hidden");
  }

  // Stems
  if (job.status === "completed" && job.stems && Object.keys(job.stems).length > 0) {
    const stemsSection = card.querySelector(".job-stems-section");
    stemsSection.classList.remove("hidden");
    renderStems(card, job);
  }
}

function renderStems(card, job) {
  const grid = card.querySelector(".stems-grid");
  if (grid.dataset.rendered) return; // avoid re-rendering
  grid.dataset.rendered = "1";

  const stemTmpl = document.getElementById("stem-card-template");

  for (const [stemName, stemUrl] of Object.entries(job.stems)) {
    const sc = stemTmpl.content.cloneNode(true);
    const stemCard = sc.querySelector(".stem-card");

    stemCard.querySelector(".stem-icon").textContent =
      STEM_ICONS[stemName] || "🎵";
    stemCard.querySelector(".stem-name").textContent =
      formatStemName(stemName);

    const audio = stemCard.querySelector(".stem-audio");
    audio.src = stemUrl;

    const dlBtn = stemCard.querySelector(".stem-download-btn");
    dlBtn.href = stemUrl;
    dlBtn.download = `${job.input_filename}_${stemName}.wav`;

    grid.appendChild(stemCard);
  }

  // ZIP button
  if (job.download_url) {
    const dlBtn = card.querySelector(".job-download-all-btn");
    dlBtn.href = job.download_url;
    dlBtn.download = `${job.input_filename}_stems.zip`;
  }
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling(jobId) {
  if (activePollers[jobId]) return;
  activePollers[jobId] = setInterval(() => pollJob(jobId), POLL_INTERVAL_MS);
}

async function pollJob(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) { stopPolling(jobId); return; }
    const job = await res.json();
    updateJobCard(job);
    if (!PROCESSING_STATUSES.has(job.status)) {
      stopPolling(jobId);
    }
  } catch {
    // Network error — keep polling
  }
}

function stopPolling(jobId) {
  clearInterval(activePollers[jobId]);
  delete activePollers[jobId];
}

// ── Delete job ────────────────────────────────────────────────────────────────
async function deleteJob(jobId) {
  if (!confirm("Xoá job này và tất cả file liên quan?")) return;
  stopPolling(jobId);
  try {
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
  } catch { /* ignore */ }
  const card = document.querySelector(`.job-card[data-job-id="${jobId}"]`);
  if (card) {
    card.style.opacity = "0";
    card.style.transform = "translateX(40px)";
    card.style.transition = "opacity .3s, transform .3s";
    setTimeout(() => card.remove(), 320);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatStemName(name) {
  const map = {
    electric_guitar:    "Electric Guitar",
    no_electric_guitar: "No Electric Guitar",
    vocals:             "Vocals",
    drums:              "Drums",
    bass:               "Bass",
    guitar:             "Guitar",
    piano:              "Piano",
    other:              "Other",
    backing_track:      "Backing Track",
    instrumental:       "Instrumental",
  };
  return map[name] || name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}
