import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)

MOCK_TOKEN = "mock:contract@finex.com:Contract User"

VALID_ANSWERS = [
    {"question_id": "W1", "answer_id": "W1_C"},
    {"question_id": "W2", "answer_id": "W2_C"},
    {"question_id": "W3", "answer_id": "W3_C"},
    {"question_id": "W4", "answer_id": "W4_C"},
    {"question_id": "W5", "answer_id": "W5_C"},
    {"question_id": "C1", "answer_id": "C1_C"},
    {"question_id": "C2", "answer_id": "C2_C"},
    {"question_id": "C3", "answer_id": "C3_C"},
    {"question_id": "C4", "answer_id": "C4_C"},
    {"question_id": "C5", "answer_id": "C5_C"},
]


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    fresh_repo = UserRepository()

    monkeypatch.setattr(
        "app.services.auth_service.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.routers.users.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.services.risk_service.risk_repository",
        __import__(
            "app.repositories.risk_repository",
            fromlist=["risk_repository"],
        ).risk_repository,
    )


def _get_access_token():
    response = client.post(
        "/api/v1/auth/google/callback",
        json={"id_token": MOCK_TOKEN},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


class TestRiskSuccessEnvelope:
    def test_risk_assessment_success_shape(self):
        token = _get_access_token()

        response = client.post(
            "/api/v1/risk/assessments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "questionnaire_version": "v1",
                "answers": VALID_ANSWERS,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True
        assert "message" in body
        assert "data" in body
        assert "meta" in body

        data = body["data"]

        assert "assessment_id" in data
        assert "user_id" in data
        assert "questionnaire_version" in data
        assert "score" in data
        assert "risk_profile" in data

        assert data["questionnaire_version"] == "v1"
        assert isinstance(data["score"], (int, float))
        assert data["risk_profile"] in {
            "Conservative",
            "Moderate",
            "Aggressive",
        }

        meta = body["meta"]

        assert "correlationId" in meta
        assert "apiVersion" in meta
        assert "dataStatus" in meta


class TestRiskErrorEnvelope:
    def test_risk_without_authentication(self):
        response = client.post(
            "/api/v1/risk/assessments",
            json={
                "questionnaire_version": "v1",
                "answers": VALID_ANSWERS,
            },
        )

        assert response.status_code == 403

        body = response.json()

        assert body["success"] is False
        assert "message" in body
        assert "error_code" in body

    def test_invalid_questionnaire_version(self):
        token = _get_access_token()

        response = client.post(
            "/api/v1/risk/assessments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "questionnaire_version": "v2",
                "answers": VALID_ANSWERS,
            },
        )

        assert response.status_code == 400

        body = response.json()

        assert body["success"] is False
        assert "message" in body
        assert "error_code" in body

    def test_empty_answers(self):
        token = _get_access_token()

        response = client.post(
            "/api/v1/risk/assessments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "questionnaire_version": "v1",
                "answers": [],
            },
        )

        assert response.status_code == 400

        body = response.json()

        assert body["success"] is False
        assert body["error_code"] == "EMPTY_RISK_ANSWERS"

    def test_incomplete_answers(self):
        token = _get_access_token()

        response = client.post(
            "/api/v1/risk/assessments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "questionnaire_version": "v1",
                "answers": VALID_ANSWERS[:5],
            },
        )

        assert response.status_code == 400

        body = response.json()

        assert body["success"] is False
        assert body["error_code"] == "INCOMPLETE_RISK_ANSWERS"

    def test_invalid_answer_id(self):
        token = _get_access_token()

        answers = VALID_ANSWERS.copy()
        answers[0] = {
            "question_id": "W1",
            "answer_id": "INVALID",
        }

        response = client.post(
            "/api/v1/risk/assessments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "questionnaire_version": "v1",
                "answers": answers,
            },
        )

        assert response.status_code == 400

        body = response.json()

        assert body["success"] is False
        assert body["error_code"] == "INVALID_ANSWER_ID"
