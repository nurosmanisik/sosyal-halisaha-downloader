const form = document.getElementById("downloadForm");
const urlInput = document.getElementById("urlInput");
const outputInput = document.getElementById("outputInput");
const outputNameInput = document.getElementById("outputNameInput");
const connectionsInput = document.getElementById("connectionsInput");
const discoverInput = document.getElementById("discoverInput");
const overwriteInput = document.getElementById("overwriteInput");
const preflightInput = document.getElementById("preflightInput");
const useYtdlpInput = document.getElementById("useYtdlpInput");
const useAriaInput = document.getElementById("useAriaInput");
const linkModeBtn = document.getElementById("linkModeBtn");
const finderModeBtn = document.getElementById("finderModeBtn");
const linkModePanel = document.getElementById("linkModePanel");
const finderModePanel = document.getElementById("finderModePanel");
const finderDateInput = document.getElementById("finderDateInput");
const finderTimeInput = document.getElementById("finderTimeInput");
const finderCityInput = document.getElementById("finderCityInput");
const finderDistrictInput = document.getElementById("finderDistrictInput");
const finderPlaceInput = document.getElementById("finderPlaceInput");
const finderFieldInput = document.getElementById("finderFieldInput");
const finderSearchBtn = document.getElementById("finderSearchBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const downloadBtn = document.getElementById("downloadBtn");
const toolsList = document.getElementById("toolsList");
const historyList = document.getElementById("historyList");
const matchList = document.getElementById("matchList");
const candidateList = document.getElementById("candidateList");
const resultBox = document.getElementById("resultBox");
const messageBox = document.getElementById("messageBox");
const resultMeta = document.getElementById("resultMeta");
const serverStatus = document.getElementById("serverStatus");
const progressPanel = document.getElementById("progressPanel");
const progressTitle = document.getElementById("progressTitle");
const progressSub = document.getElementById("progressSub");
const progressPercent = document.getElementById("progressPercent");
const progressFill = document.getElementById("progressFill");
const progressFile = document.getElementById("progressFile");
const progressBytes = document.getElementById("progressBytes");
const progressRemaining = document.getElementById("progressRemaining");
const progressSpeed = document.getElementById("progressSpeed");
const progressEta = document.getElementById("progressEta");
const progressTool = document.getElementById("progressTool");
const pauseBtn = document.getElementById("pauseBtn");
const resumeBtn = document.getElementById("resumeBtn");
const cancelBtn = document.getElementById("cancelBtn");
const revealBtn = document.getElementById("revealBtn");
const copyPathBtn = document.getElementById("copyPathBtn");
const newLinkBtn = document.getElementById("newLinkBtn");

let selectedUrl = "";
let selectedMatchUrl = "";
let currentMode = "link";
let activeJobId = "";
let activeJobPath = "";
let progressTimer = null;
let finderDefaults = {};
let fieldsRequestSeq = 0;

function payload() {
  return {
    url: urlInput.value.trim(),
    output: outputInput.value.trim(),
    output_name: outputNameInput.value.trim(),
    connections: connectionsInput.value,
    discover_cameras: discoverInput.checked,
    overwrite: overwriteInput.checked,
    no_preflight: preflightInput.checked,
    use_ytdlp: useYtdlpInput.checked,
    use_aria2: useAriaInput.checked,
    selected_url: selectedUrl || undefined
  };
}

function finderPayload() {
  return {
    date: finderDateInput.value,
    time: finderTimeInput.value,
    city_id: finderCityInput.value,
    district_id: finderDistrictInput.value,
    place_id: finderPlaceInput.value,
    city: selectedOptionText(finderCityInput),
    district: selectedOptionText(finderDistrictInput),
    place: selectedOptionText(finderPlaceInput),
    field: finderFieldInput.value,
    connections: connectionsInput.value,
    no_preflight: preflightInput.checked
  };
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const data = await response.json();
  if (!response.ok || data.status === "error") {
    throw new Error(data.error || "Islem basarisiz oldu.");
  }
  return data;
}

function setBusy(isBusy, text = "Calisiyor") {
  analyzeBtn.disabled = isBusy;
  downloadBtn.disabled = isBusy;
  finderSearchBtn.disabled = isBusy;
  serverStatus.textContent = isBusy ? text : "Hazir";
}

function showMessage(text, type = "info") {
  messageBox.textContent = text;
  messageBox.className = `message ${type}`;
}

function clearMessage() {
  messageBox.textContent = "";
  messageBox.className = "message hidden";
}

function renderTools(data) {
  toolsList.innerHTML = Object.entries({
    "yt-dlp": data.yt_dlp,
    "aria2c": data.aria2c,
    "ffmpeg": data.ffmpeg
  }).map(([name, ok]) => `
    <div class="tool">
      <strong>${name}</strong>
      <span class="${ok ? "ok" : "bad"}">${ok ? "var" : "yok"}</span>
    </div>
  `).join("");
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = `<div class="history-item">Gecmis yok.</div>`;
    return;
  }
  historyList.innerHTML = items.slice().reverse().map(item => `
    <div class="history-item">
      <strong>${formatBytes(item.size)} · ${formatSeconds(item.elapsed_seconds)}</strong>
      <code>${escapeHTML(item.path)}</code>
    </div>
  `).join("");
}

