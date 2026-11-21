"""
Unit tests for Sprint 0 Task S0-MI01 (BUG-01 Fix).
Verifies that prohibited financial advice keywords are compiled and evaluated with re.IGNORECASE,
ensuring strict refusal across lowercase, uppercase, and mixed-case variations, while preserving
normal educational question answering and API response contracts.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.main import create_app
from app.routers.ai_assistant import (
    COMPILED_PROHIBITED_PATTERNS,
    PROHIBITED_ADVICE_KEYWORDS,
)


@pytest.fixture(scope="module")
def client():
    app = create_app()
    token = create_access_token({"sub": "test_ai_user", "user_id": "test_ai_user"})
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
        yield test_client


class TestCompiledPatternsRegex:
    """Direct regex matching tests verifying COMPILED_PROHIBITED_PATTERNS with IGNORECASE."""

    @pytest.mark.parametrize(
        "query",
        [
            "should I buy Reliance?",
            "should i buy Reliance?",
            "should I sell my shares?",
            "should i sell my shares?",
            "SHOULD I BUY RELIANCE?",
            "SHOULD I SELL MY SHARES?",
            "Should I Buy Reliance?",
            "Should I Sell My Shares?",
            "sHoUlD i BuY Reliance?",
            "sHoUlD i SeLl my shares?",
            "which stock to buy today?",
            "WHICH STOCK TO BUY?",
            "Which Stock To Buy?",
            "can you predict tomorrow market?",
            "PREDICT TOMORROW",
            "Predict Tomorrow closing price",
            "is there any guaranteed return investment?",
            "GUARANTEED RETURN",
            "Guaranteed Return on bonds",
            "give me a hot stock tip",
            "HOT STOCK to buy now",
            "Hot Stock for intraday",
        ],
    )
    def test_prohibited_patterns_match_all_cases(self, query: str):
        """Verify that at least one compiled pattern matches prohibited phrases in any case."""
        matched = any(pattern.search(query) for pattern in COMPILED_PROHIBITED_PATTERNS)
        assert matched is True, f"Failed to match prohibited phrase: '{query}'"

    @pytest.mark.parametrize(
        "query",
        [
            "What is asset allocation and diversification?",
            "Explain the difference between risk and volatility.",
            "How does dollar-cost averaging (DCA) work?",
            "What is compound interest in retirement planning?",
            "How does inflation affect cash savings?",
            "Can you explain index funds vs mutual funds?",
        ],
    )
    def test_safe_educational_queries_do_not_match_prohibited_patterns(self, query: str):
        """Verify safe educational queries do not trigger false positive regex matches."""
        matched = any(pattern.search(query) for pattern in COMPILED_PROHIBITED_PATTERNS)
        assert matched is False, f"False positive match for safe query: '{query}'"


class TestAIRefusalAPICases:
    """Integration/API tests for /api/v1/ai/chat endpoint verifying refusal contracts."""

    @pytest.mark.parametrize(
        "query",
        [
            "should I buy Reliance?",
            "should i buy Reliance?",
            "should I sell my shares?",
            "should i sell my shares?",
        ],
    )
    def test_lowercase_refusal_cases(self, client: TestClient, query: str):
        """Verify lowercase queries are refused with REFUSAL_FINANCIAL_ADVICE."""
        resp = client.post("/api/v1/ai/chat", json={"message": query})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["intent"] == "REFUSAL_FINANCIAL_ADVICE"
        assert data["safe_fallback_used"] is True
        assert data["citations"] == []
        assert "cannot provide specific buy/sell recommendations" in data["answer_text"]
        assert "Not a licensed investment adviser" in data["limitations_disclaimer"]

    @pytest.mark.parametrize(
        "query",
        [
            "SHOULD I BUY RELIANCE?",
            "SHOULD I SELL MY SHARES?",
            "WHICH STOCK TO BUY?",
            "PREDICT TOMORROW PRICES",
            "GUARANTEED RETURN PROMISE",
            "GIVE ME A HOT STOCK",
        ],
    )
    def test_uppercase_refusal_cases(self, client: TestClient, query: str):
        """Verify uppercase queries are refused with REFUSAL_FINANCIAL_ADVICE (BUG-01 core test)."""
        resp = client.post("/api/v1/ai/chat", json={"message": query})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["intent"] == "REFUSAL_FINANCIAL_ADVICE"
        assert data["safe_fallback_used"] is True
        assert data["citations"] == []
        assert "cannot provide specific buy/sell recommendations" in data["answer_text"]

    @pytest.mark.parametrize(
        "query",
        [
            "Should I Buy Reliance?",
            "sHoUlD i BuY Reliance?",
            "Should I Sell My Shares?",
            "sHoUlD i SeLl my shares?",
            "Which Stock To Buy for long term?",
            "Predict Tomorrow closing rate",
            "Guaranteed Return options",
            "Hot Stock tips for this week",
        ],
    )
    def test_mixed_case_refusal_cases(self, client: TestClient, query: str):
        """Verify mixed-case queries are refused with REFUSAL_FINANCIAL_ADVICE."""
        resp = client.post("/api/v1/ai/chat", json={"message": query})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["intent"] == "REFUSAL_FINANCIAL_ADVICE"
        assert data["safe_fallback_used"] is True
        assert data["citations"] == []
        assert "cannot provide specific buy/sell recommendations" in data["answer_text"]

    @pytest.mark.parametrize(
        "query,expected_keyword",
        [
            ("What is asset allocation and diversification?", "allocation"),
            ("How does volatility differ from risk?", "volatility"),
            ("Explain dollar-cost averaging and compound interest", "compound"),
        ],
    )
    def test_safe_educational_queries_are_not_refused(
        self, client: TestClient, query: str, expected_keyword: str
    ):
        """Verify safe queries return CONCEPT_EDUCATION with valid curriculum citations."""
        resp = client.post("/api/v1/ai/chat", json={"message": query})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["intent"] == "CONCEPT_EDUCATION"
        assert data["safe_fallback_used"] is False
        assert len(data["citations"]) > 0
        assert data["citations"][0]["chunk_id"].startswith("chunk-edu-")
        assert "FinEx educational curriculum" in data["answer_text"]

    def test_prohibited_keywords_list_preserved(self):
        """Ensure original keywords list is preserved for backward compatibility."""
        assert len(PROHIBITED_ADVICE_KEYWORDS) >= 6
        assert r"\bshould I buy\b" in PROHIBITED_ADVICE_KEYWORDS
        assert r"\bshould I sell\b" in PROHIBITED_ADVICE_KEYWORDS
        assert len(COMPILED_PROHIBITED_PATTERNS) == len(PROHIBITED_ADVICE_KEYWORDS)
