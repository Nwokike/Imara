# 🛡️ Project Imara: AI System Knowledge Base (2026 Standard)

This document is the foundational source of truth for Project Imara. It contains the complete architectural, operational, and mission-critical knowledge required for any AI or developer to maintain and evolve the platform without guesswork.

---

## 🌍 1. Mission & Narrative
*   **Primary Objective**: To fight Online Gender-Based Violence (OGBV) in Africa by providing an invisible, immediate, and forensic-grade Digital Bodyguard.
*   **Narrative Focus**: Protecting Africans facing OGBV. The system is inclusive but specialized in the regional context of digital violence.
*   **Brand Persona**: "Aunty Imara" — a technically competent Forensic Support Specialist. She is warm and empathetic but primarily reassuring through her specialized competence and use of the "Agent Hive."

---

## 🏗️ 2. Core Architecture: The Bodyguard Hive
Imara operates on a **"One Agent, One Tool"** micro-agent architecture (Google ADK 2026 compliant). Logic is split between two distinct pipelines.

### **The 7-Agent Roster**
| Agent | Responsibility | Primary Model (Groq/Gemini) |
| :--- | :--- | :--- |
| **Sentinel** | Safety Policy | `gpt-oss-safeguard-20b` |
| **Linguist** | Dialect/Tone | `qwen/qwen3-32b` |
| **Visionary** | OCR/Vision | `llama-4-maverick-17b` |
| **Navigator** | Jurisdiction | `llama-3.3-70b-versatile` |
| **Forensic** | Reasoning/Hash | `gpt-oss-120b` |
| **Messenger** | Dispatch | `kimi-k2-instruct` |
| **Counselor** | Persona/Safe-Plan | `kimi-k2-instruct-0905` |

### **The Dual-Pipeline Standard**
1.  **Stateful Chat (`chat_orchestration`)**:
    *   Used by Telegram, Meta, and Discord.
    *   **Temporal Context Pruning**: If the last interaction was >24 hours ago, the `Counselor` resets its persona state, but the `Forensic` agent retains full history for audit integrity.
    *   **Live Updates**: Uses an `on_step` callback to live-update "Thinking" messages on the platform.
2.  **Stateless Web (`web_orchestration`)**:
    *   Used by the anonymous Web Form.
    *   High-speed batch processing. No history lookup. Optimized for immediate forensic dispatch.

---

## 🛠️ 3. Technology Stack & Constraints
*   **Resource Limit**: **1GB RAM VM**. All components are strictly optimized.
*   **Backend**: Django 6.0.2 (Native Async support).
*   **Python**: 3.12+ (Managed via `uv`).
*   **Serving**: **Uvicorn (ASGI)** via Unix Socket (`imara.sock`).
*   **Task Worker**: Django Native Tasks (`django-tasks-db`). Replaces Huey/Celery.
*   **Database**: SQLite (WAL Mode enabled).
*   **AI Routing**: **LiteLLM Router** with 5-layer fallback and **Semantic Disk Caching** (located at `/tmp/litellm_cache`).
*   **Forensics**: Every report is SHA-256 hashed. Media is streamed (never loaded fully into RAM).

---

## 🚀 4. Deployment & Infrastructure (GCP)

### **Server Details**
*   **Host IP**: `35.209.14.56`
*   **User**: `projectimarahq`
*   **Password**: `NdiIgbo1234@`
*   **Project Path**: `/home/projectimarahq/imara`
*   **Domain**: `imara.africa`

### **Systemd Services**
*   `imara.service`: Uvicorn ASGI web server.
*   `imara-worker.service`: Native background task consumer (`python manage.py db_worker`).
*   `nginx.service`: Reverse proxy handling SSL (Certbot) and static files.

### **R2 Cloudflare Storage**
*   `imara-media`: Active evidence and report assets.
*   `imara-backups`: Daily SQLite database snapshots.

---

## 🔧 5. Operational Commands (The Runbook)

### **Local Development**
```bash
uv sync
uv run python manage.py migrate
uv run uvicorn imara.asgi:application --reload
uv run python manage.py db_worker
```

### **Server Management**
```bash
# Update everything
git pull origin main && uv sync && uv run python manage.py migrate && sudo systemctl restart imara imara-worker

# Check logs
journalctl -u imara -f
journalctl -u imara-worker -f
```

---

## 📜 6. Key Files & Logic Locations
*   `triage/agents/`: Individual agent logic and system prompts.
*   `triage/decision_engine.py`: The orchestrator and pipeline logic.
*   `intake/webhook_service.py`: Real-time Telegram/Meta message handling.
*   `dispatch/tasks.py`: Email delivery and database backups.
*   `utils/ratelimit.py`: Custom zero-RAM cache-based rate limiter.
*   `litellm_config.yaml`: Model fallback chains and group definitions.

---

## 🔒 7. Security Mandates
1.  **No Huey**: Huey is deleted. Never re-introduce it.
2.  **No Dotenv**: Use `uv` native environment loading or the custom loader in `manage.py`.
3.  **Fail-Closed**: Turnstile and Safety Sentinel must fail-closed in production.
4.  **English-First**: Agents must not use non-English greetings unless the user speaks that language first.

**Final Handover Note**: This system is balanced for 1GB RAM. Adding heavy libraries or synchronous I/O will crash the VM. Always prioritize async `httpx` and `db_worker` tasks.