function renderCandidates(data) {
  selectedUrl = data.selected_url;
  resultMeta.textContent = `${data.candidates.length} video`;
  if (!data.candidates.length) {
    candidateList.innerHTML = `<div class="empty-state">Video linki bulunamadi.</div>`;
    return;
  }
  candidateList.innerHTML = data.candidates.map((candidate, index) => `
    <div class="candidate video-card ${candidate.url === selectedUrl ? "selected" : ""}" data-url="${escapeHTML(candidate.url)}">
      <div class="candidate-top">
        <strong>${index + 1}. ${escapeHTML(candidate.filename)}</strong>
        <span>${escapeHTML(candidate.type)}</span>
      </div>
      <code>${escapeHTML(candidate.url)}</code>
    </div>
  `).join("");
  candidateList.querySelectorAll(".candidate").forEach(item => {
    item.addEventListener("click", () => {
      selectedUrl = item.dataset.url;
      candidateList.querySelectorAll(".candidate").forEach(node => node.classList.remove("selected"));
      item.classList.add("selected");
    });
  });
  if (data.preflight) {
    resultBox.innerHTML = metrics([
      ["Boyut", data.preflight.size_text],
      ["Icerik", data.preflight.content_type || "bilinmiyor"],
      ["Parcali", data.preflight.range_supported === null ? "bilinmiyor" : (data.preflight.range_supported ? "var" : "yok")],
      ["Baglanti", String(data.connections)]
    ]);
  } else {
    resultBox.innerHTML = metrics([["Baglanti", String(data.connections)]]);
  }
}

function renderFinderMatches(data) {
  selectedUrl = "";
  candidateList.innerHTML = "";
  resultMeta.textContent = `${data.matches.length} mac`;
  if (!data.matches.length) {
    matchList.innerHTML = `<div class="empty-state">Bu filtreyle mac bulunamadi. Tarih, saat veya saha secimini kontrol et.</div>`;
    resultBox.innerHTML = "";
    showMessage(data.message || "Mac bulunamadi.", "error");
    return;
  }
  selectedMatchUrl = data.preferred_url || data.matches[0].url;
  matchList.innerHTML = data.matches.map((match, index) => `
    <div class="candidate match-card ${match.url === selectedMatchUrl ? "selected" : ""}" data-match-url="${escapeHTML(match.url)}">
      <div class="candidate-top">
        <strong>${index + 1}. ${escapeHTML(match.title)}</strong>
        <span>${match.score >= 80 ? "Eslesen" : "Alternatif"}</span>
      </div>
      <div class="match-meta">
        <span>${escapeHTML(match.date || "Tarih yok")}</span>
        <span>${escapeHTML(match.place_name || "Tesis yok")}</span>
        <span>${match.watch_count === null || match.watch_count === undefined ? "Izlenme yok" : `${match.watch_count} izlenme`}</span>
      </div>
      <code>${escapeHTML(match.url)}</code>
    </div>
  `).join("");
  matchList.querySelectorAll(".candidate").forEach(item => {
    item.addEventListener("click", () => {
      selectedMatchUrl = item.dataset.matchUrl;
      selectedUrl = "";
      matchList.querySelectorAll(".candidate").forEach(node => node.classList.remove("selected"));
      item.classList.add("selected");
      candidateList.innerHTML = "";
      extractSelectedMatch().catch(error => showMessage(error.message, "error"));
    });
  });
  resultBox.innerHTML = metrics([
    ["Eslesme", data.preferred_url ? "Secilen saha bulundu" : "Manuel secim gerekli"],
    ["Kaynak", data.source || "http"],
    ["Mac detay", selectedMatchUrl],
    ["Filtre", data.filter_url]
  ]);
  showMessage(data.message || "Mac arama tamamlandi.", "info");
  extractSelectedMatch().catch(error => showMessage(error.message, "error"));
}

