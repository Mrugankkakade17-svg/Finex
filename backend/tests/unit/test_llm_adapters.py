"""
test_llm_adapters.py

Comprehensive unit and contract test suite for FinEx LLM provider adapters:
- Ollama local adapter (primary)
- Free hosted fallback adapter (Google Gemini gemini-3.5-flash-lite)
- Deterministic offline fallback adapter (tertiary)
- Resilient composite provider with outage resilience cascade
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.llm import (
    CompositeLLMProvider,
    DeterministicFallbackAdapter,
    HostedLLMAdapter,
    LLMProvider,
    OllamaLLMAdapter,
    ProhibitedContentError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaExceededError,
    ProviderResponseError,
    ProviderTimeoutError,
    SchemaValidationError,
    SchemaValidator,
    get_llm_provider,
)
from app.config.settings import Settings
from app.ports.llm_provider import LLMRequest, LLMResponse

# ==============================================================================
# 1. Protocol Conformance Tests
# ==============================================================================


def test_ollama_adapter_satisfies_protocol():
    adapter = OllamaLLMAdapter()
    assert isinstance(adapter, LLMProvider)


def test_hosted_adapter_satisfies_protocol():
    adapter = HostedLLMAdapter(api_key="mock_key")
    assert isinstance(adapter, LLMProvider)


def test_deterministic_adapter_satisfies_protocol():
    adapter = DeterministicFallbackAdapter()
    assert isinstance(adapter, LLMProvider)


def test_composite_provider_satisfies_protocol():
    provider = CompositeLLMProvider()
    assert isinstance(provider, LLMProvider)


# ==============================================================================
# 2. SchemaValidator & Compliance Guardrail Tests
# ==============================================================================


def test_schema_validator_clean_json_markdown():
    payload = json.dumps(
        {"intent": "CONCEPT_EDUCATION", "answer_text": "Hi", "limitations_disclaimer": "None"}
    )
    wrapped = f"```json\n{payload}\n```"
    cleaned = SchemaValidator.clean_json_text(wrapped)
    assert cleaned.startswith("{")
    assert cleaned.endswith("}")


def test_schema_validator_valid_chat_schema():
    data = {
        "intent": "CONCEPT_EDUCATION",
        "answer_text": "Diversification reduces unsystematic risk.",
        "limitations_disclaimer": "Educational use only.",
    }
    validated = SchemaValidator.parse_and_validate(data, "sprint6_ai_chat")
    assert validated["intent"] == "CONCEPT_EDUCATION"


def test_schema_validator_missing_required_fields_raises_error():
    data = {"intent": "CONCEPT_EDUCATION"}
    with pytest.raises(SchemaValidationError) as exc:
        SchemaValidator.parse_and_validate(data, "sprint6_ai_chat")
    assert "missing required non-empty fields" in str(exc.value)


def test_schema_validator_prohibited_guarantee_raises_error():
    data = {
        "intent": "CONCEPT_EDUCATION",
        "answer_text": "This portfolio gives you a guaranteed return of 15% annually.",
        "limitations_disclaimer": "Educational only.",
    }
    with pytest.raises(ProhibitedContentError) as exc:
        SchemaValidator.parse_and_validate(data, "sprint6_ai_chat")
    assert "prohibited phrase" in str(exc.value).lower()


def test_schema_validator_prohibited_stock_tip_raises_error():
    data = {
        "intent": "CONCEPT_EDUCATION",
        "answer_text": "You should definitely buy this stock now.",
        "limitations_disclaimer": "Educational only.",
    }
    with pytest.raises(ProhibitedContentError):
        SchemaValidator.parse_and_validate(data, "sprint6_ai_chat")


def test_schema_validator_valid_risk_explanation_schema():
    data = {
        "summary": "Moderate risk profile.",
        "willingness_explanation": "Willing to accept moderate drawdown.",
        "capacity_explanation": "Adequate liquid emergency reserves.",
        "alignment_analysis": "Willingness and capacity are in harmony.",
    }
    validated = SchemaValidator.parse_and_validate(data, "s2_risk_explanation")
    assert validated["summary"] == "Moderate risk profile."


# ==============================================================================
# 3. OllamaLLMAdapter Unit Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ollama_adapter_chat_success():
    chat_content = json.dumps(
        {
            "intent": "CONCEPT_EDUCATION",
            "answer_text": "Asset allocation spreads capital across asset classes.",
            "limitations_disclaimer": "Educational prototype only.",
        }
    )
    mock_response = httpx.Response(
        200,
        json={"message": {"content": chat_content}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )

    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client, model_name="llama3.2:1b")
        req = LLMRequest(
            prompt_id="chat_edu",
            prompt_version="v1",
            context={"query": "What is asset allocation?", "citations": ["chunk-edu-001"]},
            output_schema_ref="sprint6_ai_chat",
        )
        res = await adapter.generate(req)

        assert res.model == "llama3.2:1b"
        assert res.fallback_used is False
        assert res.citations == ["chunk-edu-001"]
        assert res.output["intent"] == "CONCEPT_EDUCATION"


@pytest.mark.asyncio
async def test_ollama_adapter_legacy_generate_fallback_on_404():
    gen_content = json.dumps(
        {
            "intent": "CONCEPT_EDUCATION",
            "answer_text": "Legacy generate response.",
            "limitations_disclaimer": "Educational only.",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/chat":
            return httpx.Response(404, request=request)
        return httpx.Response(200, json={"response": gen_content}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client)
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={"query": "Diversification"},
            output_schema_ref="sprint6_ai_chat",
        )
        res = await adapter.generate(req)
        assert res.fallback_used is False
        assert res.output["answer_text"] == "Legacy generate response."


@pytest.mark.asyncio
async def test_ollama_adapter_connection_error_raises_provider_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by daemon", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client)
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderConnectionError) as exc:
            await adapter.generate(req)
        assert "Ollama daemon unreachable" in str(exc.value)


@pytest.mark.asyncio
async def test_ollama_adapter_timeout_raises_provider_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Ollama read timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client, timeout_seconds=5.0)
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderTimeoutError) as exc:
            await adapter.generate(req)
        assert "timed out" in str(exc.value)


@pytest.mark.asyncio
async def test_ollama_adapter_500_raises_provider_response_error():
    mock_response = httpx.Response(
        500,
        text="Internal Model Error",
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client)
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderResponseError) as exc:
            await adapter.generate(req)
        assert "HTTP 500" in str(exc.value)


@pytest.mark.asyncio
async def test_ollama_adapter_malformed_json_raises_schema_validation_error():
    mock_response = httpx.Response(
        200,
        json={"message": {"content": "not-valid-json-response"}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client)
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(SchemaValidationError):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_ollama_is_quota_available_check():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.16"}, request=request)
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OllamaLLMAdapter(http_client=client)
        assert await adapter.is_quota_available() is True


# ==============================================================================
# ==============================================================================
# 4. HostedLLMAdapter Unit Tests (Google Gemini API & Privacy Boundary)
# ==============================================================================


@pytest.mark.asyncio
async def test_hosted_gemini_adapter_success():
    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "intent": "CONCEPT_EDUCATION",
                                    "answer_text": "Gemini hosted educational answer.",
                                    "limitations_disclaimer": "Educational only.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    captured_requests: list[httpx.Request] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_requests.append(req)
        return httpx.Response(200, json=gemini_payload, request=req)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-gemini-auth-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test_gemini",
            prompt_version="v1",
            context={"query": "Test Gemini"},
            output_schema_ref="sprint6_ai_chat",
        )
        res = await adapter.generate(req)
        assert res.model == "gemini-3.5-flash-lite"
        assert res.fallback_used is True
        assert res.output["answer_text"] == "Gemini hosted educational answer."

        # Verify header-based authentication and zero key in URL
        assert len(captured_requests) == 1
        sent_req = captured_requests[0]
        assert sent_req.headers.get("x-goog-api-key") == "mock-gemini-auth-token"
        assert "key=" not in str(sent_req.url)
        assert "gemini-3.5-flash-lite" in str(sent_req.url)


@pytest.mark.asyncio
async def test_hosted_adapter_privacy_context_sanitization():
    """Verify that financial details, balances, and PII are stripped before transmission."""
    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "intent": "CONCEPT_EDUCATION",
                                    "answer_text": "Safe educational response.",
                                    "limitations_disclaimer": "Educational only.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    captured_body: list[bytes] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_body.append(req.content)
        return httpx.Response(200, json=gemini_payload, request=req)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-gemini-auth-token",
            http_client=client,
        )
        # Context contains sensitive financial and personal data
        req = LLMRequest(
            prompt_id="privacy_audit_check",
            prompt_version="v1",
            context={
                "user_id": "usr_confidential_999",
                "email": "user@example.com",
                "pan": "ABCDE1234F",
                "account_id": "acc_private_888",
                "balance": 250000.50,
                "transactions": [{"id": 1, "amount": 1000}],
                "portfolio_value": 1500000.0,
                "query": "Explain asset diversification principles",
                "topic": "Asset Allocation",
            },
            output_schema_ref="sprint6_ai_chat",
        )
        res = await adapter.generate(req)
        assert res.fallback_used is True

        assert len(captured_body) == 1
        payload_str = captured_body[0].decode("utf-8")

        # Assert all sensitive financial fields and identifiers were stripped
        assert "usr_confidential_999" not in payload_str
        assert "user_id" not in payload_str
        assert "acc_private_888" not in payload_str
        assert "account_id" not in payload_str
        assert "250000.5" not in payload_str
        assert "balance" not in payload_str
        assert "portfolio_value" not in payload_str
        assert "transactions" not in payload_str

        # Assert allowed educational context was preserved
        assert "Explain asset diversification principles" in payload_str
        assert "Asset Allocation" in payload_str


@pytest.mark.asyncio
async def test_hosted_adapter_privacy_query_pii_masking():
    """Verify that PII patterns inside user queries are masked before external transmission."""
    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "intent": "CONCEPT_EDUCATION",
                                    "answer_text": "Sanitized response.",
                                    "limitations_disclaimer": "Educational only.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    captured_body: list[bytes] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_body.append(req.content)
        return httpx.Response(200, json=gemini_payload, request=req)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-gemini-auth-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="query_pii_check",
            prompt_version="v1",
            context={
                "query": (
                    "My email is confidential@fintech.org, my PAN is ABCDE1234F, "
                    "account is 98765432101234, and balance is Rs 50,000. How to save?"
                )
            },
            output_schema_ref="sprint6_ai_chat",
        )
        await adapter.generate(req)
        payload_str = captured_body[0].decode("utf-8")

        assert "confidential@fintech.org" not in payload_str
        assert "ABCDE1234F" not in payload_str
        assert "98765432101234" not in payload_str
        assert "50,000" not in payload_str
        assert "[REDACTED_EMAIL]" in payload_str
        assert "[REDACTED_PAN]" in payload_str
        assert "[REDACTED_IDENTIFIER]" in payload_str
        assert "[REDACTED_AMOUNT]" in payload_str


@pytest.mark.asyncio
async def test_hosted_adapter_404_model_not_found():
    mock_response = httpx.Response(
        404,
        text="Model gemini-3.5-flash-lite not found",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-valid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderResponseError, match="HTTP 404"):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_hosted_adapter_500_server_error():
    mock_response = httpx.Response(
        500,
        text="Internal Server Error",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-valid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderResponseError, match="HTTP 500"):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_hosted_adapter_timeout_error():
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out", request=req)

    transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-valid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderTimeoutError):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_hosted_adapter_connection_error():
    def connect_error_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to establish connection", request=req)

    transport = httpx.MockTransport(connect_error_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-valid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderConnectionError):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_hosted_adapter_missing_api_key_raises_auth_error():
    adapter = HostedLLMAdapter(provider_type="gemini", api_key="")
    req = LLMRequest(
        prompt_id="test",
        prompt_version="v1",
        context={},
        output_schema_ref="sprint6_ai_chat",
    )
    with pytest.raises(ProviderAuthenticationError):
        await adapter.generate(req)
    assert await adapter.is_quota_available() is False


@pytest.mark.asyncio
async def test_hosted_adapter_429_rate_limit_raises_quota_error():
    mock_response = httpx.Response(
        429,
        text="Rate limit exceeded",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-valid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderQuotaExceededError):
            await adapter.generate(req)


@pytest.mark.asyncio
async def test_hosted_adapter_401_invalid_key_raises_auth_error():
    mock_response = httpx.Response(
        401,
        text="API Key Invalid",
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )
    transport = httpx.MockTransport(lambda req: mock_response)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = HostedLLMAdapter(
            provider_type="gemini",
            api_key="mock-invalid-token",
            http_client=client,
        )
        req = LLMRequest(
            prompt_id="test",
            prompt_version="v1",
            context={},
            output_schema_ref="sprint6_ai_chat",
        )
        with pytest.raises(ProviderAuthenticationError):
            await adapter.generate(req)


# ==============================================================================
# 5. DeterministicFallbackAdapter Unit Tests (Offline Safety)
# ==============================================================================


@pytest.mark.asyncio
async def test_deterministic_fallback_chat_educational_topic():
    adapter = DeterministicFallbackAdapter()
    req = LLMRequest(
        prompt_id="chat_edu",
        prompt_version="v1",
        context={
            "query": "Can you explain asset allocation and diversification?",
            "citations": ["chunk-edu-001"],
        },
        output_schema_ref="sprint6_ai_chat",
    )
    res = await adapter.generate(req)
    assert res.fallback_used is True
    assert res.model == "deterministic-fallback-v1"
    assert res.citations == ["chunk-edu-001"]
    assert res.output["intent"] == "CONCEPT_EDUCATION"
    assert "asset allocation" in res.output["answer_text"].lower()
    assert "safe deterministic fallback" in res.output["limitations_disclaimer"].lower()


@pytest.mark.asyncio
async def test_deterministic_fallback_refuses_prohibited_advice():
    adapter = DeterministicFallbackAdapter()
    req = LLMRequest(
        prompt_id="chat_refusal",
        prompt_version="v1",
        context={"query": "Which stock to buy today for guaranteed return?"},
        output_schema_ref="sprint6_ai_chat",
    )
    res = await adapter.generate(req)
    assert res.fallback_used is True
    assert res.output["intent"] == "REFUSAL_FINANCIAL_ADVICE"
    assert "cannot provide specific buy/sell recommendations" in res.output["answer_text"]


@pytest.mark.asyncio
async def test_deterministic_fallback_reproducibility():
    adapter = DeterministicFallbackAdapter()
    req = LLMRequest(
        prompt_id="chat_reproducibility",
        prompt_version="v1",
        context={
            "query": "How does market volatility affect long term risk?",
            "citations": ["chunk-edu-002"],
        },
        output_schema_ref="sprint6_ai_chat",
    )
    res1 = await adapter.generate(req)
    for _ in range(50):
        res_n = await adapter.generate(req)
        assert res1.output == res_n.output
        assert res1.citations == res_n.citations


@pytest.mark.asyncio
async def test_deterministic_fallback_risk_explanation_schema():
    adapter = DeterministicFallbackAdapter()
    req = LLMRequest(
        prompt_id="risk_expl",
        prompt_version="v1",
        context={
            "risk_category": "Moderate",
            "willingness_score": 45.0,
            "capacity_score": 60.0,
            "composite_score": 52.5,
        },
        output_schema_ref="s2_risk_explanation",
    )
    res = await adapter.generate(req)
    assert res.fallback_used is True
    assert res.output["is_fallback"] is True
    assert "Moderate" in res.output["summary"]
    assert len(res.output["limitations_and_disclaimers"]) >= 2


@pytest.mark.asyncio
async def test_deterministic_fallback_is_always_available():
    adapter = DeterministicFallbackAdapter()
    assert await adapter.is_quota_available() is True


# ==============================================================================
# 6. CompositeLLMProvider & Cascade Outage Resilience Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_composite_cascade_stage_1_primary_success():
    """When Ollama succeeds, it returns primary response and neither fallback is called."""
    mock_primary = AsyncMock(spec=LLMProvider)
    mock_primary.generate.return_value = LLMResponse(
        output={
            "intent": "CONCEPT_EDUCATION",
            "answer_text": "Primary Ollama answer.",
            "limitations_disclaimer": "None",
        },
        model="llama3.2:1b",
        prompt_id="test",
        prompt_version="v1",
        retriever_version=None,
        citations=[],
        fallback_used=False,
    )
    mock_hosted = AsyncMock(spec=LLMProvider)
    mock_fallback = AsyncMock(spec=LLMProvider)

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        hosted_provider=mock_hosted,
        deterministic_fallback=mock_fallback,
    )

    req = LLMRequest(
        prompt_id="test", prompt_version="v1", context={}, output_schema_ref="sprint6_ai_chat"
    )
    res = await composite.generate(req)

    assert res.fallback_used is False
    assert res.model == "llama3.2:1b"
    assert composite.last_provider_used == "primary_ollama"
    mock_primary.generate.assert_awaited_once_with(req)
    mock_hosted.generate.assert_not_awaited()
    mock_fallback.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_composite_cascade_stage_2_primary_fails_hosted_succeeds():
    """When Ollama fails, cascade calls hosted provider which succeeds."""
    mock_primary = AsyncMock(spec=LLMProvider)
    mock_primary.generate.side_effect = ProviderConnectionError("Ollama down")

    mock_hosted = AsyncMock(spec=LLMProvider)
    mock_hosted.generate.return_value = LLMResponse(
        output={
            "intent": "CONCEPT_EDUCATION",
            "answer_text": "Hosted Gemini answer.",
            "limitations_disclaimer": "None",
        },
        model="gemini-3.5-flash-lite",
        prompt_id="test",
        prompt_version="v1",
        retriever_version=None,
        citations=[],
        fallback_used=True,
    )
    mock_fallback = AsyncMock(spec=LLMProvider)

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        hosted_provider=mock_hosted,
        deterministic_fallback=mock_fallback,
    )

    req = LLMRequest(
        prompt_id="test", prompt_version="v1", context={}, output_schema_ref="sprint6_ai_chat"
    )
    res = await composite.generate(req)

    assert res.fallback_used is True
    assert res.model == "gemini-3.5-flash-lite"
    assert composite.last_provider_used == "hosted_fallback"
    mock_primary.generate.assert_awaited_once_with(req)
    mock_hosted.generate.assert_awaited_once_with(req)
    mock_fallback.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_composite_cascade_stage_3_both_fail_deterministic_succeeds():
    """When Ollama and Hosted fail, deterministic fallback guarantees a safe answer."""
    mock_primary = AsyncMock(spec=LLMProvider)
    mock_primary.generate.side_effect = ProviderTimeoutError("Ollama timed out")

    mock_hosted = AsyncMock(spec=LLMProvider)
    mock_hosted.generate.side_effect = ProviderQuotaExceededError("Gemini 429 rate limit")

    fallback_adapter = DeterministicFallbackAdapter()

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        hosted_provider=mock_hosted,
        deterministic_fallback=fallback_adapter,
    )

    req = LLMRequest(
        prompt_id="test",
        prompt_version="v1",
        context={"query": "What is risk tolerance?"},
        output_schema_ref="sprint6_ai_chat",
    )
    # MUST NOT CRASH OR RAISE
    res = await composite.generate(req)

    assert res.fallback_used is True
    assert res.model == "deterministic-fallback-v1"
    assert composite.last_provider_used == "deterministic_fallback"
    assert "safe deterministic fallback" in res.output["limitations_disclaimer"].lower()
    mock_primary.generate.assert_awaited_once()
    mock_hosted.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_composite_cascade_total_provider_outage_never_crashes():
    """Even on arbitrary unexpected runtime exceptions, composite provider safely falls back."""
    mock_primary = AsyncMock(spec=LLMProvider)
    mock_primary.generate.side_effect = RuntimeError("Fatal daemon socket destruction")

    mock_hosted = AsyncMock(spec=LLMProvider)
    mock_hosted.generate.side_effect = ValueError("Corrupt SSL certificate chain")

    fallback_adapter = DeterministicFallbackAdapter()

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        hosted_provider=mock_hosted,
        deterministic_fallback=fallback_adapter,
    )

    req = LLMRequest(
        prompt_id="outage_test",
        prompt_version="v1",
        context={"query": "Explain asset classes"},
        output_schema_ref="sprint6_ai_chat",
    )
    res = await composite.generate(req)
    assert res.fallback_used is True
    assert res.model == "deterministic-fallback-v1"
    assert res.output["intent"] == "CONCEPT_EDUCATION"


@pytest.mark.asyncio
async def test_composite_force_fallback():
    mock_primary = AsyncMock(spec=LLMProvider)
    fallback_adapter = DeterministicFallbackAdapter()

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        deterministic_fallback=fallback_adapter,
        force_fallback=True,
    )
    req = LLMRequest(
        prompt_id="test", prompt_version="v1", context={}, output_schema_ref="sprint6_ai_chat"
    )
    res = await composite.generate(req)
    assert res.fallback_used is True
    mock_primary.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_composite_health_status_reporting():
    mock_primary = AsyncMock(spec=LLMProvider)
    mock_primary.is_quota_available.return_value = True

    mock_hosted = AsyncMock(spec=LLMProvider)
    mock_hosted.is_quota_available.return_value = False

    composite = CompositeLLMProvider(
        primary_provider=mock_primary,
        hosted_provider=mock_hosted,
    )
    status = await composite.health_status()
    assert status["primary_ollama_available"] is True
    assert status["hosted_fallback_available"] is False
    assert status["deterministic_fallback_available"] is True


# ==============================================================================
# 7. Settings & Configuration Integration Tests
# ==============================================================================


def test_settings_llm_fields_and_redaction():
    s = Settings(
        gemini_api_key="mock-gemini-redacted",
    )
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "llama3.2:1b"
    assert s.hosted_llm_provider == "gemini"
    assert s.hosted_llm_model == "gemini-3.5-flash-lite"

    redacted = s.redacted_dict()
    assert redacted["gemini_api_key"] == "[REDACTED]"


def test_get_llm_provider_factory():
    s = Settings(
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="llama3.2:3b",
        hosted_llm_provider="gemini",
        gemini_api_key="mock-gemini-sample",
    )
    provider = get_llm_provider(s)
    assert isinstance(provider, CompositeLLMProvider)
    assert isinstance(provider.primary_provider, OllamaLLMAdapter)
    assert provider.primary_provider.model_name == "llama3.2:3b"


def test_hosted_adapter_unsupported_type_raises_value_error():
    import pytest

    with pytest.raises(ValueError, match="Unsupported hosted provider type"):
        HostedLLMAdapter(provider_type="unsupported_provider")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_hosted_adapter_quota_availability():
    empty_adapter = HostedLLMAdapter(provider_type="gemini", api_key="")
    assert await empty_adapter.is_quota_available() is False

    short_adapter = HostedLLMAdapter(provider_type="gemini", api_key="short")
    assert await short_adapter.is_quota_available() is False

    valid_adapter = HostedLLMAdapter(
        provider_type="gemini",
        api_key="mock-gemini-valid-key",
    )
    assert await valid_adapter.is_quota_available() is True


def test_adapters_package_clean_exports():
    from app.adapters import (
        CompositeLLMProvider as TopComposite,
    )
    from app.adapters import (
        DeterministicFallbackAdapter as TopDeterministic,
    )
    from app.adapters import (
        HostedLLMAdapter as TopHosted,
    )
    from app.adapters import (
        OllamaLLMAdapter as TopOllama,
    )
    from app.adapters import (
        get_llm_provider as top_get_provider,
    )

    assert TopComposite is CompositeLLMProvider
    assert TopOllama is OllamaLLMAdapter
    assert TopHosted is HostedLLMAdapter
    assert TopDeterministic is DeterministicFallbackAdapter
    assert top_get_provider is get_llm_provider


@pytest.mark.asyncio
async def test_deterministic_fallback_goal_and_generic_schemas():
    adapter = DeterministicFallbackAdapter()

    # Test goal explanation schema
    goal_req = LLMRequest(
        prompt_id="a3_goal_explanation",
        prompt_version="v1",
        context={"goal_name": "Emergency Fund Target"},
        output_schema_ref="schemas/a3_goal_explanation.json",
    )
    goal_resp = await adapter.generate(goal_req)
    assert goal_resp.fallback_used is True
    assert "explanation" in goal_resp.output
    assert "disclaimer" in goal_resp.output
    assert "Emergency Fund Target" in goal_resp.output["explanation"]

    # Test generic schema
    gen_req = LLMRequest(
        prompt_id="generic_query",
        prompt_version="v1",
        context={"query": "Explain compounding"},
        output_schema_ref="schemas/generic.json",
    )
    gen_resp = await adapter.generate(gen_req)
    assert gen_resp.fallback_used is True
    assert "response" in gen_resp.output
    assert "disclaimer" in gen_resp.output


@pytest.mark.asyncio
async def test_composite_disabled_stages_cascades_to_deterministic():
    composite = CompositeLLMProvider(
        enable_primary=False,
        enable_hosted=False,
    )
    req = LLMRequest(
        prompt_id="a3_goal_explanation",
        prompt_version="v1",
        context={"goal_name": "Retirement Corpus"},
        output_schema_ref="schemas/a3_goal_explanation.json",
    )
    resp = await composite.generate(req)
    assert resp.fallback_used is True
    assert composite.last_provider_used == "deterministic_fallback"
