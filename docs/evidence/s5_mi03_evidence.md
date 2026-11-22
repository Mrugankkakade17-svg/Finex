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
**Head Commit:** `f7f774a` (Verified active Gemini 3.5 Flash-Lite & Privacy Boundary)
**Acceptance Criterion:** `app/adapters/llm/* (N) Provider outage still returns a safe answer`
**Date:** 22 November 2026  

---

## 1. Executive Summary & Objective

The objective of `S5-MI03` is to deliver an authoritative, decoupled LLM adapter layer for FinEx, implementing a resilient three-tier cascade:
1. **Primary Provider (`OllamaLLMAdapter`):** Lightweight local CPU inference (`llama3.2:1b` via Ollama REST API `/api/chat` with `/api/generate` fallback) with finite connection (3s) and read (10s) timeouts, ensuring 100% offline operation without external network dependency.
2. **Secondary Provider (`HostedLLMAdapter`):** Free-tier hosted provider adapter designating **Google Gemini API (`gemini-3.5-flash-lite`)** as the authoritative verified free hosted provider. Enforces client-side data minimization, PII/financial scrubbing, header-based credential authentication (`x-goog-api-key`), and clean handling of HTTP 404, 429 quota exhaustion, 401/403 authentication, and 500+ provider errors.
3. **Tertiary Provider (`DeterministicFallbackAdapter`):** Purely offline, template-based deterministic fallback executing with **zero network calls**, zero external API calls, and zero model hallucinations. Enforces non-negotiable financial compliance rules (refusing direct buy/sell tips or return guarantees), guarantees 100% reproducible output, and injects transparent outage disclaimers.
4. **Resilient Orchestrator (`CompositeLLMProvider`):** Implements the frozen `LLMProvider` protocol (`app/ports/llm_provider.py`). Seamlessly cascades: `Request -> Ollama -> Hosted -> Deterministic`. A complete external provider outage **never raises an unhandled exception or crashes the application**; it always returns a validated, safe answer (`Provider outage still returns a safe answer`).

---

## 2. Authoritative Requirements Traceability Matrix

| Requirement ID | Requirement Description | Source Document / Ref | Implemented Artifact(s) | Verification Status |
| :--- | :--- | :--- | :--- | :---: |
| **REQ-PORT-01** | Preserve existing `LLMProvider` protocol and dataclasses without breaking changes | Final Implementation Plan p. 18; Issue #75 | `backend/app/ports/llm_provider.py` (V) | **PASS** (Protocol preserved 100%) |
| **REQ-OLLAMA-01** | Primary Ollama adapter wrapping local model with finite timeouts | Final Implementation Plan p. 18 | `app/adapters/llm/ollama_adapter.py` | **PASS** (7 unit tests passing) |
| **REQ-OLLAMA-02** | Handle Ollama daemon offline, connection refused, and read timeout | Architecture Specs; S0-MI02 | `ProviderConnectionError`, `ProviderTimeoutError` | **PASS** (test_ollama_adapter_connection_error) |
| **REQ-HOSTED-01** | Free-tier hosted provider adapter using verified active Gemini model (`gemini-3.5-flash-lite`) | Final Implementation Plan p. 18 | `app/adapters/llm/hosted_adapter.py` | **PASS** (10 unit & privacy tests passing) |
| **REQ-HOSTED-02** | No hardcoded secrets; API keys loaded from environment/settings with redaction | FinEx Security Rules; Issue #75 | `app/config/settings.py` (`SENSITIVE_FIELDS`) | **PASS** (test_settings_llm_fields_and_redaction) |
| **REQ-PRIVACY-01** | Client-side privacy boundary: strip financial details, balances, PAN, and mask PII | Milestone #6 Privacy Resilience | `HostedLLMAdapter.sanitize_context_for_external_provider` | **PASS** (test_hosted_adapter_privacy_*) |
| **REQ-AUTH-01** | Transmit API key via HTTP header (`x-goog-api-key`); zero secrets in URL | Security Best Practices | `HostedLLMAdapter._call_gemini` | **PASS** (test_hosted_gemini_adapter_success) |
| **REQ-DET-01** | Offline deterministic fallback executing with zero network calls | Final Implementation Plan p. 18 | `app/adapters/llm/deterministic_adapter.py` | **PASS** (6 unit tests passing) |
| **REQ-DET-02** | 100% reproducible output across identical input contexts | DoD; Compliance Rules | `DeterministicFallbackAdapter.generate` | **PASS** (test_deterministic_fallback_reproducibility) |
| **REQ-DET-03** | Safe refusal of prohibited financial advice queries | FinEx Safety Guardrails (S0-MI01) | `REFUSAL_FINANCIAL_ADVICE` intent | **PASS** (test_deterministic_fallback_refuses_prohibited_advice) |
| **REQ-CASCADE-01** | Cascade: Ollama -> Hosted Fallback -> Deterministic Fallback | Final Implementation Plan p. 18 | `app/adapters/llm/composite_provider.py` | **PASS** (test_composite_cascade_*) |
| **REQ-CASCADE-02** | Provider outage still returns a safe answer (zero crashes/unhandled errors) | Issue #75 Acceptance Criterion | `CompositeLLMProvider.generate` | **PASS** (test_composite_cascade_total_provider_outage_never_crashes) |
| **REQ-SCHEMA-01** | Schema validation against versioned `output_schema_ref` and guardrails | Port Contract; Issue #75 | `app/adapters/llm/schema_validator.py` | **PASS** (6 unit tests passing) |
| **REQ-ENV-01** | Document environment variables in `.env.example` without committing secrets | Issue #75; Phase 3.J | `backend/.env.example` | **PASS** (Documented with placeholders) |
| **REQ-ARCH-01** | Clean ports-and-adapters separation; no pseudo-ports in `ports/adapters` | FinEx Hexagonal Architecture | Removed `app/ports/adapters/llm.py` | **PASS** (Clean `app.adapters` export) |
| **REQ-TEST-01** | Targeted test suite verifying all adapters, error modes, and cascades | Acceptance Criteria | `backend/tests/unit/test_llm_adapters.py` | **PASS** (45/45 passed) |
| **REQ-REGRESS-01** | Full regression test suite passing with zero failures | DoD | `backend/tests/` | **PASS** (All tests green) |
| **REQ-CODE-01** | Static analysis compliance (Ruff lint, Ruff format, Mypy type-checking) | Project Code Standards | `ruff check .`, `mypy app` | **PASS** (0 errors) |

