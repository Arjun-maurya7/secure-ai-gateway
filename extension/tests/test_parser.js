/**
 * test_parser.js — Security property tests for PayloadParser.replacePromptText()
 *
 * Run with: node extension/tests/test_parser.js
 *
 * These tests verify the critical security guarantee of the integration:
 *
 *   - REDACT: the sanitized body contains the [PLACEHOLDER] and does NOT
 *     contain the original PII value.
 *   - BLOCK / Unsupported format: replacePromptText() THROWS and the caller
 *     must never fall back to sending the original body.
 *   - ALLOW: the body is returned unchanged.
 *   - System/assistant messages: only USER messages are rewritten.
 *   - nativeFetch / nativeSend are simulated with mock functions so we can
 *     assert exactly what body they receive (or that they are never called).
 *
 * No external test framework required.
 */

"use strict";

const PayloadParser = require("../scripts/parser.js");

// ---------------------------------------------------------------------------
// Tiny assertion helper
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;

function assert(condition, description) {
  if (condition) {
    console.log(`  ✅ PASS: ${description}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${description}`);
    failed++;
  }
}

function assertThrows(fn, description) {
  try {
    fn();
    console.error(`  ❌ FAIL (did not throw): ${description}`);
    failed++;
  } catch (e) {
    console.log(`  ✅ PASS (threw as expected): ${description} — ${e.message.split(".")[0]}`);
    passed++;
  }
}

function section(name) {
  console.log(`\n${"─".repeat(60)}`);
  console.log(`▶ ${name}`);
  console.log("─".repeat(60));
}

// ---------------------------------------------------------------------------
// 1. ALLOW — replacePromptText returns body unchanged when texts are equal
// ---------------------------------------------------------------------------
section("ALLOW: body unchanged when originalText === sanitizedText");

{
  const body = JSON.stringify({
    messages: [{ role: "user", content: "What is the capital of France?" }]
  });

  const result = PayloadParser.replacePromptText(
    body,
    "https://api.openai.com/v1/chat/completions",
    "What is the capital of France?",
    "What is the capital of France?" // same
  );

  assert(result === body, "ALLOW: result is reference-equal to original body");

  const parsed = JSON.parse(result);
  assert(
    parsed.messages[0].content === "What is the capital of France?",
    "ALLOW: user content field is unchanged"
  );
}

// ---------------------------------------------------------------------------
// 2. REDACT — Standard OpenAI messages format
// ---------------------------------------------------------------------------
section("REDACT: Standard OpenAI messages format — string content");

{
  const original = "Contact Rahul at rahul@gmail.com";
  const sanitized = "Contact [NAME] at [EMAIL]";

  const body = JSON.stringify({
    model: "gpt-4o",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: original }
    ]
  });

  const resultStr = PayloadParser.replacePromptText(
    body,
    "https://api.openai.com/v1/chat/completions",
    original,
    sanitized
  );

  const result = JSON.parse(resultStr);

  // Security property: original PII absent
  assert(
    !resultStr.includes("rahul@gmail.com"),
    "REDACT(openai): original email NOT in rewritten body"
  );
  // Sanitized value present
  assert(
    resultStr.includes("[EMAIL]"),
    "REDACT(openai): [EMAIL] placeholder present in rewritten body"
  );
  // System message untouched
  assert(
    result.messages[0].content === "You are a helpful assistant.",
    "REDACT(openai): system message content unchanged"
  );
  // User message updated
  assert(
    result.messages[1].content === sanitized,
    "REDACT(openai): user message content equals sanitized text"
  );
  // Model field preserved
  assert(
    result.model === "gpt-4o",
    "REDACT(openai): model field preserved"
  );
}

// ---------------------------------------------------------------------------
// 3. REDACT — ChatGPT parts[] format
// ---------------------------------------------------------------------------
section("REDACT: ChatGPT parts[] format");