function renderDownloadResult(data) {
  resultMeta.textContent = "Tamamlandi";
  resultBox.innerHTML = metrics([
    ["Konum", data.path],
    ["Sure", data.duration],
    ["Boyut", data.size_text],
    ["Ortalama hiz", data.average_speed_text],
    ["Baglanti", String(data.connections)],
    ["Parcali", data.range_supported === null ? "bilinmiyor" : (data.range_supported ? "var" : "yok")]
  ]);
}

function showProgress() {
  progressPanel.classList.remove("hidden");
}

function hideProgress() {
  progressPanel.classList.add("hidden");
  progressPanel.dataset.status = "";
}

function renderProgress(job) {
  showProgress();
  activeJobPath = job.path || activeJobPath;
  const percent = job.percent === null || job.percent === undefined ? 0 : Number(job.percent);
  const clamped = Math.max(0, Math.min(100, percent));
  progressPanel.dataset.status = job.status || "";
  progressTitle.textContent = statusTitle(job.status);
  progressSub.textContent = progressSubtitle(job);
  progressPercent.textContent = job.percent === null || job.percent === undefined ? "--" : `${clamped.toFixed(clamped >= 10 ? 0 : 1)}%`;
  progressFill.style.width = `${clamped}%`;
  progressFile.textContent = job.file_name || "dosya hazirlaniyor";
  progressBytes.textContent = `${job.downloaded_text || "bilinmiyor"} / ${job.total_text || "bilinmiyor"}`;
  progressRemaining.textContent = job.remaining_text || "hesaplaniyor";
  progressSpeed.textContent = job.speed_text || "bilinmiyor";
  progressEta.textContent = job.eta_text || "hesaplaniyor";
  progressTool.textContent = job.tool ? `${job.tool} · ${job.connections || "-"} baglanti` : "bekleniyor";
  pauseBtn.disabled = job.status !== "running";
  resumeBtn.disabled = !["paused", "failed", "cancelled"].includes(job.status);
  cancelBtn.disabled = !["queued", "running", "paused"].includes(job.status);
  revealBtn.disabled = job.status !== "completed" || !job.path;
  copyPathBtn.disabled = !job.path;
  serverStatus.textContent = statusTitle(job.status);
  if (job.status === "completed") {
    renderDownloadResult(job);
  }
}

function statusTitle(status) {
  return {
    queued: "Sirada",
    running: "Indiriliyor",
    paused: "Duraklatildi",
    cancelled: "Iptal edildi",
    failed: "Hata",
    completed: "Tamamlandi"
  }[status] || "Durum";
}

function progressSubtitle(job) {
  if (job.status === "running" && job.progress_quality === "estimated") {
    return "Kalan sure anlik hizdan hesaplandi.";
  }
  if (job.status === "running" && job.progress_quality === "limited") {
    return "Indirme suruyor, kalan sure hesaplaniyor.";
  }
  return job.message || "";
}

function stopProgressTimer() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

