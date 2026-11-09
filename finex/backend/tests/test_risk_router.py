from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app

client = TestClient(app)


def test_risk_questions_requires_authentication():
    response = client.get("/api/v1/risk/questions")

    assert response.status_code in (401, 403)


def test_risk_questions_success():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.get("/api/v1/risk/questions")

    assert response.status_code == 200

    body = response.json()

    assert body["data"]["questionnaire_version"] == "v1"
    assert len(body["data"]["questions"]) == 10
    assert "meta" in body
    assert body["meta"]["correlationId"]

    app.dependency_overrides.clear()


def test_risk_assessment_success():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.post(
        "/api/v1/risk/assessments",
        json={
            "questionnaire_version": "v1",
            "answers": [
                {"question_id": "W1", "answer_id": "W1_A"},
                {"question_id": "W2", "answer_id": "W2_A"},
                {"question_id": "W3", "answer_id": "W3_A"},
                {"question_id": "W4", "answer_id": "W4_A"},
                {"question_id": "W5", "answer_id": "W5_A"},
                {"question_id": "C1", "answer_id": "C1_A"},
                {"question_id": "C2", "answer_id": "C2_A"},
                {"question_id": "C3", "answer_id": "C3_A"},
                {"question_id": "C4", "answer_id": "C4_A"},
                {"question_id": "C5", "answer_id": "C5_A"},
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["data"]["user_id"] == 1
    assert body["data"]["questionnaire_version"] == "v1"
    assert "score" in body["data"]
    assert "risk_profile" in body["data"]

    assert "meta" in body
    assert body["meta"]["correlationId"]

    app.dependency_overrides.clear()


def test_risk_assessment_rejects_invalid_answer_id():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.post(
        "/api/v1/risk/assessments",
        json={
            "questionnaire_version": "v1",
            "answers": [
                {"question_id": "W1", "answer_id": "wrong_id"},
                {"question_id": "W2", "answer_id": "W2_A"},
                {"question_id": "W3", "answer_id": "W3_A"},
                {"question_id": "W4", "answer_id": "W4_A"},
                {"question_id": "W5", "answer_id": "W5_A"},
                {"question_id": "C1", "answer_id": "C1_A"},
                {"question_id": "C2", "answer_id": "C2_A"},
                {"question_id": "C3", "answer_id": "C3_A"},
                {"question_id": "C4", "answer_id": "C4_A"},
                {"question_id": "C5", "answer_id": "C5_A"},
            ],
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["error"]["code"] == "INVALID_ANSWER_ID"

    app.dependency_overrides.clear()


def test_risk_assessment_rejects_wrong_questionnaire_version():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.post(
        "/api/v1/risk/assessments",
        json={
            "questionnaire_version": "REVIEW",
            "answers": [
                {"question_id": "W1", "answer_id": "W1_A"},
            ],
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["error"]["code"] == "INVALID_QUESTIONNAIRE_VERSION"

    app.dependency_overrides.clear()