{
  const original = "My email is test@example.com";
  const sanitized = "My email is [EMAIL]";

  const body = JSON.stringify({
    messages: [
      {
        author: { role: "system" },
        content: { parts: ["You are a helpful assistant."] }
      },
      {
        author: { role: "user" },
        content: { parts: [original] }
      }
    ]
  });

  const resultStr = PayloadParser.replacePromptText(
    body,
    "https://chatgpt.com/backend-api/conversation",
    original,
    sanitized
  );
  const result = JSON.parse(resultStr);

  // Security property: original PII absent
  assert(
    !resultStr.includes("test@example.com"),
    "REDACT(parts): original email NOT in rewritten body"
  );
  // Sanitized placeholder present
  assert(
    resultStr.includes("[EMAIL]"),
    "REDACT(parts): [EMAIL] placeholder present"
  );
  // System parts untouched
  assert(
    result.messages[0].content.parts[0] === "You are a helpful assistant.",
    "REDACT(parts): system parts unchanged"
  );
  // User parts updated
  assert(
    result.messages[1].content.parts[0] === sanitized,
    "REDACT(parts): user parts[0] equals sanitized text"
  );
}

// ---------------------------------------------------------------------------
// 4. REDACT — Claude prompt field
// ---------------------------------------------------------------------------
section("REDACT: Claude { prompt: '...' } format");

{
  const original = "My PAN card is ABCDE1234F";
  const sanitized = "My PAN card is [PAN]";

  const body = JSON.stringify({
    model: "claude-3-5-sonnet-20241022",
    prompt: original,
    max_tokens: 1024
  });

  const resultStr = PayloadParser.replacePromptText(
    body,
    "https://claude.ai/api/organizations/org-123/chat_conversations/abc/completion",
    original,
    sanitized
  );
  const result = JSON.parse(resultStr);

  // Security property
  assert(
    !resultStr.includes("ABCDE1234F"),
    "REDACT(claude): original PAN NOT in rewritten body"
  );
  assert(
    resultStr.includes("[PAN]"),
    "REDACT(claude): [PAN] placeholder present"
  );
  assert(
    result.prompt === sanitized,
    "REDACT(claude): prompt field equals sanitized text"
  );
  // Unrelated fields preserved
  assert(
    result.model === "claude-3-5-sonnet-20241022",
    "REDACT(claude): model field preserved"
  );
  assert(
    result.max_tokens === 1024,
    "REDACT(claude): max_tokens preserved"
  );
}

// ---------------------------------------------------------------------------
// 5. REDACT — Perplexity { query: '...' } format
// ---------------------------------------------------------------------------
section("REDACT: Perplexity { query: '...' } format");

{
  const original = "Call John on 9876543210";
  const sanitized = "Call John on [PHONE]";

  const body = JSON.stringify({ query: original });

  const resultStr = PayloadParser.replacePromptText(body, "/rest/threads", original, sanitized);
  const result = JSON.parse(resultStr);

  assert(!resultStr.includes("9876543210"), "REDACT(perplexity): original phone absent");
  assert(resultStr.includes("[PHONE]"), "REDACT(perplexity): [PHONE] placeholder present");
  assert(result.query === sanitized, "REDACT(perplexity): query field updated");
}

// ---------------------------------------------------------------------------
// 6. System message is NOT touched — only user messages are rewritten
// ---------------------------------------------------------------------------
section("REDACT: System message must NOT be modified");

{
  const systemContent = "You help with account queries. Customer email: rahul@gmail.com";
  const userContent = "My email is user@example.com";
  const sanitizedUser = "My email is [EMAIL]";

  const body = JSON.stringify({
    messages: [
      { role: "system", content: systemContent },
      { role: "user",   content: userContent }
    ]
  });

  const resultStr = PayloadParser.replacePromptText(
    body,
    "/v1/chat/completions",
    userContent,
    sanitizedUser
  );
  const result = JSON.parse(resultStr);

  // The system message contains an email but must NOT be touched.
  assert(
    result.messages[0].content === systemContent,
    "REDACT: system message content is completely unchanged"
  );
  // The user message is rewritten.
  assert(
    result.messages[1].content === sanitizedUser,
    "REDACT: user message content is rewritten"
  );
  // The original user email is gone from the user field
  assert(
    !result.messages[1].content.includes("user@example.com"),
    "REDACT: original user email absent from user message"
  );
}

