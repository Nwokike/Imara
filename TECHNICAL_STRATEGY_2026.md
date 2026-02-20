# Technical Strategy 2026: The "Bodyguard Hive" Network

**Project:** Imara (Digital Bodyguard)
**Target:** 1GB RAM VM (GCP Production)
**Stack:** Django 6.0, Google ADK 2026, LiteLLM Router, ASGI

---

## 1. Multi-Agent Architecture ("The Hive")

We utilize a **One Agent, One Tool** pattern to achieve 100% reasoning specialization.

| Agent Name | Role | Core Responsibility | Model Target |
| :--- | :--- | :--- | :--- |
| **Sentinel** | Policy | Content safety check | `gpt-oss-safeguard-20b` |
| **Linguist** | Dialect | Pidgin/Swahili translation | `qwen/qwen3-32b` |
| **Visionary** | OCR | Multi-modal image audit | `llama-4-maverick` |
| **Navigator** | Juris | Location matching (54 nations) | `llama-3.3-70b` |
| **Forensic** | Audit | Evidence hashing & legal logic | `gpt-oss-120b` |
| **Messenger** | Dispatch | Automated partner drafting | `kimi-k2-instruct` |
| **Counselor** | Persona | Victim-facing empathetic chat | `kimi-k2-0905` |

---

## 2. LiteLLM Router Implementation

We manage model reliability through a 5-layer fallback chain defined in `litellm_config.yaml`.
*   **Routing Strategy**: Simple-shuffle for load balancing across free/paid tiers.
*   **Semantic Caching**: reasoning results are cached to disk to minimize latency and token spend.
*   **Group Mapping**:
    *   `vision-specialist` -> Targets multi-modal Groq/Gemini models.
    *   `chat-counselor` -> High context (256k) targets for deep history.

---

## 3. Dual-Pipeline Orchestration

Logic is bifurcated to handle different entry points efficiently:

### A. Stateful Chat (`chat_orchestration`)
- **Sources**: Telegram, Meta, Discord.
- **Context**: Hydrates up to 10 history messages into the `ContextBundle`.
- **Flow**: Emphasizes counselor empathy and continuous safety planning.

### B. Stateless Web (`web_orchestration`)
- **Sources**: Anonymous Web Forms.
- **Context**: Zero history. High-speed single-turn reasoning.
- **Flow**: Optimized for forensic speed and immediate partner dispatch.

---

## 4. 1GB RAM Optimization (Production)

*   **Uvicorn (ASGI)**: Switched from Gunicorn/WSGI to enable async `httpx` calls without blocking workers.
*   **Native `db_worker`**: Uses `django-tasks-db` to manage the queue directly in SQLite. Zero Redis/RabbitMQ overhead.
*   **Streaming I/O**: File-based evidence is never loaded entirely into RAM; agents operate on paths and streamed chunks.
*   **Dependency Purge**: Removed `django-huey`, `requests`, `django-editorjs2`, and `python-dotenv`.

---

## 5. Security & Forensic Integrity

*   **Evidence Hashing**: Forensic Agent generates an immutable SHA-256 digest of all artifacts.
*   **Production Hardening**: Enforced `CSRF_TRUSTED_ORIGINS`, `DEBUG=False`, and custom rate limiting.
*   **Worker Safety**: Backup tasks use atomic SQLite snapshots to prevent DB corruption.

---
**Implementation Finalized:** 20 February 2026.
**Enforced by:** Gemini CLI Bodyguard Module.
