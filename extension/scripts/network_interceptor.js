/**
 * network_interceptor.js - Core Network Firewall (MAIN World Script)
 *
 * Runs in the webpage's MAIN execution world before any AI scripts load.
 *
 * Flow:
 *   1. Replaces native `window.fetch` and `window.XMLHttpRequest`.
 *   2. Pauses execution and extracts the prompt text from the request body.
 *   3. Sends to DLP backend via content_bridge.js → background.js → /v1/redact.
 *   4. ALLOW  → nativeFetch/nativeSend with the original body, unchanged.
 *   5. REDACT → replacePromptText() rewrites the body; nativeFetch/nativeSend
 *               with the sanitized body. Original PII never leaves the browser.
 *   6. BLOCK  → request aborted/rejected; blocked modal shown.
 *   7. TIMEOUT or ERROR → fail CLOSED; original body is never sent.
 *
 * Security guarantee: the original PII-bearing body is NEVER forwarded when
 * the policy says REDACT or BLOCK, and never forwarded on gateway errors.
 */

(function () {
  console.log(
    "%c[Secure AI Gateway]%c Network Firewall Active on:",
    "background: #1e293b; color: #38bdf8; font-weight: bold; padding: 2px 4px; border-radius: 4px;",
    "color: #94a3b8;",
    window.location.hostname
  );

  // References to native implementations — captured before any page scripts run.
  const nativeFetch = window.fetch;
  const NativeXHR = window.XMLHttpRequest;

  // Pending verification promises, keyed by request ID.
  const pendingRequests = new Map();

  /** Generates a unique request ID. */
  function generateId() {
    return "req_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9);
  }

  /**
   * Sends prompt text across the execution-world boundary to the extension
   * bridge, waits for the DLP decision, and returns it.
   *
   * FAIL CLOSED: if the backend is unreachable or the timeout fires, the
   * function resolves with action=BLOCK, not ALLOW.
   *
   * @param {string} text - Extracted prompt text
   * @param {string} url  - Target AI URL
   * @returns {Promise<{allowed: boolean, action: string, sanitized_text?: string, entities: Array, reason?: string}>}
   */
  function verifyWithGateway(text, url) {
    return new Promise((resolve) => {
      const id = generateId();

      // 5-second safety timeout — resolves BLOCKED, not allowed.
      const timeoutHandle = setTimeout(() => {
        if (pendingRequests.has(id)) {
          pendingRequests.delete(id);
          console.warn(
            "[Secure AI Gateway] DLP scan timed out. Failing CLOSED — request will be blocked."
          );
          resolve({
            allowed: false,
            action: "BLOCK",
            reason: "DLP gateway timeout. Request blocked for safety.",
            entities: []
          });
        }
      }, 5000);

      pendingRequests.set(id, { resolve, timeoutHandle });

      window.postMessage(
        {
          type: "SECURE_AI_FIREWALL_VERIFY_REQUEST",
          id: id,
          payload: {
            text: text,
            url: String(url),
            source: window.location.href
          }
        },
        "*"
      );
    });
  }

  // Listen for verification responses from content_bridge.js.
  window.addEventListener("message", (event) => {
    if (!event.data || event.data.type !== "SECURE_AI_FIREWALL_VERIFY_RESPONSE") return;

    const { id, result } = event.data;
    if (pendingRequests.has(id)) {
      const { resolve, timeoutHandle } = pendingRequests.get(id);
      clearTimeout(timeoutHandle);
      pendingRequests.delete(id);
      resolve(result);
    }
  });

  // ==========================================================================
  // Shared result handler
  // ==========================================================================
  /**
   * Given a DLP scan result and the original request body, returns the body
   * that should actually be sent.
   *
   * Returns null when the request must be BLOCKED (caller should abort/reject).
   * Returns a body string for ALLOW or REDACT.
   * Throws only in truly unexpected cases (treated as BLOCK by callers).
   *
   * @param {object} scanResult  - Result from verifyWithGateway()
   * @param {string} originalBody - Original serialised request body
   * @param {string} url          - Target URL
   * @param {string} promptText   - Extracted prompt text
   * @returns {{ body: string|null, action: string }}
   */
  function _resolveBody(scanResult, originalBody, url, promptText) {
    // Normalise legacy responses (no action field) for safety.
    if (!scanResult) {
      return { body: null, action: "BLOCK" };
    }

    const action = scanResult.action || (scanResult.allowed ? "ALLOW" : "BLOCK");

    if (action === "BLOCK" || !scanResult.allowed) {
      return { body: null, action: "BLOCK" };
    }

    if (action === "REDACT") {
      const sanitizedText = scanResult.sanitized_text;
      if (!sanitizedText || !window.PayloadParser || !window.PayloadParser.replacePromptText) {
        // Cannot rewrite — fail closed.
        console.error(
          "[Secure AI Gateway] REDACT: replacePromptText unavailable. " +
          "Failing closed — original body will NOT be sent."
        );
        return { body: null, action: "BLOCK" };
      }

      // replacePromptText throws for unrecognised formats — catch and block.
      let rewrittenBody;
      try {
        rewrittenBody = window.PayloadParser.replacePromptText(
          originalBody,
          url,
          promptText,
          sanitizedText
        );
      } catch (rewriteErr) {
        console.error(
          "[Secure AI Gateway] REDACT body rewrite failed:",
          rewriteErr.message,
          "Failing closed."
        );
        if (window.UIModal) {
          window.UIModal.showBlockedModal({
            reason: "PII detected but body format could not be safely rewritten. " +
                    "Request blocked for safety.",
            entities: scanResult.entities || []
          });
        }
        return { body: null, action: "BLOCK" };
      }

      return { body: rewrittenBody, action: "REDACT" };
    }

    // ALLOW — return original body unchanged.
    return { body: originalBody, action: "ALLOW" };
  }

  // ==========================================================================
  // 1. Monkey-Patching `window.fetch`
  // ==========================================================================
  window.fetch = async function (...args) {
    let [resource, config] = args;
    const url = typeof resource === "string" ? resource : (resource && resource.url) || "";
    const method = (config && config.method) ? config.method.toUpperCase() : "GET";

    if (config && config.body && (method === "POST" || method === "PUT" || method === "PATCH")) {
      const isAiEndpoint = window.PayloadParser
        ? window.PayloadParser.isAiPromptEndpoint(url)
        : false;

      if (isAiEndpoint) {
        const promptText = window.PayloadParser
          ? window.PayloadParser.extractPromptText(config.body, url)
          : "";

        if (promptText && promptText.trim().length > 1) {
          if (window.UIModal) window.UIModal.toggleScanningBadge(true);

          let scanResult;
          try {
            scanResult = await verifyWithGateway(promptText, url);
          } catch (err) {
            if (window.UIModal) window.UIModal.toggleScanningBadge(false);
            console.error("[Secure AI Gateway] verifyWithGateway error:", err);
            // Treat verification errors as BLOCK (fail closed).
            return Promise.reject(
              new TypeError("Failed to fetch: DLP gateway error. Request blocked for safety.")
            );
          }

          if (window.UIModal) window.UIModal.toggleScanningBadge(false);

          const originalBody = typeof config.body === "string"
            ? config.body
            : JSON.stringify(config.body);

          const { body: resolvedBody, action } = _resolveBody(
            scanResult, originalBody, url, promptText
          );

          if (action === "BLOCK") {
            console.error("[Secure AI Gateway] Fetch BLOCKED.", scanResult);
            if (window.UIModal) window.UIModal.showBlockedModal(scanResult);
            return Promise.reject(
              new TypeError("Failed to fetch: Request blocked by Secure AI Gateway DLP policy.")
            );
          }

          if (action === "REDACT") {
            console.info(
              "[Secure AI Gateway] Fetch REDACTED. Sending sanitized body.",
              { entityTypes: (scanResult.entities || []).map((e) => e.type) }
            );
            if (window.UIModal) window.UIModal.showRedactNotification();

            // Build a new config with the sanitized body; preserve everything else.
            const sanitizedConfig = Object.assign({}, config, { body: resolvedBody });
            return nativeFetch.call(this, resource, sanitizedConfig);
          }

          // ALLOW — fall through to nativeFetch with original args.
          console.info("[Secure AI Gateway] Fetch ALLOWED.");
        }
      }
    }

    // Pass through to native fetch with original arguments.
    return nativeFetch.apply(this, args);
  };

  // ==========================================================================
  // 2. Monkey-Patching `XMLHttpRequest`
  // ==========================================================================
  const nativeOpen = NativeXHR.prototype.open;
  const nativeSend = NativeXHR.prototype.send;

  NativeXHR.prototype.open = function (method, url, ...rest) {
    this._url = url;
    this._method = method;
    return nativeOpen.apply(this, [method, url, ...rest]);
  };

  NativeXHR.prototype.send = function (body) {
    const method = (this._method || "").toUpperCase();
    const isAiEndpoint = window.PayloadParser
      ? window.PayloadParser.isAiPromptEndpoint(this._url)
      : false;

    if (body && isAiEndpoint && (method === "POST" || method === "PUT" || method === "PATCH")) {
      const promptText = window.PayloadParser
        ? window.PayloadParser.extractPromptText(body, this._url)
        : "";

      if (promptText && promptText.trim().length > 1) {
        const xhrRef = this;
        const originalBody = typeof body === "string" ? body : JSON.stringify(body);
        const capturedUrl = this._url;

        // Async DLP scan — DO NOT call nativeSend before the scan completes.
        verifyWithGateway(promptText, capturedUrl).then((scanResult) => {
          const { body: resolvedBody, action } = _resolveBody(
            scanResult, originalBody, capturedUrl, promptText
          );

          if (action === "BLOCK") {
            console.error("[Secure AI Gateway] XHR BLOCKED.", scanResult);
            if (window.UIModal) window.UIModal.showBlockedModal(scanResult);
            xhrRef.abort(); // Never calls nativeSend.
            return;
          }

          if (action === "REDACT") {
            console.info(
              "[Secure AI Gateway] XHR REDACTED. Sending sanitized body.",
              { entityTypes: (scanResult.entities || []).map((e) => e.type) }
            );
            if (window.UIModal) window.UIModal.showRedactNotification();
            // Send ONLY the sanitized body — original is discarded.
            nativeSend.call(xhrRef, resolvedBody);
            return;
          }

          // ALLOW — send original body.
          console.info("[Secure AI Gateway] XHR ALLOWED.");
          nativeSend.call(xhrRef, originalBody);
        }).catch((err) => {
          // Fail closed on gateway errors.
          console.error("[Secure AI Gateway] XHR gateway error:", err);
          if (window.UIModal) {
            window.UIModal.showBlockedModal({
              reason: "DLP gateway error. Request blocked for safety.",
              entities: []
            });
          }
          xhrRef.abort();
        });

        return; // Handled asynchronously — do NOT fall through to nativeSend.
      }
    }

    // Non-AI endpoint or no prompt — pass through unchanged.
    return nativeSend.apply(this, arguments);
  };
})();