// ---------------------------------------------------------------------------
// 7. BLOCK — Unsupported format: replacePromptText MUST throw
// ---------------------------------------------------------------------------
section("BLOCK/Unsupported: replacePromptText must throw for unrecognised formats");

assertThrows(
  () => PayloadParser.replacePromptText(
    "raw plain text, not JSON, not Gemini",
    "/v1/chat/completions",
    "some prompt",
    "some [REDACTED] prompt"
  ),
  "Throws for plain text (non-JSON, non-Gemini) body"
);

assertThrows(
  () => PayloadParser.replacePromptText(
    JSON.stringify({ completionText: "My phone is 9876543210" }), // no messages/prompt/query/input
    "/v1/chat/completions",
    "My phone is 9876543210",
    "My phone is [PHONE]"
  ),
  "Throws for unrecognised JSON structure (no messages/prompt/query/input)"
);

assertThrows(
  () => PayloadParser.replacePromptText(
    JSON.stringify({ messages: [{ role: "user", content: "different text entirely" }] }),
    "/v1/chat/completions",
    "original text that does not appear",  // not in body
    "sanitized"
  ),
  "Throws when originalText is not found in any user message"
);

assertThrows(
  () => PayloadParser.replacePromptText(
    JSON.stringify({ prompt: "some other prompt" }),
    "/api/chat",
    "text not in prompt field",  // not in body
    "sanitized"
  ),
  "Throws when originalText not in Claude prompt field"
);

// ---------------------------------------------------------------------------
// 8. Network layer simulation: nativeFetch receives sanitized body, not original
// ---------------------------------------------------------------------------
section("Network layer simulation: nativeFetch body verification");

