/**
 * ui_modal.js - In-Page DLP Notification and Alert Component
 * 
 * Displays rich, non-intrusive alert modals and toast badges when a prompt
 * violation is detected or when an outgoing AI request is blocked.
 */

const UIModal = (function () {
  /**
   * Sanitizes string to avoid XSS when rendering HTML.
   */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Displays the blocked request modal with detected sensitive entities.
   * @param {Object} result - Scan result from DLP backend
   * @param {Array} result.entities - Array of detected sensitive entities
   * @param {string} result.reason - Reason message
   */
  function showBlockedModal(result) {
    // Remove existing modal if any
    const existing = document.getElementById("secure-ai-firewall-modal");
    if (existing) existing.remove();

    const entities = result.entities || [];
    const entitiesHtml = entities.length > 0
      ? `<div style="margin: 14px 0; max-height: 160px; overflow-y: auto; background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 8px; padding: 10px;">
          <div style="font-size: 11px; font-weight: 700; color: #f87171; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">
            ⚠️ Blocked Sensitive Items (${entities.length}):
          </div>
          ${entities.map(e => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(239, 68, 68, 0.12); border-left: 3px solid #ef4444; border-radius: 4px; padding: 6px 10px; margin-bottom: 6px; font-size: 12px;">
              <span style="font-weight: 700; color: #fca5a5;">${escapeHtml(e.type)}</span>
              <span style="font-family: 'Consolas', 'Courier New', monospace; color: #ffffff; background: rgba(0,0,0,0.6); padding: 2px 6px; border-radius: 4px;">${escapeHtml(e.value)}</span>
            </div>
          `).join("")}
        </div>`
      : `<div style="font-size: 13px; color: #fca5a5; margin: 12px 0;">${escapeHtml(result.reason || "Data loss prevention policy triggered.")}</div>`;

    const container = document.createElement("div");
    container.id = "secure-ai-firewall-modal";
    container.innerHTML = `
      <div style="
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.75);
        backdrop-filter: blur(8px);
        z-index: 2147483647;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #f1f5f9;
        animation: secureAiModalIn 0.2s ease-out;
      ">
        <div style="
          width: 90%;
          max-width: 500px;
          background: #0f172a;
          border: 1px solid rgba(239, 68, 68, 0.45);
          box-shadow: 0 25px 50px rgba(0,0,0,0.85), 0 0 30px rgba(239, 68, 68, 0.2);
          border-radius: 16px;
          padding: 24px;
        ">
          <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 12px;">
            <div style="
              width: 44px; height: 44px; border-radius: 12px;
              background: linear-gradient(135deg, #dc2626, #7f1d1d);
              display: flex; align-items: center; justify-content: center;
              font-size: 22px; flex-shrink: 0; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.4);
            ">🛡️</div>
            <div>
              <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #ffffff;">Network Request Blocked</h2>
              <div style="font-size: 12px; color: #94a3b8;">AI Security Gateway • Active Network Firewall</div>
            </div>
          </div>

          <p style="font-size: 13px; line-height: 1.5; color: #cbd5e1; margin: 8px 0 12px 0;">
            The outgoing HTTP request to this AI model was intercepted and <strong>aborted</strong> before transmission because sensitive enterprise data was detected.
          </p>

          ${entitiesHtml}

          <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px;">
            <button id="secure-ai-close-btn" style="
              background: #334155;
              color: #f8fafc;
              border: none;
              padding: 9px 20px;
              font-size: 13px;
              font-weight: 600;
              border-radius: 8px;
              cursor: pointer;
              transition: background 0.15s;
            ">Dismiss</button>
          </div>
        </div>
      </div>
      <style>
        @keyframes secureAiModalIn {
          from { opacity: 0; transform: scale(0.96); }
          to { opacity: 1; transform: scale(1); }
        }
        #secure-ai-close-btn:hover { background: #475569 !important; }
      </style>
    `;

    document.body.appendChild(container);
    document.getElementById("secure-ai-close-btn").addEventListener("click", () => {
      container.remove();
    });
  }

  /**
   * Shows a small spinning indicator during scan
   */
  function toggleScanningBadge(show) {
    let badge = document.getElementById("secure-ai-firewall-scan-badge");
    if (!show) {
      if (badge) badge.remove();
      return;
    }
    if (badge) return;

    badge = document.createElement("div");
    badge.id = "secure-ai-firewall-scan-badge";
    badge.innerHTML = `
      <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #0f172a;
        border: 1px solid #3b82f6;
        color: #93c5fd;
        padding: 8px 16px;
        border-radius: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6);
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: sans-serif;
        font-size: 12px;
        font-weight: 600;
        z-index: 2147483647;
      ">
        <span style="display: inline-block; width: 12px; height: 12px; border: 2px solid #3b82f6; border-top-color: transparent; border-radius: 50%; animation: secureAiFirewallSpin 0.7s linear infinite;"></span>
        <span>AI Gateway: Inspecting Network Payload...</span>
      </div>
      <style>
        @keyframes secureAiFirewallSpin { to { transform: rotate(360deg); } }
      </style>
    `;
    document.body.appendChild(badge);
  }

  /**
   * Shows a brief non-intrusive toast notification when PII is redacted
   * before sending. Does NOT display any PII values or entity content.
   * Auto-dismisses after 4 seconds.
   */
  function showRedactNotification() {
    // Remove any existing redact toast
    const existing = document.getElementById("secure-ai-firewall-redact-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "secure-ai-firewall-redact-toast";
    toast.innerHTML = `
      <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #0f172a;
        border: 1px solid rgba(251, 191, 36, 0.5);
        color: #fcd34d;
        padding: 10px 18px;
        border-radius: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6), 0 0 12px rgba(251,191,36,0.15);
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 13px;
        font-weight: 600;
        z-index: 2147483647;
        animation: secureAiRedactIn 0.2s ease-out;
      ">
        <span style="font-size: 16px;">🔒</span>
        <span>Sensitive data detected and redacted before sending.</span>
      </div>
      <style>
        @keyframes secureAiRedactIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      </style>
    `;
    document.body.appendChild(toast);

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      if (toast.parentNode) toast.remove();
    }, 4000);
  }

  return {
    showBlockedModal,
    toggleScanningBadge,
    showRedactNotification
  };
})();

if (typeof window !== "undefined") {
  window.UIModal = UIModal;
}

