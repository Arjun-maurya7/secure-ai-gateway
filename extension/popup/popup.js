// popup.js - Popup logic for Secure AI Gateway extension

document.addEventListener("DOMContentLoaded", async () => {
  const guardToggle = document.getElementById("guardToggle");
  const statusDot = document.getElementById("statusDot");
  const statusTitle = document.getElementById("statusTitle");
  const statusDesc = document.getElementById("statusDesc");
  const statTotal = document.getElementById("statTotal");
  const statBlocked = document.getElementById("statBlocked");
  const statAllowed = document.getElementById("statAllowed");
  const logsContainer = document.getElementById("logsContainer");
  const backendUrlInput = document.getElementById("backendUrlInput");
  const saveConfigBtn = document.getElementById("saveConfigBtn");
  const refreshBtn = document.getElementById("refreshBtn");

  async function loadState() {
    const data = await chrome.storage.local.get(["config", "stats"]);
    const config = data.config || { enabled: true, backendUrl: "http://localhost:8000/v1/scan" };
    const stats = data.stats || { totalScans: 0, blockedCount: 0, allowedCount: 0, logs: [] };

    guardToggle.checked = config.enabled;
    backendUrlInput.value = config.backendUrl || "http://localhost:8000/v1/scan";

    updateStatusDisplay(config.enabled);

    statTotal.innerText = stats.totalScans || 0;
    statBlocked.innerText = stats.blockedCount || 0;
    statAllowed.innerText = stats.allowedCount || 0;

    renderLogs(stats.logs || []);
  }

  function updateStatusDisplay(enabled) {
    if (enabled) {
      statusDot.className = "status-indicator online";
      statusTitle.innerText = "Gateway Protected";
      statusDesc.innerText = "Scanning prompts against DLP Gateway";
    } else {
      statusDot.className = "status-indicator offline";
      statusTitle.innerText = "Protection Paused";
      statusDesc.innerText = "Prompts are passing without inspection";
    }
  }

  function renderLogs(logs) {
    if (!logs || logs.length === 0) {
      logsContainer.innerHTML = `<div class="empty-state">No scans recorded yet. Try typing a prompt on ChatGPT or Gemini!</div>`;
      return;
    }

    logsContainer.innerHTML = logs.map(log => `
      <div class="log-item">
        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 220px;">
          <div style="font-weight: 600; color: #f0f6fc;">${log.source}</div>
          <div style="color: #8b949e; font-size: 10px;">${escapeHtml(log.preview)}</div>
        </div>
        <span class="log-badge ${log.allowed ? 'badge-allowed' : 'badge-blocked'}">
          ${log.allowed ? 'ALLOW' : 'BLOCK'}
        </span>
      </div>
    `).join('');
  }

  guardToggle.addEventListener("change", async () => {
    const storage = await chrome.storage.local.get("config");
    const config = storage.config || {};
    config.enabled = guardToggle.checked;
    await chrome.storage.local.set({ config });
    updateStatusDisplay(config.enabled);
  });

  saveConfigBtn.addEventListener("click", async () => {
    const newUrl = backendUrlInput.value.trim();
    if (!newUrl) return;

    const storage = await chrome.storage.local.get("config");
    const config = storage.config || {};
    config.backendUrl = newUrl;
    await chrome.storage.local.set({ config });

    saveConfigBtn.innerText = "Saved!";
    setTimeout(() => { saveConfigBtn.innerText = "Save"; }, 1500);
  });

  refreshBtn.addEventListener("click", loadState);

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  await loadState();
});
