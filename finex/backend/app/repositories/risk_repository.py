import json
from pathlib import Path
from typing import Any

QUESTIONNAIRE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "questionnaire" / "risk_questionnaire_v1.json"
)


class RiskRepository:
    """
    Repository for risk questionnaire and assessment data.

    Questionnaire definitions are loaded from the approved v1 JSON.
    Assessment persistence remains in-memory for Sprint API development
    and can later be replaced by an OperationalStore/Lakebase adapter.
    """

    QUESTIONNAIRE_VERSION = "v1"

    def __init__(self):
        self._assessments: dict[int, dict[str, Any]] = {}
        self._next_assessment_id = 1

        with QUESTIONNAIRE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            self._questionnaire = json.load(file)

        self._questions = self._questionnaire["questions"]

    def get_questions(self) -> list[dict[str, Any]]:
        return [question.copy() for question in self._questions]

    def get_questionnaire(self) -> dict[str, Any]:
        return self._questionnaire.copy()

    def get_answer(
        self,
        question_id: str,
        answer_id: str,
    ) -> dict[str, Any] | None:
        for question in self._questions:
            if question["question_id"] != question_id:
                continue

            for answer in question["answers"]:
                if answer["code"] == answer_id:
                    return answer

        return None

    def create_assessment(
        self,
        user_id: int,
        questionnaire_version: str,
        score: float,
        risk_profile: str,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        assessment = {
            "assessment_id": self._next_assessment_id,
            "user_id": user_id,
            "questionnaire_version": questionnaire_version,
            "score": score,
            "risk_profile": risk_profile,
            "answers": answers,
        }

        self._assessments[self._next_assessment_id] = assessment
        self._next_assessment_id += 1

        return assessment


risk_repository = RiskRepository()
