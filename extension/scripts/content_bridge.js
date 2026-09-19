/**
 * content_bridge.js - Isolated World Message Bridge
 * 
 * Runs in the Chrome Extension's ISOLATED world.
 * 
 * Responsibilities:
 * 1. Listens for window.postMessage from the MAIN world (network_interceptor.js).
 * 2. Uses chrome.runtime.sendMessage to communicate with background.js (Service Worker).
 * 3. Relays the DLP scan decision back to the MAIN world via window.postMessage.
 */

(function () {
  console.log("[Secure AI Gateway] Content Bridge initialized in isolated world.");

  window.addEventListener("message", async (event) => {
    // Only process messages from the same window
    if (event.source !== window) return;

    if (event.data && event.data.type === "SECURE_AI_FIREWALL_VERIFY_REQUEST") {
      const { id, payload } = event.data;

      try {
        // Forward to background service worker
        const result = await chrome.runtime.sendMessage({
          type: "SCAN_PROMPT",
          text: payload.text,
          source: payload.source || window.location.href,
          url: payload.url
        });

        // Send decision back to MAIN world
        window.postMessage(
          {
            type: "SECURE_AI_FIREWALL_VERIFY_RESPONSE",
            id: id,
            result: result || { allowed: true }
          },
          "*"
        );
      } catch (err) {
        console.error("[Secure AI Gateway Bridge] Error forwarding scan to background worker:", err);
        // Fail-safe response
        window.postMessage(
          {
            type: "SECURE_AI_FIREWALL_VERIFY_RESPONSE",
            id: id,
            result: { allowed: false, reason: "Gateway Bridge Error: " + err.message, entities: [] }
          },
          "*"
        );
      }
    }
  });
})();
