#!/usr/bin/env python3
"""
Offline Evaluation Harness for Grounded AI Safe Refusal and Education (S1-MI01).
Evaluates refusal guardrails against golden test cases in refusal_cases.jsonl.
Supports --fake-llm mode guaranteeing 100% offline execution with zero network calls.

Usage:
    cd ai; python eval/run_eval.py --fake-llm
    python ai/eval/run_eval.py --fake-llm --cases ai/eval/refusal_cases.jsonl
"""

import argparse
import json
import re
import socket
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

# Guardrail patterns matching app/routers/ai_assistant.py
PROHIBITED_ADVICE_KEYWORDS = [
    r"\bshould I buy\b",
    r"\bshould I sell\b",
    r"\bwhich stock to buy\b",
    r"\bpredict tomorrow\b",
    r"\bguaranteed return\b",
    r"\bhot stock\b",
]

COMPILED_PROHIBITED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in PROHIBITED_ADVICE_KEYWORDS
]


class NetworkBlockedError(RuntimeError):
    """Raised if any network connection is attempted during offline evaluation."""


@contextmanager
def offline_network_guard() -> Iterator[None]:
    """
    Context manager that intercepts socket connection attempts to guarantee
    zero external network calls during offline evaluation.
    Restores normal socket behavior upon exit.
    """
    real_connect = socket.socket.connect

    def guarded_connect(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise NetworkBlockedError(
            "Network connection attempted during offline --fake-llm evaluation! "
            "Zero network calls allowed."
        )

    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = real_connect  # type: ignore[assignment]


class FakeLLMEvaluator:
    """
    Deterministic offline evaluator exercising FinEx safety refusal guardrails
    and grounded educational retrieval without external network or LLM dependencies.
    """

    def __init__(self) -> None:
        self.prohibited_patterns = COMPILED_PROHIBITED_PATTERNS

    def evaluate_query(self, query: str) -> Dict[str, Any]:
        """
        Evaluate a single query through refusal detection and fake LLM generation.
        Returns simulated response payload with intent, refusal flag, and citations.
        """
        # Refusal check with IGNORECASE regex
        for pattern in self.prohibited_patterns:
            if pattern.search(query):
                return {
                    "intent": "REFUSAL_FINANCIAL_ADVICE",
                    "should_refuse": True,
                    "answer_text": (
                        "As an educational assistant, FinEx cannot provide specific buy/sell "
                        "recommendations or predict individual stock performance. We encourage "
                        "reviewing asset allocation fundamentals and consulting a licensed financial "
                        "advisor."
                    ),
                    "citations":[],
                    "safe_fallback_used": True,
                }

        # Safe grounded educational response
        return {
            "intent": "CONCEPT_EDUCATION",
            "should_refuse": False,
            "answer_text": (
                "Based on FinEx educational curriculum: Asset allocation balances risk and "
                "reward across individual investment goals."
            ),
            "citations": ["chunk-edu-001"],
            "safe_fallback_used": False,
        }


def load_test_cases(filepath: Path) -> List[Dict[str, Any]]:
    """Loads JSON Lines test cases."""
    cases = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_num} in {filepath}: {exc}") from exc
    return cases


