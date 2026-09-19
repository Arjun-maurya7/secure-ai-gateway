/**
 * parser.js - Universal AI Endpoint Classifier & Prompt Extractor
 * 
 * Provides strict, noise-free classification of AI prompt requests across:
 * - ChatGPT (OpenAI)
 * - Google Gemini (Google DeepMind)
 * - Claude (Anthropic)
 * - DeepSeek
 * - Perplexity AI
 * - Microsoft Copilot
 * - OpenAI Standard Gateways (/v1/chat/completions)
 */

const PayloadParser = (function () {
  /**
   * Exact URL patterns for AI Prompt Completion endpoints.
   */
  const TARGET_AI_PROMPT_ENDPOINTS = [
    // 1. ChatGPT
    /\/backend-api\/(f\/)?conversation$/i,
    /\/backend-api\/(f\/)?conversation\/init$/i,

    // 2. Google Gemini
    /assistant\.lamda\.BardFrontendService\/StreamGenerate/i,
    /\/StreamGenerate/i,

    // 3. Anthropic Claude
    /\/api\/organizations\/[^\/]+\/chat_conversations\/[^\/]+\/completion/i,
    /\/api\/organizations\/[^\/]+\/chat_conversations\/[^\/]+\/retry_completion/i,

    // 4. DeepSeek
    /\/api\/v0\/chat\/completion/i,

    // 5. Perplexity AI
    /\/rest\/threads$/i,
    /\/rest\/queries$/i,

    // 6. Microsoft Copilot
    /\/c\/api\/chat/i,
    /\/turing\/conversation\/create/i,

    // 7. OpenAI-Compatible & Ollama Standards
    /\/v1\/chat\/completions/i,
    /\/v1\/completions/i,
    /\/api\/generate$/i,
    /\/api\/chat$/i
  ];

  /**
   * Endpoints explicitly ignored (telemetry, background syncs, internal RPCs).
   */
  const EXPLICIT_IGNORED_ENDPOINTS = [
    /batchexecute/i,                       // Google Gemini internal batch RPCs
    /\/ces\//i,                            // ChatGPT analytics
    /\/statsc\//i,                         // ChatGPT Statsig telemetry
    /\/obi\/sync/i,                        // OpenAI consent sync
    /\/sentinel\//i,                       // OpenAI bot/auth check
    /\/settings\//i,                       // User settings
    /\/accounts\//i,                       // Account info
    /\/telemetry/i,                        // Generic telemetry
    /\/analytics/i,                        // Generic analytics
    /\/datadog/i,                          // Datadog monitoring
    /\/sentry/i,                           // Sentry error tracking
    /\/track/i,                            // Tracking pixels
    /\/log/i,                              // Logging
    /\/metrics/i,                          // Metrics
    /\/user_segments/i,                    // Segmentation
    /\/subscriptions/i,                    // Subscriptions check
    /\/bootstrap/i,                        // Bootstraps
    /\/client_204/i,                       // Google pingbacks
    /\/play\//i                            // Google Play services
  ];

  /**
   * Determines if a request URL is a legitimate AI prompt completion endpoint.
   * @param {string} url - Target request URL
   * @returns {boolean}
   */
  function isAiPromptEndpoint(url) {
    if (!url) return false;
    const urlStr = String(url);

    // 1. If it matches any ignored telemetry pattern -> SKIP IMMEDIATELY
    if (EXPLICIT_IGNORED_ENDPOINTS.some((pattern) => pattern.test(urlStr))) {
      return false;
    }

    // 2. Must match an authentic AI prompt completion pattern
    return TARGET_AI_PROMPT_ENDPOINTS.some((pattern) => pattern.test(urlStr));
  }

  /**
   * Extracts clean, human-typed prompt text from request body.
   * @param {any} body - Outgoing HTTP payload
   * @param {string} url - Target request URL
   * @returns {string} - Extracted prompt text
   */
  function extractPromptText(body, url = "") {
    if (!body) return "";

    // 1. Handle Google Gemini URL-encoded Form body
    if (typeof body === "string" && body.includes("f.req=")) {
      return extractFromGeminiPayload(body);
    }

    // 2. Handle JSON Bodies
    let parsedJson = null;
    if (typeof body === "string") {
      try {
        parsedJson = JSON.parse(body);
      } catch {
        return body;
      }
    } else if (typeof body === "object") {
      parsedJson = body;
    }

    if (!parsedJson) return String(body);

    // 3. ChatGPT Format: {"messages": [{"author": {"role": "user"}, "content": {"parts": ["..."]}}]}
    if (Array.isArray(parsedJson.messages)) {
      const userMsgs = parsedJson.messages.filter(
        (m) => (m.author && m.author.role === "user") || m.role === "user"
      );
      if (userMsgs.length > 0) {
        const parts = [];
        for (const msg of userMsgs) {
          if (msg.content && Array.isArray(msg.content.parts)) {
            parts.push(...msg.content.parts.filter((p) => typeof p === "string"));
          } else if (typeof msg.content === "string") {
            parts.push(msg.content);
          } else if (typeof msg.text === "string") {
            parts.push(msg.text);
          }
        }
        if (parts.length > 0) return parts.join("\n").trim();
      }
    }

    // 4. Claude Format: {"prompt": "..."} or {"messages": [...]}
    if (typeof parsedJson.prompt === "string" && parsedJson.prompt.trim()) {
      return parsedJson.prompt.trim();
    }

    // 5. Perplexity / Standard Format: {"query": "..."} or {"input": "..."}
    if (typeof parsedJson.query === "string" && parsedJson.query.trim()) {
      return parsedJson.query.trim();
    }
    if (typeof parsedJson.input === "string" && parsedJson.input.trim()) {
      return parsedJson.input.trim();
    }

    // 6. Generic Object Fallback
    return extractTextFromNestedObject(parsedJson);
  }

  /**
   * Extracts user prompt from Gemini StreamGenerate payload.
   */
  function extractFromGeminiPayload(bodyStr) {
    try {
      const params = new URLSearchParams(bodyStr);
      const reqVal = params.get("f.req");
      if (reqVal) {
        const parsed = JSON.parse(reqVal);
        // Gemini RPC payload: [[["User prompt here", 0, null, null, null, null, 0], ...]]
        return extractTextFromNestedObject(parsed);
      }
    } catch (e) {
      console.warn("[Secure AI Gateway] Error parsing Gemini RPC payload:", e);
    }
    return "";
  }

  /**
   * Recursively walks nested arrays and objects to extract clean strings.
   */
  function extractTextFromNestedObject(obj) {
    if (!obj) return "";
    const extractedStrings = [];

    function traverse(node) {
      if (typeof node === "string") {
        const trimmed = node.trim();
        // Ignore internal identifiers, timestamps, hex IDs, empty values
        if (
          trimmed.length > 1 &&
          !/^[0-9a-f-]{24,}$/i.test(trimmed) &&
          !/^\d{4}-\d{2}-\d{2}T/.test(trimmed) &&
          !/^(generic|null|true|false|undefined)$/i.test(trimmed)
        ) {
          extractedStrings.push(trimmed);
        }
        return;
      }

      if (Array.isArray(node)) {
        for (const item of node) traverse(item);
        return;
      }

      if (typeof node === "object" && node !== null) {
        for (const [key, value] of Object.entries(node)) {
          // Skip internal telemetry and configuration keys
          if (/^(telemetry|token|timestamp|version|device|session|user_id|session_id|statsig|event_id)$/i.test(key)) {
            continue;
          }
          traverse(value);
        }
      }
    }

    traverse(obj);
    return extractedStrings.join("\n").trim();
  }

  // ==========================================================================
  // replacePromptText — format-aware request body rewriter
  // ==========================================================================
  /**
   * Replaces the user prompt text inside an outgoing request body with
   * `sanitizedText`, using format-aware field targeting so that unrelated
   * fields (system prompt, metadata, IDs, etc.) are never modified.
   *
   * Supported formats (mirrors extractPromptText):
   *   1. Standard OpenAI messages  — messages[].content (string)
   *   2. ChatGPT parts messages    — messages[].content.parts[]
   *   3. Claude prompt field       — body.prompt
   *   4. Perplexity/generic query  — body.query / body.input
   *   5. Gemini f.req URL-encoded  — f.req JSON rewritten
   *
   * For any unrecognised format this function THROWS.
   * The caller must treat a throw as "fail closed" and must NOT send the
   * original body.
   *
   * @param {string} bodyStr       - Original request body (string)
   * @param {string} url           - Target request URL (used for format hints)
   * @param {string} originalText  - The prompt text as extracted by extractPromptText
   * @param {string} sanitizedText - The redacted replacement text
   * @returns {string} - Rewritten body string
   * @throws {Error} - If the format is unrecognised or replacement cannot be
   *                   confirmed; caller must block the request.
   */
  function replacePromptText(bodyStr, url, originalText, sanitizedText) {
    if (!bodyStr) throw new Error("replacePromptText: empty body");
    if (originalText === sanitizedText) return bodyStr; // Nothing to replace

    // ------------------------------------------------------------------
    // Gemini URL-encoded f.req format
    // ------------------------------------------------------------------
    if (typeof bodyStr === "string" && bodyStr.includes("f.req=")) {
      return _replaceInGeminiPayload(bodyStr, originalText, sanitizedText);
    }

    // ------------------------------------------------------------------
    // JSON formats
    // ------------------------------------------------------------------
    let parsed;
    try {
      parsed = JSON.parse(bodyStr);
    } catch (_) {
      // Non-JSON, non-Gemini body — we cannot safely transform it.
      throw new Error(
        "replacePromptText: unrecognised body format (non-JSON, non-Gemini). " +
        "Failing closed — original body must not be sent."
      );
    }

    // 1. messages[] array (OpenAI standard + ChatGPT parts + Claude messages)
    if (Array.isArray(parsed.messages)) {
      const rewritten = _replaceInMessages(parsed, originalText, sanitizedText);
      return JSON.stringify(rewritten);
    }

    // 2. Claude { prompt: "..." }
    if (typeof parsed.prompt === "string") {
      if (!parsed.prompt.includes(originalText)) {
        throw new Error(
          "replacePromptText: originalText not found in body.prompt. " +
          "Failing closed."
        );
      }
      parsed.prompt = parsed.prompt.replace(originalText, sanitizedText);
      return JSON.stringify(parsed);
    }

    // 3. Perplexity { query: "..." }
    if (typeof parsed.query === "string") {
      if (!parsed.query.includes(originalText)) {
        throw new Error(
          "replacePromptText: originalText not found in body.query. " +
          "Failing closed."
        );
      }
      parsed.query = parsed.query.replace(originalText, sanitizedText);
      return JSON.stringify(parsed);
    }

    // 4. Generic { input: "..." }
    if (typeof parsed.input === "string") {
      if (!parsed.input.includes(originalText)) {
        throw new Error(
          "replacePromptText: originalText not found in body.input. " +
          "Failing closed."
        );
      }
      parsed.input = parsed.input.replace(originalText, sanitizedText);
      return JSON.stringify(parsed);
    }

    // Unrecognised JSON structure — fail closed.
    throw new Error(
      "replacePromptText: unrecognised JSON body structure. " +
      "Failing closed — original body must not be sent."
    );
  }

  /**
   * Rewrites user message content in a messages[] array.
   * Only touches entries whose role is "user" (or author.role === "user").
   * Handles both string content and ChatGPT parts[] arrays.
   * Throws if originalText is not found in any user message.
   */
  function _replaceInMessages(parsed, originalText, sanitizedText) {
    // Deep-clone to avoid mutating the caller's object
    const result = JSON.parse(JSON.stringify(parsed));
    let replaced = false;

    for (const msg of result.messages) {
      const isUser =
        msg.role === "user" ||
        (msg.author && msg.author.role === "user");
      if (!isUser) continue;

      // Standard string content
      if (typeof msg.content === "string" && msg.content.includes(originalText)) {
        msg.content = msg.content.replace(originalText, sanitizedText);
        replaced = true;
        continue;
      }

      // ChatGPT parts[] content
      if (
        msg.content &&
        Array.isArray(msg.content.parts)
      ) {
        for (let i = 0; i < msg.content.parts.length; i++) {
          if (
            typeof msg.content.parts[i] === "string" &&
            msg.content.parts[i].includes(originalText)
          ) {
            msg.content.parts[i] = msg.content.parts[i].replace(
              originalText,
              sanitizedText
            );
            replaced = true;
          }
        }
      }

      // msg.text (some Copilot variants)
      if (typeof msg.text === "string" && msg.text.includes(originalText)) {
        msg.text = msg.text.replace(originalText, sanitizedText);
        replaced = true;
      }
    }

    if (!replaced) {
      throw new Error(
        "replacePromptText: originalText not found in any user message. " +
        "Failing closed — original body must not be sent."
      );
    }

    return result;
  }

  /**
   * Rewrites a Gemini f.req URL-encoded payload.
   * Reconstructs the f.req JSON with the prompt replaced.
   * Throws if the payload cannot be safely transformed.
   */
  function _replaceInGeminiPayload(bodyStr, originalText, sanitizedText) {
    try {
      const params = new URLSearchParams(bodyStr);
      const reqVal = params.get("f.req");
      if (!reqVal) {
        throw new Error("Missing f.req parameter");
      }

      // Replace the originalText inside the raw JSON string (string literal).
      // We use a targeted string-level replacement because the Gemini RPC
      // payload is deeply nested and reversing it completely is fragile.
      // We only replace inside string values, not in keys/identifiers.
      if (!reqVal.includes(originalText)) {
        throw new Error("originalText not found in Gemini f.req payload");
      }

      // Escape the replacement for safe JSON embedding
      const escapedSanitized = sanitizedText
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t");

      const escapedOriginal = originalText
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t");

      // Validate the replacement can be found at the JSON string level
      if (!reqVal.includes(escapedOriginal)) {
        throw new Error(
          "replacePromptText: Gemini — originalText not found at JSON-string level. " +
          "Failing closed."
        );
      }

      const rewrittenReq = reqVal.replace(escapedOriginal, escapedSanitized);
      params.set("f.req", rewrittenReq);
      return params.toString();
    } catch (e) {
      throw new Error(
        "replacePromptText: Gemini payload rewrite failed — " + e.message +
        ". Failing closed."
      );
    }
  }

  return {
    isAiPromptEndpoint,
    extractPromptText,
    replacePromptText
  };
})();

if (typeof window !== "undefined") {
  window.PayloadParser = PayloadParser;
}

// CommonJS export for Node.js test environment
if (typeof module !== "undefined" && module.exports) {
  module.exports = PayloadParser;
}

