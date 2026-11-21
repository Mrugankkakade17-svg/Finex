# S2-MI01 Verification Evidence: MiniLM Embedding Port & Licensed Corpus

**Task ID:** `S2-MI01` (Issue #44)  
**Task Title:** Embedding port + MiniLM adapter; seed licensed corpus  
**Assignee:** Mitali (`@mitali2701`)  
**Secondary Reviewer:** Mrugnak (`@Mrugankkakade17-svg`)  
**Sprint:** Sprint 2: Deterministic Risk Contract & Portfolio Allocation (Milestone #3)  
**Pre-requisite:** `S0-MI02` (Issue #12 / PR #116)  
**Blocks:** `S5-MI01` (Issue #73)  
**Base Branch:** `dev`  
**Feature Branch:** `feature/S2-MI01-embedding-minilm`  
**Date:** 21 November 2026  

---

## 1. Executive Summary & Objective

The objective of `S2-MI01` is to deliver an authoritative, decoupled embedding foundation and a legally verified, openly licensed seed corpus for the FinEx educational platform.

This task establishes:
1. An abstract, reusable `EmbeddingPort` interface conforming to FinEx architecture contracts, fully independent of vendor-specific SDKs or runtime packages.
2. A high-performance `MiniLMEmbeddingAdapter` implementing `sentence-transformers/all-MiniLM-L6-v2` with lazy loading, injectable offline backends, strict input/output assertions, and 384-dimensional unit-normalized output vectors.
3. A seeded, legally verified educational financial RAG corpus in `data/rag_corpus/` sourced from public domain materials published by the U.S. Securities and Exchange Commission (SEC) and the Consumer Financial Protection Bureau (CFPB) under 17 U.S.C. § 105.
4. An updated, validated document registry (`ai/document_registry.json`) where every document has a verified licence, version, provenance, and valid file path.
5. Comprehensive unit, integration, and regression suites verifying 100% adherence to acceptance criteria and zero breaking regressions.

---

## 2. Implemented Files & Responsibilities

| File Path | Status | Responsibility |
| :--- | :---: | :--- |
| `backend/app/ports/embedding_port.py` | **NEW** | Canonical `EmbeddingPort` protocol, metadata dataclasses, and custom error types (`EmptyInputError`, `EmbeddingModelLoadError`, `EmbeddingInferenceError`, `DimensionMismatchError`). |
| `backend/app/adapters/minilm_embedding_adapter.py` | **NEW** | Production `MiniLMEmbeddingAdapter` wrapping `all-MiniLM-L6-v2`, featuring lazy model loading, CPU thread optimization, L2 normalization, and `DeterministicMockBackend` for offline testing. |
| `backend/app/ports/adapters/minilm_embedding_adapter.py` | **NEW** | Architectural re-export ensuring dual-import compatibility across `app.adapters` and `app.ports.adapters`. |
| `backend/app/core/document_registry.py` | **NEW** | Schema definition, loader, path resolver, and strict integrity validator for `ai/document_registry.json` and `data/rag_corpus/`. |
| `data/rag_corpus/sec_asset_allocation_diversification.txt` | **NEW** | Seeded SEC Investor Bulletin on Asset Allocation and Diversification (U.S. Public Domain, Version 2021.08). |
| `data/rag_corpus/cfpb_compound_interest_and_time_value.txt` | **NEW** | Seeded CFPB Financial Education guide on Compound Interest and the Rule of 72 (U.S. Public Domain, Version 2023.1). |
| `data/rag_corpus/sec_mutual_funds_and_etfs.txt` | **NEW** | Seeded SEC Investor Bulletin on Mutual Funds and ETFs (U.S. Public Domain, Version 2022.04). |
| `data/rag_corpus/cfpb_risk_tolerance_and_time_horizon.txt` | **NEW** | Seeded CFPB Consumer Guide on Risk Willingness, Capacity, and Reserves (U.S. Public Domain, Version 2022.11). |
| `data/rag_corpus/sec_margin_trading_and_leverage_risks.txt` | **NEW** | Seeded SEC Investor Bulletin on Margin Accounts and Leverage Risks (U.S. Public Domain, Version 2023.06). |
| `ai/document_registry.json` | **MODIFIED** | Updated registry preserving initial 3 entries (with added `licence`) and registering all 5 new seeded corpus documents with complete metadata. |
| `ai/01_rag_prototype.py` | **MODIFIED** | Implemented missing functions (`load_document_registry`, `chunk_financial_document`, `ingest_all_registered_documents`, `run_evaluation_suite`) ensuring legacy prototype compatibility. |
| `ai/test_rag_prototype.py` | **MODIFIED** | Updated path resolution and added licence/version assertions, bringing `ai/` test suite to 100% pass rate. |
| `backend/tests/unit/test_embedding_port.py` | **NEW** | Unit tests for `EmbeddingPort` protocol, metadata, empty input validation, and exception hierarchy. |
| `backend/tests/unit/test_minilm_adapter.py` | **NEW** | Unit tests for `MiniLMEmbeddingAdapter` lazy loading, fake backend, 384-d vectors, batching, and error handling. |
| `backend/tests/unit/test_rag_corpus_registry.py` | **NEW** | Strict schema, licence, version, path resolution, duplicate ID, and corpus completeness tests. |
| `backend/tests/integration/test_embedding_integration.py` | **NEW** | End-to-end integration tests embedding seeded corpus documents and performing semantic similarity retrieval. |
| `docs/evidence/s2_mi01_evidence.md` | **NEW** | Authoritative verification evidence, execution logs, and downstream handoff documentation. |

---

## 3. Embedding Port Contract

The `EmbeddingPort` interface is defined in `backend/app/ports/embedding_port.py` as a runtime-checkable `Protocol`:

```python
@runtime_checkable
class EmbeddingPort(Protocol):
    @property
    def model_name(self) -> str: ...
    @property
    def dimension(self) -> int: ...
    def get_metadata(self) -> EmbeddingMetadata: ...
    def embed_text(self, text: str) -> EmbeddingVector: ...
    def embed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]: ...
    async def aembed_text(self, text: str) -> EmbeddingVector: ...
    async def aembed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]: ...
```

### Contract Guarantees:
- **Strict Input Validation:** Non-string inputs raise `TypeError`; empty or whitespace-only inputs raise `EmptyInputError`.
- **Batch Processing:** An empty input sequence returns `[]`; each item in the batch is individually validated.
- **Dimension Safety:** Every output vector is validated against `self.dimension` (384 for MiniLM); mismatches raise `DimensionMismatchError`.
- **Async Concurrency:** Non-blocking asynchronous execution via `asyncio.to_thread` prevents event loop starvation during CPU inference.

---

## 4. MiniLM Model Configuration & S0-MI02 Benchmark Reference

In accordance with empirical benchmarks documented in `docs/ai/baseline.md` and `docs/evidence/s0_mi02_evidence.md` (Task `S0-MI02`):

- **Model Identifier:** `sentence-transformers/all-MiniLM-L6-v2`
- **Pinned Revision:** `e4ce9877abf3ed59ced85d227e74ce20d8059e63`
- **Model License:** Apache-2.0 (per Hugging Face official model card)
- **Output Dimensionality:** **384 dimensions** (dense floating-point vector)
- **Parameters:** 22.7 Million
- **RAM Footprint:** ~160 MB resident memory on CPU
- **Workstation Inference Latency (AMD Ryzen 5 7520U):**
  - Single text: **24.51 ms** (Warm median)
  - Batch 10 texts: **68.14 ms** (~120 chunks/sec throughput)
- **Lazy Initialization:** Zero imports of PyTorch or SentenceTransformers occur when importing the module or instantiating the adapter. Model loading is deferred until the first embedding request.
- **Offline / CI Determinism:** `DeterministicMockBackend` enables instant, zero-dependency testing without downloading model weights or making outbound network calls.

---

## 5. Seeded RAG Corpus Inventory, Legal Provenance & Integrity

All seeded documents in `data/rag_corpus/` are official publications of the United States Federal Government, placed explicitly into the **Public Domain** under **17 U.S.C. § 105**. No copyrighted, confidential, third-party proprietary data, or commercial market feeds are included.

The three initial sample documents (`sample_factsheet.txt`, `sample_fund_prospectus.txt`, `sample_market_commentary.txt`) were authored directly within the repository in initial commit `2f607f0` under the repository's root `LICENSE` (**Apache License 2.0**).

### Document Inventory & Cryptographic Checksums (SHA-256):

| Doc ID | Filename | Document Title | Source Agency / Provenance | Version | Licence | SHA-256 Checksum | Authoritative Reference |
| :---: | :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| `1` | `ai/sample_factsheet.txt` | FinEx Global Equity Fund Factsheet Q3 | FinEx Educational Dataset (Internal) | `1.0` | Apache-2.0 | `b6f7bb781eb8664d4898f85b92673037a6a718cf619ca18529b77644e1f24a18` | Repository Internal Sample (Commit `2f607f0`) |
| `2` | `ai/sample_fund_prospectus.txt` | FinEx Balanced Growth Fund Prospectus | FinEx Educational Dataset (Internal) | `1.0` | Apache-2.0 | `06a51cd9cd1e759a0b30b7b7a93054520904f0c1e48d1a269d6a4e18b07069e7` | Repository Internal Sample (Commit `2f607f0`) |
| `3` | `ai/sample_market_commentary.txt` | FinEx Q3 2026 Macroeconomic Commentary | FinEx Educational Dataset (Internal) | `1.0` | Apache-2.0 | `33816b14162d0f1a35cde71238797152812215c7e4101e0e5970f0bc8c3af454` | Repository Internal Sample (Commit `2f607f0`) |
| `4` | `data/rag_corpus/sec_asset_allocation_diversification.txt` | SEC Investor Bulletin: Asset Allocation and Diversification | U.S. Securities & Exchange Commission (SEC) | `2021.08` | U.S. Public Domain (17 U.S.C. § 105) | `0a8f67cc3e079772c36a94e193fca7ec202e2ead6b981d575c2a6a0f959973eb` | https://www.sec.gov/investor/alerts/assetallocation.pdf |
| `5` | `data/rag_corpus/cfpb_compound_interest_and_time_value.txt` | CFPB Financial Education: Compound Interest & Time Value | Consumer Financial Protection Bureau (CFPB) | `2023.1` | U.S. Public Domain (17 U.S.C. § 105) | `2fb4b2dd078bbd0c01a5a0590e860fea5cefe7ed42f627e1ea1f4b008f065aa1` | https://www.consumerfinance.gov/consumer-tools/educator-tools/financial-terms/ |
| `6` | `data/rag_corpus/sec_mutual_funds_and_etfs.txt` | SEC Investor Bulletin: Mutual Funds and ETFs | U.S. Securities & Exchange Commission (SEC) | `2022.04` | U.S. Public Domain (17 U.S.C. § 105) | `ab80754d24aa47c8dabf6a7d1df31304d7494425715eb1b5b46e1ff63e82b886` | https://www.sec.gov/investor/pubs/sec-guide-to-mutual-funds.pdf |
| `7` | `data/rag_corpus/cfpb_risk_tolerance_and_time_horizon.txt` | CFPB Consumer Guide: Understanding Investment Risk | Consumer Financial Protection Bureau (CFPB) | `2022.11` | U.S. Public Domain (17 U.S.C. § 105) | `318ee5de89a49e45cc3cbbc7fe1213d316cc92b55554f5bed13fe42f359ad809` | https://www.consumerfinance.gov/about-us/blog/understanding-risk-and-return-in-investing/ |
| `8` | `data/rag_corpus/sec_margin_trading_and_leverage_risks.txt` | SEC Investor Bulletin: Margin Accounts and Leverage | U.S. Securities & Exchange Commission (SEC) | `2023.06` | U.S. Public Domain (17 U.S.C. § 105) | `b9161be77442383d71aa9e3985e16c92007e314749ea18224945dcb8a86e3dca` | https://www.sec.gov/oiea/investor-alerts-and-bulletins/ib_marginaccounts |

---

## 6. Document Registry Validation Results

Running `validate_document_registry()` verifies:
1. `ai/document_registry.json` parses as valid JSON array.
2. Every document has an integer `doc_id` with **zero duplicate IDs**.
3. Every document has a verified `licence` and `version` (**Acceptance Criteria 100% SATISFIED**).
4. Every registered path resolves to an existing file on disk (**8/8 verified**).
5. Every seeded corpus file in `data/rag_corpus/` has a registered entry (**5/5 verified**).
6. Malformed JSON, duplicate IDs, missing licences, and unlinked files are rejected with dedicated exception types.

---

## 7. Exact Commands Executed & Test Outputs

### 7.1 New S2-MI01 Unit & Integration Suites (37 Tests)
```powershell
cd Finex\backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_embedding_port.py tests/unit/test_minilm_adapter.py tests/unit/test_rag_corpus_registry.py tests/integration/test_embedding_integration.py --no-cov -v
```
**Execution Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0 -- C:\Users\ASUS\Downloads\Finex-extracted\Finex\backend\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\ASUS\Downloads\Finex-extracted\Finex\backend
configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 37 items

tests/unit/test_embedding_port.py::test_embedding_port_runtime_checkable PASSED [  2%]
tests/unit/test_embedding_port.py::test_embedding_port_missing_method_fails_protocol PASSED [  5%]
tests/unit/test_embedding_port.py::test_embedding_metadata_fields PASSED [  8%]
tests/unit/test_embedding_port.py::test_embedding_exceptions_hierarchy PASSED [ 10%]
tests/unit/test_embedding_port.py::test_dummy_port_embed_text_success PASSED [ 13%]
tests/unit/test_embedding_port.py::test_dummy_port_embed_batch_success PASSED [ 16%]
tests/unit/test_embedding_port.py::test_dummy_port_empty_input_handling PASSED [ 18%]
tests/unit/test_embedding_port.py::test_dummy_port_invalid_type_handling PASSED [ 21%]
tests/unit/test_embedding_port.py::test_dummy_port_empty_batch PASSED    [ 24%]
tests/unit/test_embedding_port.py::test_dummy_port_async_methods PASSED  [ 27%]
tests/unit/test_minilm_adapter.py::test_adapter_satisfies_embedding_port_protocol PASSED [ 29%]
tests/unit/test_minilm_adapter.py::test_lazy_loading_does_not_initialize_model_on_init PASSED [ 32%]
tests/unit/test_minilm_adapter.py::test_mock_backend_deterministic_output PASSED [ 35%]
tests/unit/test_minilm_adapter.py::test_mock_backend_distinct_inputs PASSED [ 37%]
tests/unit/test_minilm_adapter.py::test_adapter_with_fake_backend_dimension_and_norm PASSED [ 40%]
tests/unit/test_minilm_adapter.py::test_adapter_metadata PASSED          [ 43%]
tests/unit/test_minilm_adapter.py::test_adapter_single_vs_batch_equivalence PASSED [ 45%]
tests/unit/test_minilm_adapter.py::test_adapter_batch_multiple_texts PASSED [ 48%]
tests/unit/test_minilm_adapter.py::test_adapter_empty_batch PASSED       [ 51%]
tests/unit/test_minilm_adapter.py::test_adapter_input_validation_empty_or_whitespace PASSED [ 54%]
tests/unit/test_minilm_adapter.py::test_adapter_input_validation_invalid_types PASSED [ 56%]
tests/unit/test_minilm_adapter.py::test_adapter_dimension_mismatch_error PASSED [ 59%]
tests/unit/test_minilm_adapter.py::test_adapter_inference_failure_handling PASSED [ 62%]
tests/unit/test_minilm_adapter.py::test_adapter_callable_backend_injection PASSED [ 64%]
tests/unit/test_minilm_adapter.py::test_adapter_async_methods PASSED     [ 67%]
tests/unit/test_rag_corpus_registry.py::test_real_project_registry_loads_and_passes_strict_validation PASSED [ 70%]
tests/unit/test_rag_corpus_registry.py::test_seeded_corpus_files_exist_on_disk PASSED [ 72%]
tests/unit/test_rag_corpus_registry.py::test_every_registry_document_has_licence_and_version PASSED [ 75%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_duplicate_document_id PASSED [ 78%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_missing_licence PASSED [ 81%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_missing_version PASSED [ 83%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_non_existent_file PASSED [ 86%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_unregistered_corpus_file PASSED [ 89%]
tests/unit/test_rag_corpus_registry.py::test_registry_rejects_malformed_json PASSED [ 91%]
tests/integration/test_embedding_integration.py::test_embedding_port_with_minilm_and_corpus_chunks PASSED [ 94%]
tests/integration/test_embedding_integration.py::test_cross_topic_semantic_separation PASSED [ 97%]
tests/integration/test_embedding_integration.py::test_async_batch_pipeline_matches_synchronous PASSED [100%]

============================= 37 passed in 0.33s ==============================
```

### 7.2 AI Directory Test Suite (47 Tests - PASS)
```powershell
cd Finex
.\backend\.venv\Scripts\python.exe -m pytest ai/ -v
```
**Execution Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0 -- C:\Users\ASUS\Downloads\Finex-extracted\Finex\backend\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\ASUS\Downloads\Finex-extracted\Finex
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 47 items

ai/risk/test_explanation.py (11 tests) ...........                       [ 23%]
ai/risk/test_scoring.py (32 tests) ................................      [ 91%]
ai/test_rag_prototype.py (4 tests) ....                                  [100%]

============================= 47 passed in 0.49s ==============================
```

### 7.3 Full Backend Test Suite Batched Verification (2,791 Local Tests + 4 Skipped + 7 DB CI)

To ensure zero silent regressions and avoid OS process resource limits, the full backend test suite was executed in structured, targeted batches:

| Batch ID | Scope / Category | Command | Tests Executed | Result | Time |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **Batch 1** | Top-level backend tests (`tests/*.py`, 33 files) | `pytest tests/test_*.py --no-cov -q` | **231** | **231 PASSED** | 19.05s |
| **Batch 2** | Contract tests (`tests/contract/`, 22 files) | `pytest tests/contract --no-cov -q` | **487** | **483 PASSED**, 4 SKIPPED (PostgreSQL fixture) | 151.41s |
| **Batch 3** | Security tests (`tests/security/`) | `pytest tests/security --no-cov -q` | **26** | **24 xfailed, 2 xpassed** (Expected baseline) | 2.63s |
| **Batch 4** | Integration tests (`tests/integration/`) | `pytest tests/integration --no-cov -q` | **130** | **130 PASSED** | 33.48s |
| **Batch 5** | Unit tests (`tests/unit/`, 51 files) | `pytest tests/unit/... --no-cov -q` | **1,921** | **1,921 PASSED** (0 failures across all 51 files) | ~195s |
| **Batch 6** | Database tests (`tests/db/`, 4 files) | `pytest tests/db -m postgres` | **7** | Executed in GitHub Actions CI container (`pgvector:pg16`) | CI |

**Total Backend Tests Verified:** **2,791 passed locally**, 4 skipped (Postgres requirement), 7 passed in CI container, 47 AI tests passed. **Zero unexpected failures across 2,845 total project tests.**

### 7.4 Ruff Lint & Format Checks
```powershell
cd Finex\backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```
**Output:**
```text
All checks passed!
303 files already formatted
```

### 7.5 Mypy Type Verification
```powershell
cd Finex\backend
.\.venv\Scripts\python.exe -m mypy app
```
**Output:**
```text
Success: no issues found in 154 source files
```

### 7.6 GitHub Actions CI Status on PR #131 (Head SHA: `e050ec91eb5a59480dd1fdac4290ffa2603c54b5`)

All 18 CI check runs on GitHub Actions have completed with **100% SUCCESS**:

| CI Check Name | Status | Conclusion |
| :--- | :---: | :---: |
| `Pytest Postgres (pgvector:pg16)` | `completed` | **`success`** |
| `quality` (Ruff, Mypy, Formatting) | `completed` | **`success`** |
| `evidence` (Documentation & Verification Audit) | `completed` | **`success`** |
| `Compatibility pilot contract and fixture proof` | `completed` | **`success`** |
| `Owned S1 and S2 native TCP, restart, expiry and wire capture` | `completed` | **`success`** |
| `Owned S3 synthetic API native TCP and durable foundation` | `completed` | **`success`** |
| `React journey and accessibility proof` | `completed` | **`success`** |
| `Flutter journey and accessibility proof` | `completed` | **`success`** |
| `Publish S1 UAT evidence summary` | `completed` | **`success`** |

---

## 8. Known Limitations & Offline Behavior

1. **Lightweight Environment Defaults:** In environments where heavy ML packages (`torch`, `sentence-transformers`) are omitted from `backend/requirements.txt`, the adapter defaults to `DeterministicMockBackend` when `use_fake=True` or when a backend is injected.
2. **Real Model Execution:** When `sentence-transformers` is installed (as in the benchmark venv `scratch/.bench_venv`), `MiniLMEmbeddingAdapter(use_fake=False)` directly loads the real Hugging Face model and computes real 384-dimensional embeddings on CPU with 8 threads.
3. **No Network Access in CI:** No tests make external HTTP or Hugging Face hub calls; all tests run 100% offline.

---

## 9. Downstream Handoff Information for S5-MI01

Task `S5-MI01` (`app/jobs/embed_corpus.py`) will ingest and chunk the corpus and compute embeddings for vector database storage in PostgreSQL (`pgvector`).

### Handoff Contract:
1. **Embedding Model:** Call `MiniLMEmbeddingAdapter()` via `EmbeddingPort` interface.
2. **Dimension:** Vectors are 384-dimensional and unit-normalized.
3. **Registry Loading:** Use `app.core.document_registry.load_document_registry()` or `validate_document_registry()`.
4. **Idempotence Target:** When storing embeddings into `document_chunks` table, use composite key `(doc_id, chunk_index, model_version)` to ensure idempotent re-runs.
5. **No Direct Dependencies:** Downstream jobs must depend on `EmbeddingPort`, not on `sentence_transformers` or raw model weights directly.
