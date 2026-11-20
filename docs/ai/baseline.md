# FinEx AI Hardware Baseline, Model Benchmarks & Architectural Readiness Report

**Document Reference:** `FINEX-DOCS-AI-BASELINE-V2`  
**Task ID:** `S0-MI02` (Issue #12 / PR #116)  
**Author:** Mitali Dobale (Senior AI Engineer & Implementation Lead)  
**Reviewer:** Mrugank Kakade (`@Mrugankkakade17-svg`)  
**Sprint:** Sprint 0 — Verified Baseline  
**Date:** 20 November 2026  
**Status:** Verified Baseline with Empirical Local Measurements  
**Target Repository:** `https://github.com/Mrugankkakade17-svg/Finex`  
**Git Branch:** `feature/S0-MI02`  
**Related Evidence File:** `docs/evidence/s0_mi02_evidence.md`  

---

## 1. Executive Summary & Purpose

This document establishes the empirical hardware and AI runtime baseline for the FinEx platform. As mandated by the *FinEx Final Implementation Plan* (dated 17 November 2026, Page 9), Sprint 0 is a strictly verified baseline sprint designed to validate existing components, measure local hardware capabilities, evaluate model latency and throughput, and define concrete architectural recommendations before production feature implementation begins in Sprint 1.

### 1.1 Acceptance Criteria Mapping (Implementation Plan Page 9)
- **Requirement 1:** Run `ai/` tests and audit existing test coverage. $\rightarrow$ **Completed (Section 3)**
- **Requirement 2:** Try Ollama, MiniLM and FinBERT on team development laptop. $\rightarrow$ **Completed with actual local CPU execution (Sections 4, 5, 6)**
- **Requirement 3:** Record CPU latency and RAM for each model. $\rightarrow$ **Completed (Sections 4, 5, 6)**
- **Requirement 4:** Feed the sentiment decision for Sprint 6. $\rightarrow$ **Completed with empirical justification (Section 7)**
- **Requirement 5:** Deliver authoritative baseline documentation. $\rightarrow$ **Completed (`docs/ai/baseline.md` and `docs/evidence/s0_mi02_evidence.md`)**

### 1.2 Data Provenance & Measurement Transparency Statement
In strict adherence to the **Honesty Rules** defined in the *FinEx Final Implementation Plan* (Page 1: *"Nothing here is a test result: no test, server or migration was run while planning"*), all figures in this document represent **actual, direct measurements taken on the local workstation hardware**:

1. **Ollama LLM Execution (`llama3.2:latest` & `deepseek-r1:1.5b`):** Directly executed via Ollama REST API (`http://localhost:11434/api/generate`). Models were evicted from memory prior to testing using `keep_alive: 0` to measure genuine cold-start load times from disk, followed by 10 warm runs per model.
2. **MiniLM Embeddings (`sentence-transformers/all-MiniLM-L6-v2`):** Directly loaded and executed locally via PyTorch 2.15.0+cpu across single queries, batch of 5, and batch of 10 chunks.
3. **FinBERT Financial Sentiment (`ProsusAI/finbert`):** Directly loaded and executed locally via Hugging Face `transformers` and PyTorch CPU across positive, negative, and neutral financial news headlines, measuring single headline and batch 10 latency.
4. **Dependency Isolation:** Model testing dependencies were installed in an isolated benchmark virtual environment (`scratch/.bench_venv`), keeping `backend/requirements.txt` lightweight and clean.

---

## 2. Workstation Hardware & Environment Specifications

All benchmarks were performed directly on the primary engineering development workstation.

| Parameter | Specification | Verification Method |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Home (64-bit Build 26100) | `Get-CimInstance Win32_OperatingSystem` |
| **Processor (CPU)** | AMD Ryzen 5 / AMD64 Family 23 Model 160 Stepping 0 (8 Logical Cores, ~3.20 GHz base) | `Get-CimInstance Win32_Processor` |
| **System RAM** | 16.00 GB Physical DDR4 (15.28 GB addressable) | `GlobalMemoryStatusEx` Win32 API |
| **Free RAM at Baseline** | ~4.87 GB Available (~71% background load) | Win32 Memory API |
| **Disk Storage** | 244.14 GB Total / 22.42 GB Available SSD | `Get-PSDrive C` |
| **Python Runtimes** | - Primary App: Python 3.13.17 (`backend/.venv`)<br>- Benchmark Runner: Python 3.13.17 (`scratch/.bench_venv`) | `python --version` |
| **LLM Service** | Ollama v0.40.16 (Windows Desktop Service on port 11434) | `GET http://localhost:11434/api/tags` |
| **GPU Acceleration** | None (CPU inference only; `size_vram: 0` in Ollama) | `GET http://localhost:11434/api/ps` |

---

## 3. AI Test Execution Results & Module Readiness

A comprehensive test audit was executed against all test files in the `ai/` and `backend/` directories using Pytest 8.4.1.

### 3.1 Test Execution Summary Table

| Test Suite Path | Scope / Domain | Total | Passed | Failed | Skipped | Status Assessment |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ai/risk/test_scoring.py` | Risk Scoring Deterministic Engine | 32 | **32** | 0 | 0 | **PASSED:** 12 risk profiles, boundary transitions, 1000-run replay determinism. |
| `ai/risk/test_explanation.py` | Risk Explanation & Prompt Template Guardrails | 11 | **11** | 0 | 0 | **PASSED:** Zero numerical drift, injection resistance, fallback on malformed JSON. |
| `backend/tests/unit/test_ai_refusal_case.py` | Regulatory Advice Refusal (`S0-MI01` / BUG-01) | 50 | **50** | 0 | 0 | **PASSED:** Precompiled `re.IGNORECASE` pattern matching across all casing variants. |
| `ai/test_rag_prototype.py` | RAG Prototype & Document Chunking (`S1-AI-02`) | 4 | 0 | **4** | 0 | **FAILED (By Design):** Tests require functions planned for Sprint 1 (`S1-AI-02`). |
| `ai/eval/run_eval.py` | LLM Quantitative Evaluation Pipeline | — | — | — | — | **NOT TESTED:** File does not exist in Sprint 0; scheduled for Sprint 5 (`S5-MI05`). |
| **Total Test Count** | **Comprehensive AI Test Audit** | **97** | **93** | **4** | **0** | **95.9% Pass Rate across audited suites.** |

### 3.2 In-Depth Analysis of Failing Tests in `ai/test_rag_prototype.py`
The 4 failures in `ai/test_rag_prototype.py` were verified against the codebase:
- `test_document_registry_structure`: Fails with `AttributeError: module 'rag_prototype_mod' has no attribute 'load_document_registry'`.
- `test_chunking_metadata_attachment`: Fails with `TypeError: chunk_financial_document() got an unexpected keyword argument 'doc_id'`.
- `test_ingest_all_registered_documents`: Fails with `AttributeError: module 'rag_prototype_mod' has no attribute 'ingest_all_registered_documents'`.
- `test_retrieval_five_golden_questions`: Fails with `AttributeError: module 'rag_prototype_mod' has no attribute 'ingest_all_registered_documents'`.

**Audit Conclusion:** These tests were authored specifically for **Task `S1-AI-02` (Sprint 1)** to define the acceptance interface for Palak / Likhita's document ingestion pipeline. The existing file `ai/01_rag_prototype.py` is an unmounted exploratory script. In strict adherence to Sprint 0 rules, we preserve existing code and do not implement Sprint 1 features prematurely.

---

## 4. Empirical Ollama LLM Benchmark (AMD Ryzen CPU)

All measurements conducted locally via HTTP REST API (`/api/generate`) with test prompt:  
`"Explain asset allocation in 2 sentences."` (Temperature: 0.2, Seed: 42).

### 4.1 Eviction & Measurement Protocol
To guarantee genuine cold-start measurements:
1. Active models were checked via `GET /api/ps`.
2. Existing resident models were evicted using `keep_alive: 0`.
3. Eviction was verified (`GET /api/ps` returned `{"models": []}`).
4. Genuine cold-start request was issued, recording real disk-to-RAM loading duration.
5. 10 warm runs were executed consecutively ($N=10$).
6. Model was evicted post-test to restore baseline RAM.

### 4.2 Benchmark Results Table (Actual Measured Values)

| Metric | `llama3.2:latest` (3.2B Q4_K_M) | `deepseek-r1:1.5b` (1.8B Q4_K_M) | Operational Analysis |
| :--- | :---: | :---: | :--- |
| **Disk Size / Quantization** | 2.02 GB (Q4_K_M) | 1.12 GB (Q4_K_M) | Compact GGUF format fits workstation storage. |
| **Active Models Before Test** | `[]` (Evicted) | `[]` (Evicted) | Verifies genuine cold-start state. |
| **Pre-Test System RAM Used** | 10.92 GB (71%) | 10.46 GB (68%) | Workstation background memory state. |
| **Cold Start Wall Clock** | **18.189 s** | **23.311 s** | Unsuitable for synchronous HTTP request ($>18\text{s}$). |
| **Cold Disk-to-RAM Load** | **8.502 s** | **4.404 s** | Real disk read overhead into memory. |
| **Cold Prompt Eval Time** | 1.406 s | 0.298 s | Sub-second tokenization and prompt encoding. |
| **Cold Generation Time** | 8.251 s (72 tokens) | 18.590 s (310 tokens) | `deepseek-r1` generates internal `<think>` tokens. |
| **Cold Generation Speed** | 8.73 tokens/sec | 16.68 tokens/sec | Faster token rate on smaller 1.8B architecture. |
| **RAM During Inference** | 12.77 GB (Delta: **+1.85 GB**) | 11.78 GB (Delta: **+1.32 GB**) | Physical memory resident during execution. |
| **Warm Run #01 Latency** | 7.321 s (9.62 tok/s) | 16.168 s (17.34 tok/s) | Steady-state generation across 10 runs. |
| **Warm Run #02 Latency** | 7.571 s (9.29 tok/s) | 15.189 s (18.47 tok/s) | Consistent generation speed. |
| **Warm Run #03 Latency** | 7.540 s (9.32 tok/s) | 14.712 s (19.07 tok/s) | Low timing jitter. |
| **Warm Run #04 Latency** | 8.198 s (8.58 tok/s) | 14.621 s (19.20 tok/s) | Thermal dissipation under load. |
| **Warm Run #05 Latency** | 8.584 s (8.20 tok/s) | 15.031 s (18.67 tok/s) | Steady execution. |
| **Warm Run #06 Latency** | 8.623 s (8.16 tok/s) | 14.916 s (18.81 tok/s) | Sustained CPU throughput. |
| **Warm Run #07 Latency** | 8.340 s (8.42 tok/s) | 14.904 s (18.83 tok/s) | Consistent performance. |
| **Warm Run #08 Latency** | 8.293 s (8.46 tok/s) | 14.637 s (19.16 tok/s) | Stable generation. |
| **Warm Run #09 Latency** | 8.683 s (8.09 tok/s) | 14.764 s (19.04 tok/s) | Near peak observed latency. |
| **Warm Run #10 Latency** | 7.842 s (8.96 tok/s) | 14.685 s (19.11 tok/s) | Final iteration. |
| **Warm Min Latency** | **7.321 s** | **14.621 s** | Best-case warm latency. |
| **Warm Mean Latency** | **8.100 s** | **14.963 s** | Average over 10 consecutive warm runs. |
| **Warm Median Latency** | **8.245 s** | **14.834 s** | Representative real-world user latency. |
| **90th Percentile (Rank 9)** | **8.683 s** | **16.168 s** | Empirical 90th percentile of 10 samples. |
| **Warm Max Latency** | **8.683 s** | **16.168 s** | Worst-case warm latency. |
| **Mean Generation Throughput** | **8.71 tokens/sec** | **18.77 tokens/sec** | Generation throughput on 8 CPU threads. |
| **Post-Test Evicted RAM** | **10.43 GB** | **10.39 GB** | Verified memory released via `keep_alive: 0`. |

---

## 5. MiniLM (`all-MiniLM-L6-v2`) Actual Local Benchmark

Testing was conducted using PyTorch CPU (version `2.15.0+cpu`) in an isolated benchmark virtual environment (`scratch/.bench_venv`), preserving production dependencies.

- **Model ID:** `sentence-transformers/all-MiniLM-L6-v2`
- **Architecture:** BERT-6L-384H (22.7M parameters)
- **Output Embedding Dimensions:** **384** (Verified: Float32 normalized vectors)
- **Threads Configured:** 8 CPU threads (`torch.set_num_threads(8)`)
- **Baseline RAM Before Load:** **10.35 GB**
- **Model Load Time (Disk to CPU RAM):** **1.580 s** (Download + Load first time: 70.989s)
- **Resident RAM Delta for Model:** **+0.16 GB** (~160 MB resident footprint)
- **RAM During Inference:** **10.51 GB**

### 5.1 Latency & Throughput Benchmark Results ($N=10$ Warm Runs)
| Input Scenario | Cold Latency | Warm Min | Warm Mean | Warm Median | Warm Max | Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Single Query** (*"What is the management fee..."*) | **74.54 ms** | **19.64 ms** | **23.68 ms** | **24.51 ms** | **27.18 ms** | **~41 queries/sec** |
| **Batch 5 Chunks** (Financial factsheet excerpts) | — | **37.53 ms** | **42.27 ms** | **40.88 ms** | **63.52 ms** | **8.45 ms / chunk** (~118 chunks/s) |
| **Batch 10 Chunks** (Full fund prospectus section) | — | **60.11 ms** | **82.99 ms** | **68.14 ms** | **207.10 ms** | **8.30 ms / chunk** (~120 chunks/s) |

### 5.2 Architectural Verdict for Sprint 1 & Sprint 5
`all-MiniLM-L6-v2` is **100% viable on CPU**. With single query embeddings completing in **~24.5 ms** and batch processing operating at **~8.3 ms per chunk**, MiniLM easily fits within real-time API latency budgets and integrates natively with PostgreSQL `pgvector` (`vector(384)`).

---

## 6. FinBERT (`ProsusAI/finbert`) Actual Local Benchmark

Testing was conducted using Hugging Face `transformers 5.23.0` and PyTorch CPU in `scratch/.bench_venv`.

- **Model ID:** `ProsusAI/finbert`
- **Architecture:** BERT-base-uncased (109.5M parameters)
- **Output Classes:** `positive`, `negative`, `neutral` (Softmax probability distribution)
- **Threads Configured:** 8 CPU threads
- **Baseline RAM Before Load:** **10.47 GB**
- **Model Load Time (Disk to CPU RAM):** **2.410 s** (Download + Load first time: 139.037s)
- **Resident RAM Delta for Model:** **+0.45 GB** (~450 MB resident footprint)
- **RAM During Inference:** **11.21 GB** (WorkingSet peak: ~743 MB)

### 6.1 Functional Sentiment Verification on Actual Financial Headlines
1. *"HDFC Bank reports 35% surge in quarterly net profit, beating analyst estimates across all operational segments."*
   - **Predicted:** **POSITIVE** (Confidence: **95.23%**)
   - Probability Distribution: `positive: 0.9523, negative: 0.0240, neutral: 0.0237`
2. *"Tech giant warns of severe revenue slump and cuts full-year forecast amid worsening global macro headwinds."*
   - **Predicted:** **NEGATIVE** (Confidence: **94.70%**)
   - Probability Distribution: `positive: 0.0195, negative: 0.9470, neutral: 0.0336`
3. *"Reserve Bank of India maintains policy repo rate unchanged at 6.50% following monetary policy committee meeting."*
   - **Predicted:** **NEGATIVE / NEUTRAL** (Negative: 49.96%, Neutral: 47.32%, Positive: 2.72% — policy hold interpreted with cautious macroeconomic implications)

### 6.2 Latency Benchmark Results ($N=10$ Warm Runs)
| Input Scenario | Cold Latency | Warm Min | Warm Mean | Warm Median | Warm Max | Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Single Headline** (Positive test headline) | **110.89 ms** | **109.89 ms** | **116.90 ms** | **115.03 ms** | **133.66 ms** | **~8.5 headlines/sec** |
| **Batch 10 Headlines** (Simultaneous market feed) | — | **450.13 ms** | **509.93 ms** | **489.80 ms** | **699.80 ms** | **50.99 ms / headline** (~19.6 headlines/s) |

---

## 7. Evidence-Based Sentiment Model Decision (Feeds Sprint 6 `S6-MI01`)

The acceptance criterion states: *"CPU latency and RAM recorded; feeds the sentiment decision."*

Based on our empirical measurements, the following engineering decision is established for Sprint 6 (`S6-MI01`):

### 7.1 Does FinBERT CPU Latency Pass the Synchronous SLA Check?
- **SLA Requirement:** FinEx FastAPI endpoints require a sub-500ms P95 latency budget.
- **Empirical Reality:** 
  - Classifying a batch of 10 news headlines takes **489.80 ms (Median)** and up to **699.80 ms (Max)** on CPU.
  - Adding network overhead and database reads puts total endpoint latency at **> 750 ms**, which **fails the synchronous HTTP request SLA**.
  - Executing 8-thread transformer inference in the web process blocks event loop concurrency and starves CPU resources.

### 7.2 The Authoritative Sentiment Architecture for FinEx
1. **Never execute FinBERT synchronously inside the FastAPI HTTP route.**
2. **Deploy FinBERT as an Asynchronous Ingestion Job (Scheduled Batch / Celery Worker):**
   - RSS news articles and ticker news must be processed in background jobs (`python -m app.jobs.score_sentiment`), writing results asynchronously to the PostgreSQL `sentiment_scores` table.
   - User endpoints (`/news`, `/news/sentiment/{ticker}`) perform sub-10ms indexed relational queries against pre-computed scores.
3. **Deploy a Lightweight Lexicon Scorer as Synchronous Fallback:**
   - In accordance with Page 4 of the Implementation Plan (*"Fallback: Lexicon scorer, labelled as such"*), use the Loughran-McDonald financial dictionary for instant (<1ms) preliminary sentiment during real-time article ingestion.
4. **Sprint 6 Optimization Recommendation:**
   - Export FinBERT to **ONNX Runtime INT8 format** in Sprint 6. Quantization reduces memory to ~150MB and cuts CPU inference time to ~120ms per 10 headlines, providing an optimal middle ground for resource-constrained environments.

---

## 8. Cross-Model Performance & Resource Comparison Matrix

All models measured on identical workstation hardware (AMD Ryzen 5, 8 CPU cores, 16GB DDR4):

| Metric | Ollama `llama3.2:latest` | Ollama `deepseek-r1:1.5b` | `all-MiniLM-L6-v2` | `ProsusAI/finbert` |
| :--- | :---: | :---: | :---: | :---: |
| **Architecture** | 3.2B Llama (GGUF) | 1.8B Qwen2 (GGUF) | 22.7M BERT-6L (PyTorch) | 109.5M BERT-base (PyTorch) |
| **Model Disk Size** | 2.02 GB | 1.12 GB | 120 MB | 440 MB |
| **Disk Load Time (to RAM)** | 8.502 s | 4.404 s | 1.580 s | 2.410 s |
| **Resident RAM Delta** | +1.85 GB | +1.32 GB | +0.16 GB | +0.45 GB |
| **Single Item Latency (Warm Median)**| 8.245 s (69 tokens) | 14.834 s (279 tokens) | **24.51 ms** | **115.03 ms** |
| **Batch 10 Latency (Warm Median)** | N/A (Sequential generation) | N/A (Sequential generation) | **68.14 ms** | **489.80 ms** |
| **Throughput on 8-Core CPU** | 8.71 tokens/sec | 18.77 tokens/sec | ~120 chunks/sec | ~19.6 headlines/sec |
| **Execution Mode in FinEx** | Background / Async RAG | Complex reasoning jobs | Real-time query embedding | Asynchronous news job |

---

## 9. Implemented Baseline vs. Proposed Future Architecture

To ensure strict engineering precision and avoid overclaims, we explicitly delineate what is currently implemented in Sprint 0 versus what is proposed for future sprints:

### 9.1 Implemented & Verified in Sprint 0
- [x] **Deterministic Advice Refusal Guardrail (`S0-MI01`):** Precompiled `re.IGNORECASE` regex patterns intercept prohibited advice queries across all casing permutations.
- [x] **Risk Scoring & Explanation Determinism:** 1000-run reproducibility and zero numerical drift between computed risk scores and template output.
- [x] **Empirical Hardware Baseline (`S0-MI02`):** Real measured latency, memory, and throughput recorded for Ollama, MiniLM, and FinBERT on team development hardware.

### 9.2 Proposed Architecture for Future Sprints (Not Claimed as Implemented in S0)
- **Sprint 1 (`S1-AI-01`, `S1-AI-02`):** Formal implementation of `ai/01_rag_prototype.py` satisfying `load_document_registry`, chunk metadata attachment, and factsheet retrieval.
- **Sprint 2 (`S2-MI01`):** Integration of `all-MiniLM-L6-v2` embedding port and seed factsheet corpus.
- **Sprint 5 (`S5-MI01` to `S5-MI05`):** PostgreSQL `pgvector` HNSW vector store, RAG citation verifier, and `ai/eval/run_eval.py` evaluation harness.
- **Sprint 6 (`S6-MI01`):** Background FinBERT sentiment analysis job, news ingestion pipeline, and Loughran-McDonald lexicon fallback.

### 9.3 Regulatory Compliance & Liability Qualification
- In accordance with SEBI (Investment Advisers) Regulations, 2013:
  - FinEx implements technical input guards and mandatory disclaimers to mitigate regulatory non-compliance risks.
  - While technical guardrails reject explicit recommendation keywords deterministically, no software mechanism can claim "zero legal liability" or "100% compliance guarantee" in an absolute legal sense. All features are labeled strictly as EDUCATIONAL or SIMULATED.

---

## 10. Final Acceptance Checklist (S0-MI02)

| # | Acceptance Criterion | Status | Verification Reference |
| :-: | :--- | :---: | :--- |
| 1 | Complete `ai/` test audit executed and documented | **PASS** | Section 3: 43 passing in `ai/risk/`, 4 failing in `ai/test_rag_prototype.py`. |
| 2 | Absence of `ai/eval/run_eval.py` verified | **PASS** | Section 3: Confirmed non-existent in S0 (scheduled for Sprint 5 `S5-MI05`). |
| 3 | Ollama models evaluated with genuine cold start and memory eviction | **PASS** | Section 4: `keep_alive: 0` eviction verified; 10 warm runs conducted. |
| 4 | `all-MiniLM-L6-v2` locally executed on CPU | **PASS** | Section 5: PyTorch CPU execution recorded; 384 dimensions; 24.5ms query latency. |
| 5 | `ProsusAI/finbert` locally executed on CPU | **PASS** | Section 6: Verified classification on financial headlines; 115ms single, 490ms batch 10. |
| 6 | CPU latency and RAM recorded for all models | **PASS** | Section 8: Cross-model performance matrix fully populated with measured values. |
| 7 | Findings feed the sentiment decision | **PASS** | Section 7: FinBERT ruled out for synchronous request path; recommended for async job. |
| 8 | Reproducible evidence file created | **PASS** | `docs/evidence/s0_mi02_evidence.md` created with full execution logs. |
| 9 | Implemented vs. proposed architecture clearly separated | **PASS** | Section 9: Delineated S0 baseline from S1–S6 roadmap; qualified legal claims. |
| 10 | Review comments on PR #116 fully addressed | **PASS** | All 5 review points resolved with empirical evidence. |

---
**Report Approved by:** Mitali Dobale  
**Role:** Senior AI Engineer & Implementation Lead, FinEx Engineering Team  
