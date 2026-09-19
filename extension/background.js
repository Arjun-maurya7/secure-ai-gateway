// background.js - Central Service Worker for Secure AI Gateway Extension
// Integrated with the main FastAPI /v1/redact endpoint.
//
// Response contract returned to network_interceptor.js:
//
//   ALLOW  → { allowed: true,  action: "ALLOW",  sanitized_text: <original>, entities: [] }
//   REDACT → { allowed: true,  action: "REDACT", sanitized_text: <redacted>,  entities: [...] }
//   BLOCK  → { allowed: false, action: "BLOCK",  reason: "...",               entities: [...] }
//
// Backend availability failures are distinct from policy blocks:
//   ERROR  → { allowed: false, action: "BLOCK", error: true, reason: "...", entities: [] }

const DEFAULT_CONFIG = {
  // Points to the main project's /v1/redact endpoint.
  // Change via chrome.storage ("UPDATE_CONFIG") to point at a different host.
  backendUrl: "http://localhost:8000/v1/redact",
  enabled: true
};

// ---------------------------------------------------------------------------
// Install / startup
// ---------------------------------------------------------------------------
chrome.runtime.onInstalled.addListener(async () => {
  const data = await chrome.storage.local.get(["config", "stats"]);
  if (!data.config) {
    await chrome.storage.local.set({ config: DEFAULT_CONFIG });
  }
  if (!data.stats) {
    await chrome.storage.local.set({
      stats: { totalScans: 0, blockedCount: 0, redactedCount: 0, allowedCount: 0, logs: [] }
    });
  }
  console.log("[Secure-AI-Gateway] Service worker installed & initialized.");
});

// ---------------------------------------------------------------------------
// Message dispatcher
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SCAN_PROMPT") {
    handleScanPrompt(message, sender)
      .then((res) => sendResponse(res))
      .catch((err) => {
        console.error("[Secure-AI-Gateway] Scan error:", err.message);
        sendResponse({
          allowed: false,
          action: "BLOCK",
          error: true,
          reason: `Security Gateway Error: ${err.message}`,
          entities: []
        });
      });
    return true; // Keep channel open for async response
  }

  if (message.type === "GET_STATS") {
    chrome.storage.local.get(["stats", "config"]).then((data) => sendResponse(data));
    return true;
  }

  if (message.type === "UPDATE_CONFIG") {
    chrome.storage.local.set({ config: message.config }).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }
});

// ---------------------------------------------------------------------------
// Core scan handler
// ---------------------------------------------------------------------------
async function handleScanPrompt(message, sender) {
  const storage = await chrome.storage.local.get(["config", "stats"]);
  const config = storage.config || DEFAULT_CONFIG;
  const stats = storage.stats || {
    totalScans: 0, blockedCount: 0, redactedCount: 0, allowedCount: 0, logs: []
  };

  if (!config.enabled) {
    return { allowed: true, action: "ALLOW", bypassed: true, entities: [], sanitized_text: message.text || "" };
  }

  const promptText = message.text || "";
  const source = message.source || (sender.tab ? sender.tab.url : "unknown");
  const backendUrl = config.backendUrl || DEFAULT_CONFIG.backendUrl;

  stats.totalScans += 1;

  // ─── Call /v1/redact ────────────────────────────────────────────────────
  let response;
  try {
    response = await fetch(backendUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: promptText })
    });
  } catch (networkErr) {
    // Backend completely unreachable — fail closed, do NOT allow.
    console.error("[Secure-AI-Gateway] Backend unreachable:", networkErr.message);
    await _appendLog(stats, source, "BLOCK", [], 0, "backend_unreachable");
    await chrome.storage.local.set({ stats });
    return {
      allowed: false,
      action: "BLOCK",
      error: true,
      reason: `Cannot connect to DLP backend (${networkErr.message}). Request blocked.`,
      entities: []
    };
  }

  // ─── HTTP 403 = policy BLOCK (not a backend error) ──────────────────────
  if (response.status === 403) {
    let detail = "Request blocked by DLP policy.";
    let entities = [];
    try {
      const body = await response.json();
      // FastAPI raises HTTPException with {detail: "..."}.
      detail = body.detail || detail;
    } catch (_) { /* ignore parse failures */ }

    stats.blockedCount += 1;
    await _appendLog(stats, source, "BLOCK", entities, 0, "policy_block");
    await chrome.storage.local.set({ stats });

    return {
      allowed: false,
      action: "BLOCK",
      reason: detail,
      entities: entities
    };
  }

  // ─── Any other non-2xx = backend failure, fail closed ───────────────────
  if (!response.ok) {
    const errText = `Backend returned HTTP ${response.status}`;
    console.error("[Secure-AI-Gateway]", errText);
    stats.blockedCount += 1;
    await _appendLog(stats, source, "BLOCK", [], 0, "backend_error");
    await chrome.storage.local.set({ stats });
    return {
      allowed: false,
      action: "BLOCK",
      error: true,
      reason: `DLP backend error (${response.status}). Request blocked for safety.`,
      entities: []
    };
  }

  // ─── 200 OK: parse redact response ──────────────────────────────────────
  const data = await response.json();
  const sanitized_text = data.sanitized_text || promptText;
  const entities = data.entities || [];

  // Derive action: if sanitized text differs from original, entities were REDACTED.
  // If text is identical, all entities were ALLOWED (or there were none).
  const wasRedacted = sanitized_text !== promptText;
  const action = wasRedacted ? "REDACT" : "ALLOW";

  if (action === "REDACT") {
    stats.redactedCount += 1;
  } else {
    stats.allowedCount += 1;
  }

  // ─── Audit log — NO raw PII stored ──────────────────────────────────────
  // Store only: timestamp, source hostname, action, entity types, count.
  // Do NOT store prompt text or sanitized text.
  const entityTypes = entities.map((e) => e.type);
  await _appendLog(stats, source, action, entityTypes, entities.length, "ok");
  await chrome.storage.local.set({ stats });

  return {
    allowed: true,
    action: action,
    sanitized_text: sanitized_text,
    entities: entities,
    reason: action === "REDACT"
      ? `Sensitive data redacted (${entityTypes.join(", ")})`
      : "Safe prompt"
  };
}

// ---------------------------------------------------------------------------
// Audit log helper — never stores raw PII
// ---------------------------------------------------------------------------
async function _appendLog(stats, source, action, entityTypes, entityCount, status) {
  let hostname = source;
  try { hostname = new URL(source).hostname || source; } catch (_) { /* ignore */ }

  const logEntry = {
    id: Date.now(),
    timestamp: new Date().toISOString(),
    source: hostname,
    action: action,
    entityTypes: entityTypes,   // e.g. ["EMAIL", "PHONE"] — not the actual values
    entityCount: entityCount,
    status: status
    // Deliberately omitting: promptText, sanitized_text, entity values
  };

  stats.logs.unshift(logEntry);
  if (stats.logs.length > 50) stats.logs.pop();
}