async function pollJob(jobId) {
  const job = await requestJSON(`/api/jobs/${jobId}`);
  renderProgress(job);
  if (["completed", "failed", "cancelled", "paused"].includes(job.status)) {
    stopProgressTimer();
    setBusy(false);
    if (job.status === "completed") {
      showMessage("Indirme tamamlandi.", "info");
      await loadHistory();
    } else if (job.status === "failed") {
      showMessage(job.error || "Indirme basarisiz oldu.", "error");
    } else if (job.status === "cancelled") {
      showMessage("Indirme iptal edildi. Yarım dosya resume icin korunur.", "info");
    } else if (job.status === "paused") {
      showMessage("Indirme duraklatildi. Devam Et ile kaldigi yerden surebilir.", "info");
    }
  }
}

function startProgressPolling(jobId) {
  activeJobId = jobId;
  stopProgressTimer();
  progressTimer = setInterval(() => {
    pollJob(jobId).catch(error => {
      stopProgressTimer();
      setBusy(false);
      showMessage(error.message, "error");
    });
  }, 1000);
  pollJob(jobId).catch(error => showMessage(error.message, "error"));
}

function metrics(items) {
  return `<div class="metric-grid">${items.map(([label, value]) => `
    <div class="metric">
      <span>${escapeHTML(label)}</span>
      <strong>${escapeHTML(value || "bilinmiyor")}</strong>
    </div>
  `).join("")}</div>`;
}

async function loadTools() {
  renderTools(await requestJSON("/api/tools"));
}

async function loadHistory() {
  renderHistory(await requestJSON("/api/history?limit=8"));
}

