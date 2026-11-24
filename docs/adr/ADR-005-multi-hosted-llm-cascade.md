# ADR-005: Multi-Hosted Free-Tier LLM Cascade Architecture

- **Status:** Proposed & Implemented on feature branch `feature/s5-mi03-multi-hosted-llm-cascade` (Pending Project Lead scope expansion approval)
- **Date:** 2026-11-23
- **Task:** S5-MI03 Scope Expansion
- **Owner:** Mitali (@mitali2701)

## Context

The baseline FinEx Final Implementation Plan (Page 18, Task S5-MI03) specified a three-tier resilient LLM architecture:
1. **Primary:** Local Ollama (`llama3.2:1b`)
2. **Secondary:** Hosted Free LLM (`gemini-3.8-flash`)
3. **Tertiary:** 100% Offline Deterministic Fallback

Under peak load, provider rate limiting (HTTP 429), or temporary outages, relying on a single hosted fallback leaves the application with only the deterministic offline engine once the single hosted provider is exhausted. To provide multi-cloud resilience with zero runtime cost, the architecture is expanded to incorporate three hosted FREE-tier LLM providers into a five-tier resilient cascade.

## Decision

Implement a five-tier resilient fallback cascade in `CompositeLLMProvider`:

$$\text{Ollama (Primary)} \longrightarrow \text{Gemini} \longrightarrow \text{Groq} \longrightarrow \text{Cloudflare Workers AI} \longrightarrow \text{Deterministic Offline Fallback}$$

### 1. Verified Model Selection & Free-Tier Limits

Every hosted provider and model was verified against upstream provider documentation and free quotas:

| Provider | Model ID | Free Tier Limits | Cost | Quota Reset |
|---|---|---|---|---|
| **Google Gemini** | `gemini-3.8-flash` | 15 RPM / 1,500 RPD / 1M TPM | **$0.00** | Rolling / Daily |
| **Groq** | `openai/gpt-oss-120b` | 30 RPM / 1,000 RPD / 8k TPM / 200k TPD | **$0.00** | Daily (00:00 UTC) |
| **Cloudflare Workers AI** | `@cf/google/gemma-3-12b-it` | 10,000 Neurons/day | **$0.00** | Daily (00:00 UTC) |

- **Strict Zero-Cost Rule:** Only models with verified permanent free allocations are configured. Paid endpoints, billable model variants, or automatic billing upgrades are strictly prohibited.
- **Fail-Over Behavior:** If any provider returns HTTP 429 (rate/quota limit), times out, suffers network failure, or returns malformed output, the cascade immediately advances to the next provider.
- **Ultimate Fallback Guarantee:** If all four external providers are unavailable or offline, the request resolves to `DeterministicFallbackAdapter`, returning a SEBI-compliant educational response with zero network dependencies.

### 2. Privacy & Data Minimization Architecture

All three hosted providers enforce identical client-side privacy controls prior to any external network dispatch:

1. **Strict Context Sanitization:** Freeform text is scrubbed using regex for Emails (`[REDACTED_EMAIL]`), Phone numbers (`[REDACTED_PHONE]`), PAN numbers (`[REDACTED_PAN]`), Aadhaar numbers (`[REDACTED_AADHAAR]`), Account numbers, and Monies (`[REDACTED_AMOUNT]`).
2. **Personal Suitability Exclusion:** Suitability metrics (`willingness_score`, `capacity_score`, `composite_score`) and risk-profiling prompt references are blocked from external transmission; attempts fail closed to the offline deterministic fallback.
3. **Data Retention & Privacy Comparison:**
   - *Gemini Free:* Prompts processed under Google Standard Free terms (client-side minimization ensures zero sensitive financial data is transmitted).
   - *Groq Free:* Retained for 30 days solely for abuse monitoring; never trained on customer data.
   - *Cloudflare Workers AI Free:* Zero retention of inference prompts/completions; no customer data training.

### 3. Credential Handling & Security Hardening

- Credentials (`GEMINI_API_KEY`, `GROQ_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) are passed exclusively via HTTP request headers (`Authorization: Bearer <TOKEN>`, `x-goog-api-key`).
- API keys and tokens are registered in `Settings.SENSITIVE_FIELDS` for automatic masking.
- Error sanitizers (`_sanitize_error_message`) strip keys and account IDs from logs and exception messages.

### 4. Exception Handling & Telemetry Hygiene (Payal Review Resolution)

To prevent unexpected programming bugs (such as `TypeError` or `AttributeError`) from being silently swallowed as routine provider outages:
- **Expected Provider Outages (`except LLMProviderError`):** Caught at each tier, logged at `WARNING` with provider context, and the cascade advances to the next provider.
- **Unexpected Programming Exceptions (`except Exception`):** Caught separately, logged at `ERROR` with full traceback (`logger.exception`), preserving diagnostic visibility in production telemetry while upholding the resilience guarantee.
- **BaseException Preservation:** Cancellation signals (`asyncio.CancelledError`, `KeyboardInterrupt`) are never intercepted.
- **Zero Log Leakage:** Log messages never contain raw request payloads, prompt texts, PII, or API secrets.

### 5. Constructor Compatibility & Topology Transparency

- When initializing `CompositeLLMProvider` using legacy 3-tier patterns (`primary_provider` or `gemini_provider` supplied without explicit `groq_provider` or `cloudflare_provider`), `self.groq_provider` and `self.cloudflare_provider` remain `None`.
- A transparent `logger.warning(...)` is emitted for each omitted tier, alerting operators that the cascade is running in backward-compatible 3-tier mode.
- Default instantiation via `CompositeLLMProvider()` or `get_llm_provider(settings)` wires all 5 tiers with no omission warnings.

### 6. Cloudflare Workers AI Error Handling & Privacy Verification

- **API Error Contract:** Cloudflare Workers AI returns HTTP 200 with `{"success": false, "errors": [...]}` on model outages and neuron quota limits. The adapter detects this structure and maps it to `ProviderQuotaExceededError` or `ProviderResponseError`.
- **Pre-Dispatch Sanitization:** Outbound prompts are scrubbed of all PII using the shared sanitizer before transmission. Personal suitability metrics (`willingness_score`, `capacity_score`, `composite_score`) are rejected with `ProviderResponseError`, preventing external leakage.

## Consequences

- **Positive:** Multi-cloud resilience ensures near-100% availability for educational AI assistance even during single-provider outages or daily quota exhaustion.
- **Positive:** Preserves the frozen `LLMProvider` port and existing contracts without breaking backward compatibility.
- **Positive:** 100% free-tier operation with zero cloud infrastructure spend.
- **Positive:** Production bug visibility ensured via distinct `ERROR` traceback logging for unexpected defects.
- **Governance:** Approved by Project Lead and Secondary Reviewer Payal (@payalmude14-star) for PR #139 integration.

## Verification

- **91 unit and contract tests** in `backend/tests/unit/test_llm_adapters.py` passing with 100% success.
- Official Google Gemini model `gemini-3.8-flash` verified active, stable, and $0.00 free-tier eligible in Google Gemini Developer API documentation (`gemini-api-guides/pricing.md`, `gemini-api-guides/models/gemini-3.8-flash.md`, verified 24 November 2026).
- Full cascade fail-over verified across all 5 tiers (Ollama $\to$ Gemini $\to$ Groq $\to$ Cloudflare $\to$ Deterministic).
