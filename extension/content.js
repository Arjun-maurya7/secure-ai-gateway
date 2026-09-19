// content.js - In-page interceptor for AI models (ChatGPT, Gemini, Claude, DeepSeek, Perplexity)

(function () {
  console.log("[Secure-AI-Gateway] Content script loaded on:", window.location.hostname);

  let isBypassing = false;
  let isScanning = false;

  // AI Platform Adapters
  const Adapters = {
    chatgpt: {
      match: () => /chatgpt\.com|chat\.openai\.com/.test(window.location.hostname),
      getInput: () => document.querySelector('#prompt-textarea, [contenteditable="true"], textarea[tabindex="0"]'),
      getText: (input) => input.value || input.innerText || input.textContent || "",
      getSendButton: () => document.querySelector('button[data-testid="send-button"], button[aria-label="Send prompt"], button[data-testid="fruitjuice-send-button"]')
    },
    gemini: {
      match: () => /gemini\.google\.com/.test(window.location.hostname),
      getInput: () => document.querySelector('.ql-editor[contenteditable="true"], rich-textarea [contenteditable="true"], textarea'),
      getText: (input) => input.innerText || input.textContent || input.value || "",
      getSendButton: () => document.querySelector('button[aria-label*="Send"], button.send-button, .send-button-container button')
    },
    claude: {
      match: () => /claude\.ai/.test(window.location.hostname),
      getInput: () => document.querySelector('div[contenteditable="true"].ProseMirror, textarea'),
      getText: (input) => input.innerText || input.textContent || input.value || "",
      getSendButton: () => document.querySelector('button[aria-label="Send Message"], button[aria-label="Send message"], button:has(svg path[d*="M208"])')
    },
    deepseek: {
      match: () => /chat\.deepseek\.com/.test(window.location.hostname),
      getInput: () => document.querySelector('textarea, [contenteditable="true"]'),
      getText: (input) => input.value || input.innerText || input.textContent || "",
      getSendButton: () => document.querySelector('div[role="button"][aria-disabled="false"], button[type="submit"]')
    },
    perplexity: {
      match: () => /perplexity\.ai/.test(window.location.hostname),
      getInput: () => document.querySelector('textarea, [contenteditable="true"]'),
      getText: (input) => input.value || input.innerText || input.textContent || "",
      getSendButton: () => document.querySelector('button[aria-label="Submit"], button[type="submit"]')
    },
    generic: {
      match: () => true,
      getInput: () => document.querySelector('textarea, [contenteditable="true"], [role="textbox"]'),
      getText: (input) => input ? (input.value || input.innerText || input.textContent || "") : "",
      getSendButton: () => document.querySelector('button[type="submit"], button[aria-label*="Send" i], button[aria-label*="Submit" i]')
    }
  };

  function getCurrentAdapter() {
    for (const [name, adapter] of Object.entries(Adapters)) {
      if (name !== 'generic' && adapter.match()) {
        return adapter;
      }
    }
    return Adapters.generic;
  }

  function getActivePromptText() {
    const adapter = getCurrentAdapter();
    const input = adapter.getInput();
    if (!input) return "";
    return adapter.getText(input).trim();
  }

  // Intercept Keydown (Enter key)
  document.addEventListener(
    "keydown",
    async (event) => {
      if (isBypassing || isScanning) return;

      if (event.key === "Enter" && !event.shiftKey) {
        const target = event.target;
        const isTextInput = target.matches('textarea, [contenteditable="true"], [role="textbox"]') ||
                            target.closest('#prompt-textarea, .ql-editor, .ProseMirror');

        if (isTextInput) {
          const text = getActivePromptText();
          if (!text) return;

          // Stop submit
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();

          await processSubmission(text, () => {
            isBypassing = true;
            // Dispatch native enter or click send button
            const adapter = getCurrentAdapter();
            const btn = adapter.getSendButton();
            if (btn && !btn.disabled) {
              btn.click();
            } else {
              target.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }));
            }
            setTimeout(() => { isBypassing = false; }, 300);
          });
        }
      }
    },
    true // Capture phase
  );

  // Intercept Click on Send Buttons
  document.addEventListener(
    "click",
    async (event) => {
      if (isBypassing || isScanning) return;

      const adapter = getCurrentAdapter();
      const sendBtn = adapter.getSendButton();
      const targetBtn = event.target.closest('button, [role="button"]');

      const isSendClick = (sendBtn && (event.target === sendBtn || sendBtn.contains(event.target))) ||
                          (targetBtn && isLikelySendButton(targetBtn));

      if (isSendClick) {
        const text = getActivePromptText();
        if (!text) return;

        // Stop submit
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        await processSubmission(text, () => {
          isBypassing = true;
          if (targetBtn) {
            targetBtn.click();
          } else if (sendBtn) {
            sendBtn.click();
          }
          setTimeout(() => { isBypassing = false; }, 300);
        });
      }
    },
    true // Capture phase
  );

  function isLikelySendButton(el) {
    const label = (el.getAttribute("aria-label") || "") + (el.getAttribute("data-testid") || "") + (el.innerText || "");
    return /send|submit|generate/i.test(label);
  }

  async function processSubmission(promptText, allowCallback) {
    isScanning = true;
    showScanningIndicator(true);

    try {
      const response = await chrome.runtime.sendMessage({
        type: "SCAN_PROMPT",
        text: promptText,
        source: window.location.href
      });

      showScanningIndicator(false);
      isScanning = false;

      const action = response.action || (response.allowed ? "ALLOW" : "BLOCK");

      if (action === "BLOCK") {
        console.warn("[Secure-AI-Gateway] Prompt blocked:", response.reason, response.entities);
        showBlockedModal(response);
        return; // Do not call allowCallback — request must not be sent.
      }

      if (action === "REDACT") {
        console.info(
          "[Secure-AI-Gateway] Prompt contains PII — will be redacted at network layer.",
          { entityTypes: (response.entities || []).map((e) => e.type) }
        );
        // The actual body rewriting happens inside network_interceptor.js.
        // We simply allow the submit to proceed; the network layer will replace
        // the PII-bearing payload with the sanitized text before it leaves the browser.
        showRedactToast();
        allowCallback();
        return;
      }

      // ALLOW
      console.log("[Secure-AI-Gateway] Prompt approved by DLP scanner.");
      allowCallback();
    } catch (err) {
      showScanningIndicator(false);
      isScanning = false;
      console.error("[Secure-AI-Gateway] Error scanning:", err);
      // Gateway communication error — block by default (fail closed).
      showBlockedModal({
        reason: "Gateway communication error. Cannot verify prompt safety. Request blocked.",
        entities: []
      });
    }
  }

  function showRedactToast() {
    const existing = document.getElementById("secure-ai-redact-content-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "secure-ai-redact-content-toast";
    toast.innerHTML = `
      <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #1e1e2f;
        border: 1px solid rgba(251, 191, 36, 0.5);
        color: #fcd34d;
        padding: 9px 16px;
        border-radius: 24px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: sans-serif;
        font-size: 13px;
        font-weight: 600;
        z-index: 999999;
      ">
        🔒 Sensitive data detected and redacted before sending.
      </div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 4000);
  }


  // In-Page DLP Notification Modal
  function showBlockedModal(result) {
    let existingModal = document.getElementById("secure-ai-modal-root");
    if (existingModal) existingModal.remove();

    const entitiesHtml = (result.entities && result.entities.length > 0)
      ? `<div style="margin: 12px 0; max-height: 140px; overflow-y: auto; background: rgba(255,255,255,0.06); border-radius: 8px; padding: 10px;">
          <div style="font-size: 11px; font-weight: 600; color: #f87171; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px;">Detected Sensitive Entities:</div>
          ${result.entities.map(e => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 6px 10px; margin-bottom: 6px; font-size: 12px;">
              <span style="font-weight: 700; color: #fca5a5;">${escapeHtml(e.type)}</span>
              <span style="font-family: monospace; color: #ffffff; background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px;">${escapeHtml(e.value)}</span>
            </div>
          `).join('')}
        </div>`
      : `<div style="font-size: 13px; color: #fca5a5; margin: 10px 0;">${escapeHtml(result.reason || "Sensitive information policy violation.")}</div>`;

    const modal = document.createElement("div");
    modal.id = "secure-ai-modal-root";
    modal.innerHTML = `
      <div style="
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(6px);
        z-index: 9999999;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        color: #f1f5f9;
        animation: secureAiFadeIn 0.2s ease-out;
      ">
        <div style="
          width: 90%;
          max-width: 480px;
          background: #111827;
          border: 1px solid rgba(239, 68, 68, 0.4);
          box-shadow: 0 20px 40px rgba(0,0,0,0.8), 0 0 20px rgba(239, 68, 68, 0.2);
          border-radius: 16px;
          padding: 24px;
          position: relative;
        ">
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
            <div style="
              width: 42px; height: 42px; border-radius: 10px;
              background: linear-gradient(135deg, #dc2626, #991b1b);
              display: flex; align-items: center; justify-content: center;
              font-size: 22px; flex-shrink: 0;
            ">🛡️</div>
            <div>
              <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #ffffff;">Prompt Submission Blocked</h2>
              <div style="font-size: 12px; color: #9ca3af;">Secure AI Gateway • Data Loss Prevention</div>
            </div>
          </div>

          <p style="font-size: 13px; line-height: 1.5; color: #d1d5db; margin: 8px 0 12px 0;">
            This request contains sensitive or confidential data restricted by your organization's security policy. Please sanitize the prompt before sending.
          </p>

          ${entitiesHtml}

          <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px;">
            <button id="secure-ai-modal-close" style="
              background: #374151;
              color: #f3f4f6;
              border: none;
              padding: 9px 18px;
              font-size: 13px;
              font-weight: 600;
              border-radius: 8px;
              cursor: pointer;
              transition: background 0.15s;
            ">Edit Prompt</button>
          </div>
        </div>
      </div>
      <style>
        @keyframes secureAiFadeIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }
        #secure-ai-modal-close:hover { background: #4b5563 !important; }
      </style>
    `;

    document.body.appendChild(modal);

    document.getElementById("secure-ai-modal-close").addEventListener("click", () => {
      modal.remove();
    });
  }

  function showScanningIndicator(show) {
    let indicator = document.getElementById("secure-ai-scan-badge");
    if (!show) {
      if (indicator) indicator.remove();
      return;
    }
    if (indicator) return;

    indicator = document.createElement("div");
    indicator.id = "secure-ai-scan-badge";
    indicator.innerHTML = `
      <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #1e1e2f;
        border: 1px solid #3b82f6;
        color: #60a5fa;
        padding: 8px 16px;
        border-radius: 24px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: sans-serif;
        font-size: 13px;
        font-weight: 600;
        z-index: 999999;
      ">
        <span style="display: inline-block; width: 12px; height: 12px; border: 2px solid #60a5fa; border-top-color: transparent; border-radius: 50%; animation: secureAiSpin 0.8s linear infinite;"></span>
        <span>Scanning prompt with AI Gateway...</span>
      </div>
      <style>
        @keyframes secureAiSpin {
          to { transform: rotate(360deg); }
        }
      </style>
    `;
    document.body.appendChild(indicator);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
})();