async function analyze() {
  clearMessage();
  resultBox.innerHTML = "";
  matchList.innerHTML = "";
  candidateList.innerHTML = "";
  hideProgress();
  if (currentMode === "finder") {
    await findMatches();
    return;
  }
  setBusy(true, "Analiz");
  try {
    const data = await requestJSON("/api/dry-run", {
      method: "POST",
      body: JSON.stringify(payload())
    });
    renderCandidates(data);
    showMessage("Analiz tamamlandi.", "info");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function findMatches() {
  setBusy(true, "Mac araniyor");
  selectedUrl = "";
  selectedMatchUrl = "";
  matchList.innerHTML = `<div class="empty-state loading">Maclar araniyor...</div>`;
  candidateList.innerHTML = "";
  try {
    const data = await requestJSON("/api/finder/search", {
      method: "POST",
      body: JSON.stringify(finderPayload())
    });
    renderFinderMatches(data);
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function loadFinderFields() {
  const requestId = ++fieldsRequestSeq;
  if (!finderCityInput.value || !finderDistrictInput.value || !finderPlaceInput.value || !finderDateInput.value || !finderTimeInput.value) {
    renderOptions(finderFieldInput, [{ id: "Üst Saha", name: "Üst Saha" }], "Saha sec");
    finderFieldInput.value = "Üst Saha";
    return;
  }
  try {
    renderOptions(finderFieldInput, [], "Sahalar yukleniyor");
    const fields = await requestJSON("/api/finder/fields", {
      method: "POST",
      body: JSON.stringify(finderPayload())
    });
    if (requestId !== fieldsRequestSeq) return;
    const options = fields.map(item => ({ id: item.name, name: item.name }));
    if (!options.length) {
      renderOptions(finderFieldInput, [{ id: "Üst Saha", name: "Üst Saha" }], "Saha sec");
      finderFieldInput.value = "Üst Saha";
      return;
    }
    renderOptions(finderFieldInput, options, "Saha sec");
    selectByText(finderFieldInput, finderDefaults.field || "Üst Saha");
  } catch (error) {
    if (requestId !== fieldsRequestSeq) return;
    renderOptions(finderFieldInput, [{ id: "Üst Saha", name: "Üst Saha" }], "Saha sec");
    finderFieldInput.value = "Üst Saha";
  }
}

async function extractSelectedMatch({ quiet = false } = {}) {
  if (!selectedMatchUrl) return false;
  if (!quiet) setBusy(true, "Video araniyor");
  candidateList.innerHTML = `<div class="empty-state loading">Video linkleri getiriliyor...</div>`;
  try {
    const data = await requestJSON("/api/finder/extract", {
      method: "POST",
      body: JSON.stringify({ ...finderPayload(), match_url: selectedMatchUrl })
    });
    renderCandidates(data);
    showMessage("Mac ve video linki bulundu.", "info");
    return true;
  } catch (error) {
    showMessage(error.message, "error");
    return false;
  } finally {
    if (!quiet) setBusy(false);
  }
}

async function download(event) {
  event.preventDefault();
  clearMessage();
  resultBox.innerHTML = "";
  setBusy(true, "Indiriliyor");
  try {
    if (!selectedUrl && currentMode === "finder" && selectedMatchUrl) {
      await extractSelectedMatch({ quiet: true });
    }
    const url = selectedUrl || urlInput.value.trim();
    if (!url) {
      throw new Error("Lutfen once link girin veya Maci Bul ile video secin.");
    }
    const data = await requestJSON("/api/download", {
      method: "POST",
      body: JSON.stringify({ ...payload(), url })
    });
    showMessage("Indirme basladi.", "info");
    startProgressPolling(data.job_id);
  } catch (error) {
    showMessage(error.message, "error");
    setBusy(false);
  }
}

function setMode(mode) {
  currentMode = mode;
  const finder = mode === "finder";
  finderModePanel.classList.toggle("hidden", !finder);
  linkModePanel.classList.toggle("hidden", finder);
  finderModeBtn.classList.toggle("active", finder);
  linkModeBtn.classList.toggle("active", !finder);
  analyzeBtn.textContent = finder ? "Maci Bul" : "Analiz Et";
  downloadBtn.textContent = finder ? "Bulunan Videoyu Indir" : "Secili Videoyu Indir";
  clearMessage();
}

function clearFinderResults() {
  selectedUrl = "";
  selectedMatchUrl = "";
  matchList.innerHTML = "";
  candidateList.innerHTML = "";
  resultMeta.textContent = "";
  resultBox.innerHTML = "";
  fieldsRequestSeq += 1;
}

async function loadFinderDefaults() {
  finderDefaults = await requestJSON("/api/finder/defaults");
  const defaults = finderDefaults;
  finderDateInput.value = defaults.date || new Date().toISOString().slice(0, 10);
  finderTimeInput.value = defaults.time || "11:00";
  await loadCities(defaults.city || "İstanbul");
  await loadDistricts(defaults.district || "Üsküdar");
  await loadPlaces(defaults.place || "Ufuk Halı Saha");
  await loadFinderFields();
}

async function loadCities(selectedText = "") {
  renderOptions(finderCityInput, [], "Iller yukleniyor");
  const cities = await requestJSON("/api/finder/cities");
  renderOptions(finderCityInput, cities, "Il sec");
  selectByText(finderCityInput, selectedText);
}

async function loadDistricts(selectedText = "") {
  renderOptions(finderDistrictInput, [], "Ilceler yukleniyor");
  renderOptions(finderPlaceInput, [], "Once ilce sec");
  if (!finderCityInput.value) return;
  const districts = await requestJSON(`/api/finder/districts?city_id=${encodeURIComponent(finderCityInput.value)}`);
  renderOptions(finderDistrictInput, districts, "Ilce sec");
  selectByText(finderDistrictInput, selectedText);
}

async function loadPlaces(selectedText = "") {
  renderOptions(finderPlaceInput, [], "Tesisler yukleniyor");
  if (!finderDistrictInput.value) return;
  const places = await requestJSON(`/api/finder/places?district_id=${encodeURIComponent(finderDistrictInput.value)}`);
  renderOptions(finderPlaceInput, places, "Tesis sec");
  selectByText(finderPlaceInput, selectedText);
}

function renderOptions(select, options, placeholder) {
  select.innerHTML = [`<option value="">${escapeHTML(placeholder)}</option>`]
    .concat(options.map(option => `<option value="${escapeHTML(option.id)}">${escapeHTML(option.name)}</option>`))
    .join("");
}

function selectByText(select, text) {
  const wanted = normalizeText(text);
  for (const option of select.options) {
    if (normalizeText(option.textContent) === wanted) {
      select.value = option.value;
      return true;
    }
  }
  for (const option of select.options) {
    if (normalizeText(option.textContent).includes(wanted) || wanted.includes(normalizeText(option.textContent))) {
      select.value = option.value;
      return true;
    }
  }
  return false;
}

function selectedOptionText(select) {
  return select.selectedOptions[0] ? select.selectedOptions[0].textContent : "";
}

function normalizeText(value) {
  return String(value || "")
    .toLocaleLowerCase("tr-TR")
    .replaceAll("ı", "i")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

async function controlJob(action) {
  if (!activeJobId) return;
  clearMessage();
  try {
    const job = await requestJSON(`/api/jobs/${activeJobId}/${action}`, { method: "POST" });
    renderProgress(job);
    if (action === "resume") {
      setBusy(true, "Indiriliyor");
      startProgressPolling(activeJobId);
      showMessage("Indirme devam ediyor.", "info");
    } else if (action === "pause") {
      showMessage("Indirme duraklatildi.", "info");
      setBusy(false);
    } else if (action === "cancel") {
      showMessage("Indirme iptal edildi.", "info");
      setBusy(false);
    }
  } catch (error) {
    showMessage(error.message, "error");
    setBusy(false);
  }
}

async function revealActiveJob() {
  if (!activeJobId) return;
  try {
    await requestJSON(`/api/jobs/${activeJobId}/reveal`, { method: "POST" });
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function copyActivePath() {
  if (!activeJobPath) return;
  try {
    await navigator.clipboard.writeText(activeJobPath);
    showMessage("Dosya yolu kopyalandi.", "info");
  } catch (error) {
    showMessage("Dosya yolu kopyalanamadi.", "error");
  }
}

function resetForNewLink() {
  stopProgressTimer();
  activeJobId = "";
  activeJobPath = "";
  selectedUrl = "";
  selectedMatchUrl = "";
  urlInput.value = "";
  resultMeta.textContent = "";
  resultBox.innerHTML = "";
  matchList.innerHTML = "";
  candidateList.innerHTML = "";
  hideProgress();
  clearMessage();
  setBusy(false);
  urlInput.focus();
}

function formatBytes(value) {
  if (value === null || value === undefined) return "bilinmiyor";
  let size = Number(value);
  for (const unit of ["B", "KB", "MB", "GB"]) {
    if (size < 1024 || unit === "GB") {
      return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
    }
    size /= 1024;
  }
  return `${size.toFixed(1)} GB`;
}

function formatSeconds(value) {
  const total = Math.round(Number(value || 0));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes ? `${minutes} dk ${seconds} sn` : `${seconds} sn`;
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

analyzeBtn.addEventListener("click", analyze);
form.addEventListener("submit", download);
linkModeBtn.addEventListener("click", () => setMode("link"));
finderModeBtn.addEventListener("click", () => setMode("finder"));
finderSearchBtn.addEventListener("click", findMatches);
finderCityInput.addEventListener("change", async () => {
  clearFinderResults();
  await loadDistricts();
  await loadPlaces();
  await loadFinderFields();
});
finderDistrictInput.addEventListener("change", async () => {
  clearFinderResults();
  await loadPlaces();
  await loadFinderFields();
});
finderPlaceInput.addEventListener("change", () => {
  clearFinderResults();
  loadFinderFields().catch(() => {});
});
finderDateInput.addEventListener("change", () => {
  clearFinderResults();
  loadFinderFields().catch(() => {});
});
finderTimeInput.addEventListener("change", () => {
  clearFinderResults();
  loadFinderFields().catch(() => {});
});
finderFieldInput.addEventListener("change", () => {
  clearFinderResults();
});
pauseBtn.addEventListener("click", () => controlJob("pause"));
resumeBtn.addEventListener("click", () => controlJob("resume"));
cancelBtn.addEventListener("click", () => controlJob("cancel"));
revealBtn.addEventListener("click", revealActiveJob);
copyPathBtn.addEventListener("click", copyActivePath);
newLinkBtn.addEventListener("click", resetForNewLink);
document.getElementById("refreshToolsBtn").addEventListener("click", loadTools);
document.getElementById("refreshHistoryBtn").addEventListener("click", loadHistory);

loadTools().catch(() => showMessage("Arac durumu okunamadi.", "error"));
loadHistory().catch(() => {});
loadFinderDefaults().catch(() => {});
