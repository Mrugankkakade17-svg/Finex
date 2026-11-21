"""Unit tests for persistent AI feedback and strict user isolation (S1-MI01).

Verifies that:
- Feedback survives service / repository re-instantiation (restart simulation).
- User isolation is strictly enforced (User A cannot see or access User B's feedback).
- Payload schema validation works as expected (valid ratings, length bounds).
"""

import tempfile
import uuid
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.main import create_app
from app.repositories.ai_feedback_repository import AIFeedbackRepository, ai_feedback_repository


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_feedback.sqlite3"
        yield db_file


@pytest.fixture
def isolated_repo(temp_db_path: Path) -> AIFeedbackRepository:
    return AIFeedbackRepository(db_path=temp_db_path)


class TestAIFeedbackRepositoryPersistence:
    """Verifies that AIFeedbackRepository correctly persists data and survives restarts."""

    def test_feedback_persists_and_survives_restart(self, temp_db_path: Path):
        user_id = f"user-{uuid.uuid4().hex[:8]}"

        # Instance 1: write feedback
        repo1 = AIFeedbackRepository(db_path=temp_db_path)
        saved = repo1.create_feedback(
            user_id=user_id,
            message_id="msg-1001",
            rating="THUMBS_UP",
            comment="Very helpful grounding citations.",
        )
        assert saved["feedback_id"].startswith("fb-")
        assert saved["user_id"] == user_id
        assert saved["message_id"] == "msg-1001"
        assert saved["rating"] == "THUMBS_UP"

        # Instance 2: re-instantiate from same database path (simulating application restart)
        repo2 = AIFeedbackRepository(db_path=temp_db_path)
        records = repo2.list_feedback_by_user(user_id)
        assert len(records) == 1
        assert records[0]["feedback_id"] == saved["feedback_id"]
        assert records[0]["message_id"] == "msg-1001"
        assert records[0]["comment"] == "Very helpful grounding citations."

        single = repo2.get_feedback(user_id=user_id, feedback_id=saved["feedback_id"])
        assert single is not None
        assert single["feedback_id"] == saved["feedback_id"]

    def test_user_isolation_in_repository(self, isolated_repo: AIFeedbackRepository):
        user_a = f"user-a-{uuid.uuid4().hex[:8]}"
        user_b = f"user-b-{uuid.uuid4().hex[:8]}"

        # User A writes 2 feedback records
        fb_a1 = isolated_repo.create_feedback(
            user_id=user_a,
            message_id="msg-a1",
            rating="THUMBS_UP",
            comment="User A note 1",
        )
        fb_a2 = isolated_repo.create_feedback(
            user_id=user_a,
            message_id="msg-a2",
            rating="THUMBS_DOWN",
            comment="User A note 2",
        )

        # User B writes 1 feedback record
        fb_b1 = isolated_repo.create_feedback(
            user_id=user_b,
            message_id="msg-b1",
            rating="THUMBS_UP",
            comment="User B note 1",
        )

        # Query as User A: must see ONLY user A's feedback
        list_a = isolated_repo.list_feedback_by_user(user_a)
        assert len(list_a) == 2
        assert all(r["user_id"] == user_a for r in list_a)
        assert {r["feedback_id"] for r in list_a} == {fb_a1["feedback_id"], fb_a2["feedback_id"]}

        # Query as User B: must see ONLY user B's feedback
        list_b = isolated_repo.list_feedback_by_user(user_b)
        assert len(list_b) == 1
        assert list_b[0]["user_id"] == user_b
        assert list_b[0]["feedback_id"] == fb_b1["feedback_id"]

        # User A cannot retrieve User B's record by ID
        cross_read = isolated_repo.get_feedback(user_id=user_a, feedback_id=fb_b1["feedback_id"])
        assert cross_read is None

        # User B cannot retrieve User A's record by ID
        cross_read_b = isolated_repo.get_feedback(user_id=user_b, feedback_id=fb_a1["feedback_id"])
        assert cross_read_b is None


class TestAIFeedbackAPIEndpointIsolation:
    """End-to-end API test verifying multi-user feedback isolation and payload validation."""

    @pytest.fixture(autouse=True)
    def clean_db(self):
        ai_feedback_repository.clear_for_test()
        yield
        ai_feedback_repository.clear_for_test()

    def test_multi_user_api_isolation(self):
        app = create_app()

        user_alice = f"usr_alice_{uuid.uuid4().hex[:6]}"
        user_bob = f"usr_bob_{uuid.uuid4().hex[:6]}"

        token_alice = create_access_token({"sub": user_alice, "user_id": user_alice})
        token_bob = create_access_token({"sub": user_bob, "user_id": user_bob})

        headers_alice = {"Authorization": f"Bearer {token_alice}"}
        headers_bob = {"Authorization": f"Bearer {token_bob}"}

        with TestClient(app) as client:
            # Alice submits feedback
            res_a = client.post(
                "/api/v1/ai/feedback",
                json={
                    "message_id": "msg-001-alice",
                    "rating": "THUMBS_UP",
                    "comment": "Alice comment",
                },
                headers=headers_alice,
            )
            assert res_a.status_code == 200
            data_a = res_a.json()["data"]
            assert data_a["user_id"] == user_alice

            # Bob submits feedback
            res_b = client.post(
                "/api/v1/ai/feedback",
                json={
                    "message_id": "msg-002-bob",
                    "rating": "THUMBS_DOWN",
                    "comment": "Bob comment",
                },
                headers=headers_bob,
            )
            assert res_b.status_code == 200
            data_b = res_b.json()["data"]
            assert data_b["user_id"] == user_bob

            # Alice lists feedback: sees only her record
            list_res_a = client.get("/api/v1/ai/feedback", headers=headers_alice)
            assert list_res_a.status_code == 200
            alice_items = list_res_a.json()["data"]
            assert len(alice_items) == 1
            assert alice_items[0]["user_id"] == user_alice
            assert alice_items[0]["message_id"] == "msg-001-alice"

            # Bob lists feedback: sees only his record
            list_res_b = client.get("/api/v1/ai/feedback", headers=headers_bob)
            assert list_res_b.status_code == 200
            bob_items = list_res_b.json()["data"]
            assert len(bob_items) == 1
            assert bob_items[0]["user_id"] == user_bob
            assert bob_items[0]["message_id"] == "msg-002-bob"

    def test_feedback_schema_validation(self):
        app = create_app()
        token = create_access_token({"sub": "usr_val", "user_id": "usr_val"})
        headers = {"Authorization": f"Bearer {token}"}

        with TestClient(app) as client:
            # Invalid rating value
            res1 = client.post(
                "/api/v1/ai/feedback",
                json={"message_id": "msg-001", "rating": "5_STARS"},
                headers=headers,
            )
            assert res1.status_code == 422

            # Missing message_id
            res2 = client.post(
                "/api/v1/ai/feedback",
                json={"rating": "THUMBS_UP"},
                headers=headers,
            )
            assert res2.status_code == 422

            # Comment exceeding max length (500 chars)
            res3 = client.post(
                "/api/v1/ai/feedback",
                json={"message_id": "msg-001", "rating": "THUMBS_UP", "comment": "A" * 501},
                headers=headers,
            )
            assert res3.status_code == 422
