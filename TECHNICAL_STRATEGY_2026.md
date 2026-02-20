# Technical Strategy 2026: The "One Agent, One Tool" Network

**Project:** Imara (Digital Bodyguard)
**Target:** 1GB RAM VM (Production)
**Stack:** Django 5.2, Google ADK 2026, LiteLLM, Huey (Async)

---

## 1. Multi-Agent Architecture ("The Hive")

To avoid "monolithic agent confusion," we employ a **One Agent, One Tool** pattern. Each agent is a specialized micro-process powered by a specific LLM suited to its task.

### The Agent Roster

| Agent Name | Role | Primary Tool | Primary Model (Groq) | Fallback 1 | Final Fallback (Gemini) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator** | Logic & Routing | `AgentDispatcher` | `kimi-k2-instruct-0905` | `llama-3.3-70b` | `Gemini 3 Flash` |
| **Sentinel** | Safety Policy | `TextFilter` | `gpt-oss-safeguard-20b` | `llama-3.1-8b` | `Gemini 2.5 Flash Lite` |
| **Visionary** | OCR & Image | `ImageAnalyzer` | `llama-4-maverick-17b` | `Gemini 2.5 Flash` | `Gemini 3 Pro` |
| **Linguist** | Translation | `DialectTranslator`| `qwen/qwen3-32b` | `kimi-k2-instruct-0905`| `Gemma 3 27B` |
| **Forensic** | Hashing & Audit| `EvidenceHasher` | `openai/gpt-oss-120b` | `llama-4-scout-17b` | `Deep Research Pro` |
| **Counselor** | Empathy Chat | `SafetyAdvisor` | `qwen/qwen3-32b` | `kimi-k2-instruct` | `Gemini 2.5 Flash` |
| **Dispatcher** | Email/Partner | `BrevoEmail` | `kimi-k2-instruct` | `llama-3.3-70b` | `Gemini 2.5 Flash` |

---

## 2. LiteLLM Router Configuration

We use LiteLLM's `Router` to manage the complex fallback chains. This provides:
*   **Automatic Retries:** 3x retries with exponential backoff.
*   **Rate Limit Handling:** Automatically switches to the next model if `429 Too Many Requests` occurs.
*   **Context Window Fallback:** If a prompt is too long for `llama-3.1-8b` (8k), it auto-switches to `kimi-k2` (256k).

**Groups:**
*   `fast`: Low latency, lower reasoning (Llama 3.1, Gemini Flash Lite).
*   `smart`: High reasoning, slower (GPT-OSS-120b, Llama 4 Scout).
*   `vision`: Multimodal capability (Llama 4 Maverick, Gemini 3 Flash).
*   `safety`: Specialized safety filtering (Safeguard 20b).

---

## 3. Google ADK 2026 Integration

We utilize the latest ADK features to modernize the agent interactions:

*   **Context Bundles:** Instead of passing raw strings, we pass a `ContextBundle` object. This bundle persists in SQLite and is "hydrated" only when an agent needs it, saving RAM.
*   **Generative Tool UI:** On the Partner Dashboard, we will render the agent's progress. "Agent is analyzing image..." -> "Agent is detecting location..." -> "Agent is dispatching email."
*   **Agent2Agent (A2A):** Future-proofing for partners who want to connect their own bots to Imara.

---

## 4. 1GB RAM Optimization Strategy

*   **Huey Task Queue:** Every agent action is a discrete Huey task.
    *   *User sends message* -> `process_telegram_update` (Task 1)
    *   *Task 1 calls Sentinel* -> `agent_sentinel_check` (Task 2)
    *   *Task 2 calls Orchestrator* -> `agent_orchestrate` (Task 3)
*   **Benefit:** The web server never holds the memory for the AI processing. The worker process picks up one small task, executes it, and releases the memory immediately.
*   **Streaming:** All file uploads (Images/Audio) are streamed to R2 storage. The AI agents operate on the **File Object/URL**, never reading the full bytes into RAM.

---

## 5. Partner Features

*   **AI Response Assistant:** A new button on the Case Detail page allowing partners to "Generate Response" for a victim, drafted by `gpt-oss-20b`.
*   **Live Audit Log:** Every AI action is logged in `PartnerAuditLog` for legal transparency.

---

**Status:** Plan Approved. Implementation Active.
