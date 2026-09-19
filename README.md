# Secure AI Gateway

Enterprise-grade DLP (Data Loss Prevention) system that intercepts AI prompts before they reach external LLMs, detects PII, and enforces policy in real time.

## Architecture

```
AI Website  →  Chrome Extension  →  POST /v1/redact  →  FastAPI Backend
                    │                                         │
                    │                              Detection + Policy + Redaction
                    │                                         │
                    │                         ┌───────────────┼───────────────┐
                    │                       ALLOW           REDACT          BLOCK
                    │                         │               │               │
                    └────────────── Original  │  Sanitized   │    Abort     ─┘
                                     request  │  request     │
                                              ▼
                                         External LLM
```

## Repo Structure

```
secure-ai-gateway/
├── backend/          # FastAPI DLP backend
│   ├── main.py
│   ├── detection/    # DetectionEngine + 10 detectors
│   ├── policy/       # PolicyEngine (ALLOW / REDACT / BLOCK)
│   ├── redaction/    # RedactionEngine ([TYPE] substitution)
│   ├── schemas/      # Pydantic models
│   ├── evaluation/   # Benchmark + evaluator
│   ├── tests/        # 125 pytest tests
│   ├── requirements.txt
│   └── pytest.ini
│
├── extension/        # Chrome Extension (MV3)
│   ├── manifest.json
│   ├── background.js         # Service worker → calls /v1/redact
│   ├── content.js            # Send-button interceptor
│   ├── scripts/
│   │   ├── network_interceptor.js  # fetch + XHR monkey-patch
│   │   ├── parser.js               # Prompt extractor + body rewriter
│   │   ├── content_bridge.js       # ISOLATED world bridge
│   │   └── ui_modal.js             # Block/redact UI toasts
│   ├── popup/                # Extension popup UI
│   └── tests/
│       └── test_parser.js    # 51 JS security property tests
│
├── frontend/         # Dashboard UI (placeholder)
└── README.md
```

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Run Tests

```bash
# Python (from backend/)
cd backend
pytest

# JavaScript (from repo root)
node extension/tests/test_parser.js
```

### Chrome Extension

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/scan` | POST | Detection only — returns entities |
| `/v1/redact` | POST | Detection + Policy + Redaction; returns 403 on BLOCK |

## Policy

| Entity | Action |
|---|---|
| EMAIL, PHONE, PAN, CARD, NAME, ACCOUNT, IP | REDACT |
| URL | ALLOW |
| API_KEY, JWT | BLOCK |