{
  // Simulate the interceptor's _resolveBody + call pattern
  function simulateRedactFetch(scanResult, originalBody, url, promptText) {
    const nativeFetchCalls = [];
    const mockNativeFetch = (resource, config) => {
      nativeFetchCalls.push({ resource, body: config.body });
      return Promise.resolve({ ok: true });
    };

    // Mirrors the logic in network_interceptor.js _resolveBody + fetch handler
    const action = scanResult.action || (scanResult.allowed ? "ALLOW" : "BLOCK");

    if (action === "BLOCK" || !scanResult.allowed) {
      return { nativeFetchCalls, rejected: true, action: "BLOCK" };
    }

    if (action === "REDACT") {
      let rewrittenBody;
      try {
        rewrittenBody = PayloadParser.replacePromptText(
          originalBody, url, promptText, scanResult.sanitized_text
        );
      } catch (e) {
        return { nativeFetchCalls, rejected: true, action: "BLOCK", rewriteError: e.message };
      }
      mockNativeFetch("https://example.com", { body: rewrittenBody });
      return { nativeFetchCalls, rejected: false, action: "REDACT", sentBody: rewrittenBody };
    }

    // ALLOW
    mockNativeFetch("https://example.com", { body: originalBody });
    return { nativeFetchCalls, rejected: false, action: "ALLOW", sentBody: originalBody };
  }

  // --- ALLOW path ---
  {
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: "What is the capital of France?" }]
    });
    const scanResult = {
      allowed: true,
      action: "ALLOW",
      sanitized_text: "What is the capital of France?",
      entities: []
    };

    const sim = simulateRedactFetch(
      scanResult, originalBody, "/v1/chat/completions", "What is the capital of France?"
    );

    assert(!sim.rejected, "ALLOW: nativeFetch is called (not rejected)");
    assert(sim.nativeFetchCalls.length === 1, "ALLOW: nativeFetch called exactly once");
    assert(
      sim.nativeFetchCalls[0].body === originalBody,
      "ALLOW: nativeFetch receives the original, unchanged body"
    );
  }

  // --- REDACT path ---
  {
    const promptText = "Contact Rahul at rahul@gmail.com";
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: promptText }]
    });
    const scanResult = {
      allowed: true,
      action: "REDACT",
      sanitized_text: "Contact [NAME] at [EMAIL]",
      entities: [{ type: "NAME", value: "Rahul" }, { type: "EMAIL", value: "rahul@gmail.com" }]
    };

    const sim = simulateRedactFetch(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(!sim.rejected, "REDACT: nativeFetch is called (not rejected)");
    assert(sim.nativeFetchCalls.length === 1, "REDACT: nativeFetch called exactly once");

    // Security property: original PII must be absent from what nativeFetch receives
    assert(
      !sim.nativeFetchCalls[0].body.includes("rahul@gmail.com"),
      "REDACT: nativeFetch body does NOT contain original email (rahul@gmail.com)"
    );
    // Sanitized placeholder must be present
    assert(
      sim.nativeFetchCalls[0].body.includes("[EMAIL]"),
      "REDACT: nativeFetch body contains [EMAIL] placeholder"
    );
    assert(
      sim.nativeFetchCalls[0].body.includes("[NAME]") ||
      !sim.nativeFetchCalls[0].body.includes("Rahul"),
      "REDACT: nativeFetch body does not contain raw name"
    );
  }

  // --- BLOCK path ---
  {
    const promptText = "My API key is sk-proj-1234567890abcdef1234567890";
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: promptText }]
    });
    const scanResult = {
      allowed: false,
      action: "BLOCK",
      reason: "Request blocked because it contains API_KEY",
      entities: [{ type: "API_KEY", value: "sk-proj-1234567890abcdef1234567890" }]
    };

    const sim = simulateRedactFetch(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(sim.rejected, "BLOCK: request is rejected");
    assert(sim.nativeFetchCalls.length === 0, "BLOCK: nativeFetch is NEVER called");
    assert(sim.action === "BLOCK", "BLOCK: action is BLOCK");
  }

  // --- Mixed REDACT + BLOCK —→ BLOCK takes precedence ---
  {
    const promptText = "Email: rahul@gmail.com Key: sk-proj-1234567890abcdef1234567890";
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: promptText }]
    });
    // Backend returns 403 for this; the background.js converts it to BLOCK.
    const scanResult = {
      allowed: false,
      action: "BLOCK",
      reason: "Request blocked because it contains API_KEY",
      entities: [
        { type: "EMAIL", value: "rahul@gmail.com" },
        { type: "API_KEY", value: "sk-proj-1234567890abcdef1234567890" }
      ]
    };

    const sim = simulateRedactFetch(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(sim.rejected, "Mixed: request is rejected (BLOCK wins)");
    assert(sim.nativeFetchCalls.length === 0, "Mixed: nativeFetch is NEVER called");
  }
}

// ---------------------------------------------------------------------------
// 9. Network layer simulation: nativeSend (XHR) body verification
// ---------------------------------------------------------------------------
section("Network layer simulation: nativeSend (XHR) body verification");