---

## 3. Hosted Model Audit: Google Gemini & Groq Review

### 3.1 Gemini Model Selection & Depreciation Audit
- **Previous Configuration:** `gemini-1.5-flash`
- **Deprecation Finding:** According to official Google Gemini API documentation (`gemini-api-guides/deprecations.md`), `gemini-1.5-flash` was formally shut down on **September 29, 2025**. Furthermore, `gemini-2.0-flash` was shut down on June 1, 2026, and Google limits access to `gemini-2.5-flash` strictly to legacy users. Google's official guidance states: *"For any new projects, use our latest models: 3.5 Flash-Lite or 3.8 Flash."*
- **Current Verified Active Model:** `gemini-3.5-flash-lite`
  - **Official Model Code:** `gemini-3.5-flash-lite`
  - **Release / Update Date:** Stable release, July 2026 update (`gemini-api-guides/models/gemini-3.5-flash-lite.md`).
  - **Official Documentation Source:**
    - Models Overview: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
    - Pricing Guide: https://ai.google.dev/pricing#gemini-3.5-flash-lite
  - **Pricing Tier:** Free of charge ($0.00 for text/multimodal input, $0.00 for output including thinking tokens).
  - **Capabilities:** High-throughput, low-latency, native structured outputs (`responseMimeType: "application/json"`). Token limit: 1,048,576 input / 65,536 output.
  - **Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`

### 3.2 Groq Review & Scope Alignment
- **Groq Availability Audit:** Groq officially discontinued self-serve access to `llama-3.1-8b-instant` on free and standard developer tiers on **August 16, 2026**. Requests sent to this model ID on developer tiers return errors.
- **Scope Alignment Decision:** The FinEx Final Implementation Plan Page 18 specifically mandates:
  *"LLM provider adapter (Ollama, free hosted fallback) with deterministic fallback"* (singular).
  Retaining Groq would introduce an unverified/discontinued free tier. Groq was therefore removed to adhere strictly to the single authoritative free hosted fallback specified in the Final Implementation Plan.

---

## 4. Privacy Audit & Data Minimization at Request Boundary

Under Google's published developer terms for the free tier (*"Used to improve our products: Yes"*), prompts may be processed for service improvement. Therefore, FinEx architecture enforces non-negotiable client-side data minimization before any prompt leaves the backend:

1. **Context Whitelisting (`SAFE_CONTEXT_KEYS`):**
   Only non-sensitive, educational, and schema-relevant keys are permitted:
   `{"query", "question", "message", "topic", "concept", "goal_name", "risk_category", "willingness_score", "capacity_score", "composite_score", "chunks", "citations", "retriever_version"}`.
2. **Strict Financial & PII Stripping (`SENSITIVE_CONTEXT_KEYS`):**
   Sensitive financial keys are explicitly stripped before prompt construction:
   `{"user_id", "email", "phone", "pan", "aadhaar", "ssn", "account_id", "account_number", "iban", "balance", "available_balance", "current_balance", "transactions", "holdings", "portfolio_value", "total_wealth", "salary", "net_worth", "password", "token"}`.
3. **Freeform Query PII / Number Masking:**
   Any freeform user query text is scanned and masked via regex:
   - Email addresses $\rightarrow$ `[REDACTED_EMAIL]`
   - Indian PAN numbers $\rightarrow$ `[REDACTED_PAN]`
   - 10-16 digit account / phone numbers $\rightarrow$ `[REDACTED_IDENTIFIER]`
   - Currency amounts (Rs./INR/₹/$) $\rightarrow$ `[REDACTED_AMOUNT]`
4. **Header-Based Authentication & Zero URL Secrets:**
   The API key is transmitted strictly via `x-goog-api-key: {self.api_key}` HTTP header. The URL contains zero query parameters (`.../gemini-3.5-flash-lite:generateContent`), preventing credential leakage in access logs or web caches.
5. **Exception Sanitization:**
   All exception handlers pass error messages through `_sanitize_error_message()` to ensure `self.api_key` is never exposed in logs, diagnostics, or test outputs.

---

## 5. Non-Negotiable Financial Safety & Regulatory Compliance

In accordance with SEBI (Investment Advisers) Regulations, 2013:
1. **The LLM Explains and Interprets; It Never Calculates Authoritative Numbers:**
   - Calculations (portfolio value, PnL, risk scoring, asset allocation weights) remain 100% deterministic outside the LLM.
2. **Prohibited Financial Advice Detection:**
   - `SchemaValidator` scans all LLM outputs for prohibited phrases:
     `"guaranteed return"`, `"guaranteed profit"`, `"risk-free profit"`, `"buy this stock"`, `"sure shot"`, etc.
   - If detected, `ProhibitedContentError` is raised, triggering safe fallback.
3. **Deterministic Fallback Refusal Intent:**
   - Queries seeking direct stock recommendations trigger `REFUSAL_FINANCIAL_ADVICE` intent advising consultation with a licensed financial advisor.
4. **Transparent Outage Disclaimers:**
   - Every deterministic fallback response includes `limitations_disclaimer`:
     *"FinEx educational prototype: Safe deterministic fallback generated during provider outage. Not personalized financial, legal, or investment advice."*

---

## 6. Verification Test Suite Execution Results

### 6.1 Targeted LLM Adapter Tests (`backend/tests/unit/test_llm_adapters.py`)
Command: `pytest tests/unit/test_llm_adapters.py -v --no-cov`
Execution Result: **45 passed in 0.39s (100% pass rate)**

### 6.2 AI & Port Related Unit Test Suites
Command: `pytest tests/unit/test_embedding_port.py tests/unit/test_minilm_adapter.py tests/unit/test_ai_refusal_case.py tests/unit/test_ai_assistant_auth.py tests/unit/test_ai_feedback_persistence.py tests/unit/test_ai_eval.py tests/test_local_settings.py tests/test_r0_settings.py -q`
Execution Result: **128 passed in 4.18s (100% pass rate)**

### 6.3 Full Backend Test Suite Non-Regression
Command: `pytest -q --no-cov`
Execution Result: **2,862 passed, 12 skipped, 13 xfailed, 2 xpassed in 280.02s (0:04:40)**
Zero failures across the entire test suite.

### 6.4 Static Code Analysis & Type Checking
- **Ruff Lint:** `python -m ruff check .` -> `All checks passed!` (0 errors)
- **Ruff Format:** `python -m ruff format --check .` -> `316 files already formatted.`
- **Mypy Type Checking:** `python -m mypy app` -> `Success: no issues found in 161 source files`

---

## 7. Definition of Done & Handover

- [x] Code implementation complete on branch `feature/s5-mi03-llm-provider`
- [x] Verified active Gemini model: `gemini-3.5-flash-lite` (free-of-charge tier confirmed in official docs)
- [x] Deprecated `gemini-1.5-flash` and discontinued Groq models removed
- [x] Client-side privacy boundary and PII/financial data scrubbing verified by unit tests
- [x] Header-based authentication (`x-goog-api-key`) with zero secrets in URLs
- [x] All 45 targeted unit and contract tests written and passing
- [x] Full backend regression verified (0 failures)
- [x] Pull request opened targeting `dev` ([PR #139](https://github.com/Mrugankkakade17-svg/Finex/pull/139))
- [x] Assigned secondary reviewer: **Payal (`@payalmude14-star`)**
