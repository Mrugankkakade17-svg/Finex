# S5-MI03 Verification Evidence: LLM Provider Adapter & Deterministic Fallback

**Task ID:** `S5-MI03` (Issue #75)  
**Task Title:** LLM provider adapter (Ollama, free hosted fallback) with deterministic fallback  
**Assignee:** Mitali (`@mitali2701`)  
**Secondary Reviewer:** Payal (`@payalmude14-star`)  
**Sprint:** Sprint 5: Privacy Resilience & Spending Analytics (Milestone #6)  
**Pre-requisite:** `S0-MI02` (Issue #12 / PR #116, merged commit `ee4c4c8` on `dev`)
**Blocks:** `S5-MI04`
**Base Branch:** `dev`
**Feature Branch:** `feature/s5-mi03-llm-provider`
**Pull Request:** [#139](https://github.com/Mrugankkakade17-svg/Finex/pull/139)
**Head Commit:** `c366fa2` (Audited and verified)
**Acceptance Criterion:** `app/adapters/llm/* (N) Provider outage still returns a safe answer`
**Date:** 22 November 2026  

---

## 1. Executive Summary & Objective

The objective of `S5-MI03` is to deliver an authoritative, decoupled LLM adapter layer for FinEx, implementing a resilient three-tier cascade:
1. **Primary Provider (Ollama Local Adapter):** Lightweight local inference (`llama3.2:1b` or configurable GGUF model via Ollama REST API) with finite connection (3s) and read (10s) timeouts, ensuring offline operation without external network dependency.
2. **Secondary Provider (Free Hosted Fallback):** Free-tier hosted provider adapter supporting Google Gemini REST API (`gemini-1.5-flash`) as the authoritative verified free hosted provider, with optional Groq support (`llama-3.1-8b-instant`), reading API keys strictly from environment variables (`GEMINI_API_KEY`, `GROQ_API_KEY`), respecting free-tier rate limits, and cleanly handling HTTP 429 / 401 / 503 errors.
3. **Tertiary Provider (Deterministic Fallback Adapter):** Purely offline, template-based deterministic fallback executing with **zero network calls**, zero external API calls, and zero model hallucinations. Enforces non-negotiable financial compliance rules (refusing direct buy/sell tips or return guarantees), guarantees 100% reproducible output, and injects transparent outage disclaimers.
4. **Resilient Orchestrator (`CompositeLLMProvider`):** Implements the frozen `LLMProvider` protocol (`app/ports/llm_provider.py`). Seamlessly cascades: `Request -> Ollama -> Hosted -> Deterministic`. A complete external provider outage **never raises an unhandled exception or crashes the application**; it always returns a validated, safe answer (`Provider outage still returns a safe answer`).

---

## 2. Authoritative Requirements Traceability Matrix

| Requirement ID | Requirement Description | Source Document / Ref | Implemented Artifact(s) | Verification Status |
| :--- | :--- | :--- | :--- | :---: |
| **REQ-PORT-01** | Preserve existing `LLMProvider` protocol and dataclasses without breaking changes | Final Implementation Plan p. 18; Issue #75 | `backend/app/ports/llm_provider.py` (V) | **PASS** (Protocol preserved) |
| **REQ-OLLAMA-01** | Primary Ollama adapter wrapping local model with finite timeouts | Final Implementation Plan p. 18 | `app/adapters/llm/ollama_adapter.py` | **PASS** (7 tests in `test_llm_adapters.py`) |
| **REQ-OLLAMA-02** | Handle Ollama daemon offline, connection refused, and read timeout | Architecture Specs; S0-MI02 | `ProviderConnectionError`, `ProviderTimeoutError` | **PASS** (test_ollama_adapter_connection_error) |
| **REQ-HOSTED-01** | Free-tier hosted provider adapter with rate-limit and auth error handling | Final Implementation Plan p. 18 | `app/adapters/llm/hosted_adapter.py` | **PASS** (8 tests in `test_llm_adapters.py`) |
| **REQ-HOSTED-02** | No hardcoded secrets; API keys loaded from environment/settings with redaction | FinEx Security Rules; Issue #75 | `app/config/settings.py` (`SENSITIVE_FIELDS`) | **PASS** (test_settings_llm_fields_and_redaction) |
| **REQ-DET-01** | Offline deterministic fallback executing with zero network calls | Final Implementation Plan p. 18 | `app/adapters/llm/deterministic_adapter.py` | **PASS** (6 tests in `test_llm_adapters.py`) |
| **REQ-DET-02** | 100% reproducible output across identical input contexts | DoD; Compliance Rules | `DeterministicFallbackAdapter.generate` | **PASS** (test_deterministic_fallback_reproducibility) |
| **REQ-DET-03** | Safe refusal of prohibited financial advice queries | FinEx Safety Guardrails (S0-MI01) | `REFUSAL_FINANCIAL_ADVICE` intent | **PASS** (test_deterministic_fallback_refuses_prohibited_advice) |
| **REQ-CASCADE-01** | Cascade: Ollama -> Hosted Fallback -> Deterministic Fallback | Final Implementation Plan p. 18 | `app/adapters/llm/composite_provider.py` | **PASS** (test_composite_cascade_*) |
| **REQ-CASCADE-02** | Provider outage still returns a safe answer (zero crashes/unhandled errors) | Issue #75 Acceptance Criterion | `CompositeLLMProvider.generate` | **PASS** (test_composite_cascade_total_provider_outage_never_crashes) |
| **REQ-SCHEMA-01** | Schema validation against versioned `output_schema_ref` and guardrails | Port Contract; Issue #75 | `app/adapters/llm/schema_validator.py` | **PASS** (6 tests in `test_llm_adapters.py`) |
| **REQ-ENV-01** | Document environment variables in `.env.example` without committing secrets | Issue #75; Phase 3.J | `backend/.env.example` | **PASS** (Documented with placeholders) |
| **REQ-ARCH-01** | Clean ports-and-adapters separation; no pseudo-ports in `ports/adapters` | FinEx Hexagonal Architecture | Deleted `app/ports/adapters/llm.py` | **PASS** (Import from `app.adapters`) |
| **REQ-TEST-01** | Targeted test suite verifying all adapters, error modes, and cascades | Acceptance Criteria | `backend/tests/unit/test_llm_adapters.py` | **PASS** (40/40 passed) |
| **REQ-REGRESS-01** | Full regression test suite passing with zero failures | DoD | `backend/tests/` | **PASS** (All tests green) |
| **REQ-CODE-01** | Static analysis compliance (Ruff lint, Ruff format, Mypy type-checking) | Project Code Standards | `ruff check .`, `mypy app` | **PASS** (0 errors) |

---

## 3. Dependency & S0-MI02 Baseline Integration

Task `S0-MI02` (`docs/ai/baseline.md`, commit `ee4c4c8` merged into `dev`) established the empirical local AI baseline on developer workstation hardware (AMD Ryzen 5 7520U, 16 GB LPDDR5 RAM):
- **Ollama `llama3.2:latest` (3.2B Q4_K_M):** 2.02 GB disk footprint, +1.85 GB resident memory, 8.24s warm median latency, 8.71 tokens/sec throughput.
- **Ollama `deepseek-r1:1.5b` (1.8B Q4_K_M):** 1.12 GB disk footprint, +1.32 GB resident memory, 14.83s warm median latency.
- **MiniLM `all-MiniLM-L6-v2`:** 384 dimensions, ~160 MB resident memory, 24.5 ms warm CPU latency.

### S5-MI03 Sizing & Configuration Decisions:
1. **Primary Model Default:** `llama3.2:1b` (or `llama3.2:latest`), running entirely on CPU over the local Ollama daemon (`http://localhost:11434`).
2. **Timeout Envelopes:**
   - Connect timeout: `3.0s` (detects immediately if Ollama service is stopped without hanging the worker).
   - Read timeout: `10.0s` (accommodates 8-10s warm CPU generation while preventing HTTP request starvation).
   - Total timeout envelope: `13.0s` maximum before triggering cascade.

---

## 4. LLM Adapter Architecture & File Inventory

### 4.1 Changed Files in PR #139:
1. `backend/app/adapters/__init__.py`: Cleanly exports all LLM adapters and `get_llm_provider` factory.
2. `backend/app/adapters/llm/__init__.py`: Package initialization, exports, typed exceptions, and `get_llm_provider` factory.
3. `backend/app/adapters/llm/composite_provider.py`: Three-tier resilient cascade orchestrator (`Request -> Ollama -> Hosted -> Deterministic`).
4. `backend/app/adapters/llm/deterministic_adapter.py`: 100% offline, zero-network, reproducible template fallback with SEBI disclaimers.
5. `backend/app/adapters/llm/exceptions.py`: Typed `LLMProviderError` hierarchy.
6. `backend/app/adapters/llm/hosted_adapter.py`: Google Gemini REST API (default) & Groq free-tier hosted adapter.
7. `backend/app/adapters/llm/ollama_adapter.py`: Primary local Ollama REST API adapter (`/api/chat` with `/api/generate` fallback).
8. `backend/app/adapters/llm/schema_validator.py`: JSON cleaner, schema structure validation, and compliance phrase scanner.
9. `backend/app/config/settings.py`: Added configuration fields and secret redaction (`gemini_api_key`, `groq_api_key`).
10. `backend/.env.example`: Documented S5-MI03 environment variables with clean placeholders.
11. `backend/tests/unit/test_llm_adapters.py`: 40 targeted unit, integration, and contract tests.
12. `docs/evidence/s5_mi03_evidence.md`: Comprehensive evidence and audit artifact.

*Note on Architecture Cleanup:* The temporary file `backend/app/ports/adapters/llm.py` was removed during the audit because it created a misleading pseudo-port under `ports/` for concrete adapter classes. In hexagonal architecture, abstract interfaces belong in `app/ports/` and implementations belong in `app/adapters/`. No callers imported `app.ports.adapters.llm`, and all adapters are cleanly accessible via `app.adapters` and `app.adapters.llm`.

---

## 5. Free-Tier Hosted Provider Audit (Official Terms & Rate Limits)

In compliance with the project instructions, official terms and rate limits for free hosted providers were audited:

### 5.1 Google Gemini API Free Tier (`gemini-1.5-flash`) — Primary Verified Hosted Fallback
- **Documentation Source:** Google AI Studio / Gemini API Pricing & Models (Verified: 22 November 2026)
  - URL: https://ai.google.dev/pricing
  - URL: https://ai.google.dev/gemini-api/docs/models/gemini
- **Pricing:** Free of charge ($0.00).
- **Rate Limits:**
  - Requests Per Minute (RPM): `15 RPM`
  - Tokens Per Minute (TPM): `1,000,000 TPM`
  - Requests Per Day (RPD): `1,500 RPD`
- **Error Behavior:** Returns `HTTP 429 Too Many Requests` when limits are reached. `HostedLLMAdapter` maps it to `ProviderQuotaExceededError`, cascading safely to deterministic fallback.
- **Privacy & Data Handling:** Under Google's free-tier terms, prompt data may be logged for service improvement. Therefore, FinEx architecture guarantees that **no real user financial records, account numbers, or PII** are ever sent to external LLMs; requests contain only educational queries and authorized conceptual context.
- **Authentication:** `GEMINI_API_KEY` passed via query parameter `?key={api_key}` over HTTPS.

### 5.2 Groq Cloud Free Tier (`llama-3.1-8b-instant`) — Optional Alternative
- **Documentation Source:** GroqCloud Developer Console & Rate Limit Documentation (Verified: 22 November 2026)
  - URL: https://console.groq.com/docs/rate-limits
- **Pricing:** Free tier for developers.
- **Rate Limits:**
  - Requests Per Minute (RPM): `30 RPM`
  - Tokens Per Minute (TPM): `6,000 TPM`
  - Requests Per Day (RPD): `14,400 RPD`
- **Role:** Preserved as an optional alternative for developers with existing Groq credentials, without adding extra tiers to the cascade.

### 5.3 Secret Redaction & Configuration Safety
- Settings class in `app/config/settings.py` includes `gemini_api_key` and `groq_api_key`.
- Both fields are registered in `SENSITIVE_FIELDS: ClassVar[set[str]]`.
- Calling `settings.redacted_dict()` automatically masks their values to `"[REDACTED]"`.

---

## 6. Non-Negotiable Financial Safety & Regulatory Compliance

In accordance with SEBI (Investment Advisers) Regulations, 2013 and FinEx architectural guardrails:
1. **The LLM Explains and Interprets; It Never Calculates Authoritative Numbers:**
   - Numerical calculations (portfolio value, PnL, risk scoring, asset weights) remain 100% outside the LLM.
2. **Prohibited Financial Advice Detection:**
   - `SchemaValidator` scans all LLM outputs for prohibited phrases:
     `"guaranteed return"`, `"guaranteed profit"`, `"risk-free profit"`, `"buy this stock"`, `"sure shot"`, etc.
   - If detected, `ProhibitedContentError` is raised, discarding the output and triggering safe fallback.
3. **Deterministic Fallback Refusal Intent:**
   - When user queries contain direct advice questions (e.g., *"Which stock to buy today?"*), `DeterministicFallbackAdapter` generates an explicit refusal response:
     - `intent: "REFUSAL_FINANCIAL_ADVICE"`
     - Answer text stating that FinEx cannot provide buy/sell advice or market predictions.
     - Mandates consulting a licensed financial advisor.
4. **Transparent Outage Disclaimers:**
   - Every deterministic fallback response includes `limitations_disclaimer`:
     *"FinEx educational prototype: Safe deterministic fallback generated during provider outage. Not personalized financial, legal, or investment advice."*

---

## 7. Verification Test Suite Execution Results

### 7.1 Targeted LLM Adapter Tests (`backend/tests/unit/test_llm_adapters.py`)
Command: `pytest tests/unit/test_llm_adapters.py -v --no-cov`
Execution Result: **40 passed in 0.35s (100% pass rate)**

### 7.2 AI & Port Related Unit Test Suites
Command: `pytest tests/unit/test_embedding_port.py tests/unit/test_minilm_adapter.py tests/unit/test_ai_refusal_case.py tests/unit/test_ai_assistant_auth.py tests/unit/test_ai_feedback_persistence.py tests/unit/test_ai_eval.py tests/test_local_settings.py tests/test_r0_settings.py -q`
Execution Result: **128 passed in 4.37s (100% pass rate)**

### 7.3 Full Backend Test Suite Non-Regression
Command: `pytest -q --no-cov`
Execution Result: **2,857 passed, 12 skipped, 13 xfailed, 2 xpassed in 271.91s (0:04:31)**
Zero failures across the entire test suite.

### 7.4 Static Code Analysis & Type Checking
- **Ruff Lint:** `python -m ruff check .` -> `All checks passed!` (0 errors)
- **Ruff Format:** `python -m ruff format --check .` -> `316 files already formatted.`
- **Mypy Type Checking:** `python -m mypy app` -> `Success: no issues found in 161 source files`

---

## 8. Definition of Done & Handover

- [x] Code implementation complete on branch `feature/s5-mi03-llm-provider`
- [x] Verified against existing contracts; zero breaking changes to `app/ports/llm_provider.py`
- [x] All 40 targeted unit and contract tests written and passing
- [x] Three-tier resilient cascade verified (Ollama -> Free Hosted -> Deterministic Fallback)
- [x] Provider outage resilience verified: outage still returns a safe answer
- [x] No secrets committed; API keys read from environment/settings with automatic redaction
- [x] Full backend regression verified (all tests passed, 0 failures)
- [x] Evidence artifact documented in `docs/evidence/s5_mi03_evidence.md`
- [x] Pull request opened targeting `dev` ([PR #139](https://github.com/Mrugankkakade17-svg/Finex/pull/139))
- [x] Assigned secondary reviewer: **Payal (`@payalmude14-star`)**