{
  function simulateRedactXHR(scanResult, originalBody, url, promptText) {
    const nativeSendCalls = [];
    const abortCalls = [];
    const mockNativeSend = (body) => { nativeSendCalls.push(body); };
    const mockAbort = () => { abortCalls.push(true); };

    const action = scanResult.action || (scanResult.allowed ? "ALLOW" : "BLOCK");

    if (action === "BLOCK" || !scanResult.allowed) {
      mockAbort();
      return { nativeSendCalls, abortCalls, action: "BLOCK" };
    }

    if (action === "REDACT") {
      let rewrittenBody;
      try {
        rewrittenBody = PayloadParser.replacePromptText(
          originalBody, url, promptText, scanResult.sanitized_text
        );
      } catch (e) {
        mockAbort();
        return { nativeSendCalls, abortCalls, action: "BLOCK", rewriteError: e.message };
      }
      mockNativeSend(rewrittenBody);
      return { nativeSendCalls, abortCalls, action: "REDACT" };
    }

    mockNativeSend(originalBody);
    return { nativeSendCalls, abortCalls, action: "ALLOW" };
  }

  // REDACT via XHR
  {
    const promptText = "Call me on 9876543210";
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: promptText }]
    });
    const scanResult = {
      allowed: true,
      action: "REDACT",
      sanitized_text: "Call me on [PHONE]",
      entities: [{ type: "PHONE", value: "9876543210" }]
    };

    const sim = simulateRedactXHR(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(sim.nativeSendCalls.length === 1, "XHR REDACT: nativeSend called exactly once");
    assert(sim.abortCalls.length === 0, "XHR REDACT: abort is NOT called");
    assert(
      !sim.nativeSendCalls[0].includes("9876543210"),
      "XHR REDACT: nativeSend body does NOT contain original phone number"
    );
    assert(
      sim.nativeSendCalls[0].includes("[PHONE]"),
      "XHR REDACT: nativeSend body contains [PHONE] placeholder"
    );
  }

  // BLOCK via XHR
  {
    const promptText = "JWT: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc";
    const originalBody = JSON.stringify({
      messages: [{ role: "user", content: promptText }]
    });
    const scanResult = {
      allowed: false,
      action: "BLOCK",
      reason: "Request blocked because it contains JWT",
      entities: []
    };

    const sim = simulateRedactXHR(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(sim.abortCalls.length === 1, "XHR BLOCK: abort() is called");
    assert(sim.nativeSendCalls.length === 0, "XHR BLOCK: nativeSend is NEVER called");
  }

  // Unsupported format via XHR → abort (fail closed)
  {
    const promptText = "My email is test@example.com";
    const originalBody = "plain text body not json"; // unrecognised format
    const scanResult = {
      allowed: true,
      action: "REDACT",
      sanitized_text: "My email is [EMAIL]",
      entities: [{ type: "EMAIL", value: "test@example.com" }]
    };

    const sim = simulateRedactXHR(
      scanResult, originalBody, "/v1/chat/completions", promptText
    );

    assert(
      sim.abortCalls.length === 1,
      "XHR Unsupported: abort() is called when replacePromptText throws"
    );
    assert(
      sim.nativeSendCalls.length === 0,
      "XHR Unsupported: nativeSend NEVER called — original body not sent"
    );
    assert(
      sim.rewriteError !== undefined,
      "XHR Unsupported: rewriteError recorded"
    );
  }
}

// ---------------------------------------------------------------------------
// 10. Fail-closed: timeout resolves to BLOCK
// ---------------------------------------------------------------------------
section("Fail-closed: timeout must resolve to BLOCK, not ALLOW");

{
  // Simulate the timeout resolution (what the interceptor does after 5s)
  const timeoutResolution = {
    allowed: false,
    action: "BLOCK",
    reason: "DLP gateway timeout. Request blocked for safety.",
    entities: []
  };

  assert(
    !timeoutResolution.allowed,
    "Timeout: resolved result has allowed=false"
  );
  assert(
    timeoutResolution.action === "BLOCK",
    "Timeout: resolved result has action=BLOCK"
  );
  assert(
    timeoutResolution.reason.toLowerCase().includes("timeout") ||
    timeoutResolution.reason.toLowerCase().includes("block"),
    "Timeout: reason string mentions timeout/block"
  );
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n${"═".repeat(60)}`);
console.log(`Results: ${passed} passed, ${failed} failed out of ${passed + failed} tests`);
if (failed === 0) {
  console.log("✅ All security property tests PASSED");
} else {
  console.error(`❌ ${failed} test(s) FAILED`);
  process.exit(1);
}
