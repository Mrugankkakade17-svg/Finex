"""Unit tests for offline Fake LLM evaluation harness (S1-MI01).

Verifies the Done-when criterion: 'Eval runs with a fake LLM, no network.'
Ensures:
- Evaluation harness executes successfully with --fake-llm.
- Network calls are strictly blocked during execution.
- 0 false positives (safe queries incorrectly refused).
- 0 false negatives (prohibited advice queries bypassing refusal).
- 100% precision, recall, and accuracy across all test cases.
"""

import importlib.util
import socket
from pathlib import Path

import pytest

# Locate repo root and eval files
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent if (BACKEND_DIR.name == "backend") else BACKEND_DIR
if (BACKEND_DIR / "ai").is_dir():
    REPO_ROOT = BACKEND_DIR
elif (BACKEND_DIR.parent / "ai").is_dir():
    REPO_ROOT = BACKEND_DIR.parent

RUN_EVAL_PATH = REPO_ROOT / "ai" / "eval" / "run_eval.py"
CASES_PATH = REPO_ROOT / "ai" / "eval" / "refusal_cases.jsonl"

spec = importlib.util.spec_from_file_location("ai_eval_run_eval", str(RUN_EVAL_PATH))
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load run_eval module from {RUN_EVAL_PATH}")
run_eval_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval_mod)

NetworkBlockedError = run_eval_mod.NetworkBlockedError
offline_network_guard = run_eval_mod.offline_network_guard
load_test_cases = run_eval_mod.load_test_cases
run_evaluation = run_eval_mod.run_evaluation


class TestAIEvalHarness:
    """Verifies the offline evaluation harness and safety conformance."""

    @pytest.fixture
    def cases_file(self) -> Path:
        assert CASES_PATH.is_file(), f"Missing refusal cases file at {CASES_PATH}"
        return CASES_PATH

    def test_refusal_cases_count_and_schema(self, cases_file: Path):
        cases = load_test_cases(cases_file)
        assert len(cases) >= 30, f"Expected at least 30 test cases, found {len(cases)}"

        categories = set()
        refusal_count = 0
        safe_count = 0

        for case in cases:
            assert "id" in case
            assert "category" in case
            assert "query" in case
            assert "expected_intent" in case
            assert "should_refuse" in case
            assert isinstance(case["should_refuse"], bool)

            categories.add(case["category"])
            if case["should_refuse"]:
                refusal_count += 1
                assert case["expected_intent"] == "REFUSAL_FINANCIAL_ADVICE"
            else:
                safe_count += 1
                assert case["expected_intent"] == "CONCEPT_EDUCATION"

        # Check category diversity
        assert refusal_count >= 20, "Expected robust refusal cases"
        assert safe_count >= 5, "Expected safe educational control cases"
        assert len(categories) >= 5, "Expected diverse category coverage"

    def test_offline_eval_run_passes_with_zero_network(self, cases_file: Path):
        """Execute evaluation harness with fake LLM and verify 100% metrics."""
        exit_code, metrics = run_evaluation(cases_file, use_fake_llm=True)

        assert exit_code == 0
        assert metrics["total_cases"] >= 30
        assert metrics["failed"] == 0
        assert metrics["false_positives"] == 0
        assert metrics["false_negatives"] == 0
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["accuracy"] == 1.0
        assert metrics["network_calls"] == 0

    def test_network_blocker_raises_on_socket_connect_attempt(self):
        """Verify that socket connection attempts raise NetworkBlockedError in guard."""
        with offline_network_guard():
            s = socket.socket()
            with pytest.raises(NetworkBlockedError):
                s.connect(("127.0.0.1", 80))
            s.close()
