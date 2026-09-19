# Secure AI Gateway - Network-Level Prompt Firewall

An enterprise-grade Chrome Extension (Manifest V3) that acts as a **Client-Side AI Firewall / Data Loss Prevention (DLP) Gateway**. It intercepts outgoing HTTP requests (`fetch` and `XMLHttpRequest`) across AI platforms (ChatGPT, Gemini, Claude, DeepSeek, Perplexity, Copilot, etc.) and halts them before they leave the browser until verified by your security backend.

---

## 🏛️ Architecture Overview

The extension uses a modular, two-world architecture to achieve 100% network interception in Chrome Manifest V3 without relying on fragile HTML selectors.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             WEBPAGE (MAIN World)                         │
│                                                                          │
│  User types prompt & triggers action                                     │
│            │                                                             │
│            ▼                                                             │
│  Site invokes window.fetch(...) or XHR                                   │
│            │                                                             │
│            ▼                                                             │
│  [ scripts/network_interceptor.js ]  <-- Monkey-patches fetch & XHR      │
│            │                                                             │
│            ├── [ scripts/parser.js ] (Extracts text from JSON / FormData)│
│            │                                                             │
│            ▼                                                             │
│    window.postMessage('SECURE_AI_FIREWALL_VERIFY_REQUEST')               │
└────────────────────┬─────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     EXTENSION CONTENT SCRIPT (ISOLATED World)            │
│                                                                          │
│  [ scripts/content_bridge.js ]                                           │
│            │                                                             │
│            ▼  chrome.runtime.sendMessage('SCAN_PROMPT')                 │
└────────────────────┬─────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND SERVICE WORKER                            │
│                                                                          │
│  [ background.js ]                                                       │
│            │                                                             │
│            ▼  HTTP POST (JSON)                                           │
│  FastAPI DLP Backend (`http://localhost:8000/v1/scan`)                   │
│            │                                                             │
│            ▼                                                             │
│  Detection Engine: Scans for PAN, Emails, Phones, API Keys, etc.         │
│            │                                                             │
│            ▼                                                             │
│  Decision: ALLOW (true) / BLOCK (false) + Detected Entities              │
└────────────────────┬─────────────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      ENFORCEMENT ACTION (MAIN World)                     │
│                                                                          │
│   ├── If ALLOWED: Native fetch executes normally -> AI receives prompt   │
│   └── If BLOCKED: Request is aborted + [ scripts/ui_modal.js ] displays  │
│                   in-page DLP alert modal with detected violations       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory & Module Structure

```
extension/
├── manifest.json                  # Manifest V3 (Registers MAIN and ISOLATED world scripts)
├── background.js                  # Central Service Worker: communicates with FastAPI backend
├── scripts/
│   ├── network_interceptor.js     # MAIN World: Intercepts window.fetch & XMLHttpRequest
│   ├── content_bridge.js          # ISOLATED World: Relays messages between page and extension
│   ├── parser.js                  # Universal payload parser extracting prompts from any JSON/body
│   └── ui_modal.js                # In-page UI modal for rendering blocked DLP notifications
├── popup/
│   ├── popup.html                 # Extension popup interface
│   ├── popup.css                  # Dark mode styling & status indicators
│   └── popup.js                   # Extension state toggle, live stats & audit logs
└── README.md                      # Documentation
```

---

## 🚀 How to Install and Test

### 1. Ensure Backend is Running
Your FastAPI backend should be running on `http://127.0.0.1:8000`:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 2. Load Extension in Chrome
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Toggle on **Developer mode** (top right).
3. Click **Load unpacked**.
4. Select the `extension/` directory.

### 3. Verify Interception
1. Navigate to **[ChatGPT](https://chatgpt.com)**, **[Gemini](https://gemini.google.com)**, or **[Claude](https://claude.ai)**.
2. Open Chrome DevTools (`F12` -> Console). You should see:
   `[Secure AI Gateway] Network Firewall Active on: chatgpt.com`
3. Send a prompt with sensitive test data:
   > *"My email is dev@company.com and my PAN card is ABCDE1234F"*
4. The network request will be intercepted and aborted immediately, and the **Network Request Blocked** security modal will appear showing the detected `EMAIL` and `PAN` entities.