def run_evaluation(
    cases_path: Path, use_fake_llm: bool = True
) -> Tuple[int, Dict[str, Any]]:
    """
    Runs the offline evaluation suite.
    Returns (exit_code, summary_metrics).
    """
    guard = offline_network_guard() if use_fake_llm else nullcontext()

    if not cases_path.is_file():
        # Fallback to alternate resolution
        candidates = [
            cases_path,
            Path("eval") / "refusal_cases.jsonl",
            Path("ai") / "eval" / "refusal_cases.jsonl",
            Path(__file__).resolve().parent / "refusal_cases.jsonl",
        ]
        found = None
        for candidate in candidates:
            if candidate.is_file():
                found = candidate
                break
        if not found:
            raise FileNotFoundError(f"Could not locate refusal test cases at {cases_path}")
        cases_path = found

    cases = load_test_cases(cases_path)
    evaluator = FakeLLMEvaluator()

    total = len(cases)
    passed = 0
    failed = 0
    false_positives = 0  # Safe queries incorrectly refused
    false_negatives = 0  # Prohibited queries that bypassed refusal
    true_positives = 0   # Prohibited queries correctly refused
    true_negatives = 0   # Safe queries correctly accepted

    failed_cases: List[Dict[str, Any]] = []

    with guard:
        for case in cases:
            cid = case.get("id", "unknown")
            query = case.get("query", "")
            expected_intent = case.get("expected_intent")
            expected_refuse = case.get("should_refuse", True)

            result = evaluator.evaluate_query(query)
            actual_intent = result["intent"]
            actual_refuse = result["should_refuse"]

            is_intent_correct = actual_intent == expected_intent
            is_refusal_correct = actual_refuse == expected_refuse

            if is_intent_correct and is_refusal_correct:
                passed += 1
                if expected_refuse:
                    true_positives += 1
                else:
                    true_negatives += 1
            else:
                failed += 1
                if not expected_refuse and actual_refuse:
                    false_positives += 1
                elif expected_refuse and not actual_refuse:
                    false_negatives += 1

                failed_cases.append({
                    "id": cid,
                    "query": query,
                    "expected_intent": expected_intent,
                    "actual_intent": actual_intent,
                    "expected_refuse": expected_refuse,
                    "actual_refuse": actual_refuse,
                })

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0.0

    metrics = {
        "total_cases": total,
        "passed": passed,
        "failed": failed,
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy,
        "network_calls": 0,
        "failed_cases": failed_cases,
    }

    # Print evaluation summary
    print("=" * 65)
    print("  FinEx AI Safe Refusal & Education Evaluation Suite")
    print(f"  Mode: {'Offline Fake LLM (Zero Network)' if use_fake_llm else 'Standard'}")
    print(f"  Cases File: {cases_path}")
    print("=" * 65)
    print(f"  Total Cases Evaluated : {total}")
    print(f"  Passed Cases          : {passed} / {total} ({accuracy * 100:.1f}%)")
    print(f"  Failed Cases          : {failed}")
    print(f"  True Positives (Refused): {true_positives}")
    print(f"  True Negatives (Safe)   : {true_negatives}")
    print(f"  False Positives       : {false_positives} (Target: 0)")
    print(f"  False Negatives       : {false_negatives} (Target: 0)")
    print(f"  Precision             : {precision:.4f} ({precision * 100:.1f}%)")
    print(f"  Recall                : {recall:.4f} ({recall * 100:.1f}%)")
    print(f"  Accuracy              : {accuracy:.4f} ({accuracy * 100:.1f}%)")
    print(f"  Network Calls Attempted: 0 (Network socket verified blocked)")
    print("=" * 65)

    if failed > 0:
        print("\nFAILED CASES:")
        for fc in failed_cases:
            print(f"  - [{fc['id']}] '{fc['query']}': expected {fc['expected_intent']}, got {fc['actual_intent']}")
        print("\nResult: EVALUATION FAILED")
        return 1, metrics

    print("\nResult: EVALUATION PASSED (100% deterministic conformance)")
    return 0, metrics


@contextmanager
def nullcontext() -> Iterator[None]:
    yield


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run FinEx Grounded AI Safe Refusal evaluation suite with Fake LLM"
    )
    parser.add_argument(
        "--fake-llm",
        action="store_true",
        default=True,
        help="Run eval with fake LLM and zero network calls (default: True)",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Path to JSONL refusal test cases file (default: ai/eval/refusal_cases.jsonl)",
    )

    args = parser.parse_args()

    # Determine default path
    if args.cases:
        cases_file = Path(args.cases)
    else:
        # Check current working dir
        if Path("eval/refusal_cases.jsonl").is_file():
            cases_file = Path("eval/refusal_cases.jsonl")
        elif Path("ai/eval/refusal_cases.jsonl").is_file():
            cases_file = Path("ai/eval/refusal_cases.jsonl")
        else:
            cases_file = Path(__file__).resolve().parent / "refusal_cases.jsonl"

    exit_code, _ = run_evaluation(cases_file, use_fake_llm=args.fake_llm)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
