"""FastAPI endpoints integration tests for Risk Evaluation and Explanation (S2-AI-02)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_ANSWERS = [
    {"question_id": "W1", "answer_code": "W1_C"},
    {"question_id": "W2", "answer_code": "W2_C"},
    {"question_id": "W3", "answer_code": "W3_C"},
    {"question_id": "W4", "answer_code": "W4_C"},
    {"question_id": "W5", "answer_code": "W5_C"},
    {"question_id": "C1", "answer_code": "C1_C"},
    {"question_id": "C2", "answer_code": "C2_C"},
    {"question_id": "C3", "answer_code": "C3_C"},
    {"question_id": "C4", "answer_code": "C4_C"},
    {"question_id": "C5", "answer_code": "C5_C"},
]


def test_api_risk_evaluate_success():
    """Verify POST /api/v1/risk/evaluate computes deterministic score in standard envelope."""
    payload = {
        "questionnaire_id": "risk_questionnaire_v1",
        "version": "v1",
        "answers": SAMPLE_ANSWERS,
        "calculated_at": "2026-08-29T12:00:00Z",
    }
    response = client.post("/api/v1/risk/evaluate", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert "data" in body
    data = body["data"]
    assert data["composite_score"] == 50.0
    assert data["risk_category"] == "Moderate"
    assert data["willingness_score"] == 50.0
    assert data["capacity_score"] == 50.0


def test_api_risk_explain_with_answers_success():
    """Verify POST /api/v1/risk/explain generates structured explanation from answers."""
    payload = {
        "questionnaire_id": "risk_questionnaire_v1",
        "version": "v1",
        "answers": SAMPLE_ANSWERS,
        "force_fallback": True,
    }
    response = client.post("/api/v1/risk/explain", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "Moderate" in data["summary"]
    assert "willingness_explanation" in data
    assert "capacity_explanation" in data
    assert "alignment_analysis" in data
    assert len(data["key_influencing_factors"]) > 0
    assert len(data["limitations_and_disclaimers"]) >= 3
    assert data["is_fallback"] is True
    assert data["prompt_version"] == "v1.0.0"
    assert data["schema_version"] == "v1.0.0"


def test_api_risk_evaluate_and_explain_one_shot():
    """Verify POST /api/v1/risk/evaluate-and-explain combines calculation and explanation."""
    payload = {
        "questionnaire_id": "risk_questionnaire_v1",
        "version": "v1",
        "answers": SAMPLE_ANSWERS,
    }
    response = client.post("/api/v1/risk/evaluate-and-explain", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "assessment" in data
    assert "explanation" in data
    assert data["assessment"]["composite_score"] == 50.0
    assert data["assessment"]["risk_category"] == "Moderate"
    assert "Moderate" in data["explanation"]["summary"]


def test_api_risk_evaluate_missing_questions_error():
    """Verify validation error when required questions are omitted."""
    incomplete_answers = [
        {"question_id": "W1", "answer_code": "W1_A"},
    ]
    payload = {
        "questionnaire_id": "risk_questionnaire_v1",
        "version": "v1",
        "answers": incomplete_answers,
    }
    response = client.post("/api/v1/risk/evaluate", json=payload)
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_RISK_ASSESSMENT_INPUT"


def test_api_risk_explain_with_precalculated_assessment_success():
    """Verify POST /api/v1/risk/explain accepts pre-calculated assessment result."""
    # First evaluate
    eval_resp = client.post(
        "/api/v1/risk/evaluate",
        json={
            "questionnaire_id": "risk_questionnaire_v1",
            "version": "v1",
            "answers": SAMPLE_ANSWERS,
            "calculated_at": "2026-08-29T12:00:00Z",
        },
    )
    assessment_data = eval_resp.json()["data"]

    # Now explain using assessment object
    payload = {
        "assessment": assessment_data,
        "answers": SAMPLE_ANSWERS,
        "force_fallback": True,
    }
    response = client.post("/api/v1/risk/explain", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert "Moderate" in body["data"]["summary"]


def test_api_risk_explain_missing_both_assessment_and_answers_error():
    """Verify 400 error when neither assessment nor answers are provided."""
    response = client.post(
        "/api/v1/risk/explain",
        json={
            "questionnaire_id": "risk_questionnaire_v1",
            "version": "v1",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_EXPLANATION_REQUEST"


def test_api_risk_evaluate_and_explain_invalid_id_error():
    """Verify 400 error when invalid questionnaire_id is passed."""
    response = client.post(
        "/api/v1/risk/evaluate-and-explain",
        json={
            "questionnaire_id": "non_existent_questionnaire",
            "version": "v1",
            "answers": SAMPLE_ANSWERS,
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_RISK_ASSESSMENT_INPUT"
