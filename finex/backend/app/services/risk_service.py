from app.core.exceptions import BadRequestException
from app.repositories.risk_repository import risk_repository

QUESTIONNAIRE_VERSION = "v1"


def get_risk_questions() -> dict:
    """Return the approved active risk questionnaire."""

    return {
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "questions": risk_repository.get_questions(),
    }


def calculate_risk_score(answers: list[dict]) -> float:
    """
    Calculate the approved v1 risk score.

    5 willingness questions and 5 capacity questions are scored 1-5.
    Each dimension is normalized to 0-100, then combined 50/50.
    """

    if not answers:
        raise BadRequestException(
            message="At least one risk answer is required.",
            error_code="EMPTY_RISK_ANSWERS",
        )

    questions = {question["question_id"]: question for question in risk_repository.get_questions()}

    if len(answers) != len(questions):
        raise BadRequestException(
            message="All risk questions must be answered.",
            error_code="INCOMPLETE_RISK_ANSWERS",
        )

    willingness_scores = []
    capacity_scores = []
    answered_questions = set()

    for answer in answers:
        question_id = answer.get("question_id")
        answer_id = answer.get("answer_id")

        if not isinstance(question_id, str) or not isinstance(answer_id, str):
            raise BadRequestException(
                message="Invalid risk answer payload.",
                error_code="INVALID_RISK_ANSWER_PAYLOAD",
            )

        if question_id in answered_questions:
            raise BadRequestException(
                message=f"Duplicate answer for question: {question_id}",
                error_code="DUPLICATE_RISK_ANSWER",
            )

        question = questions.get(question_id)

        if question is None:
            raise BadRequestException(
                message=f"Invalid question ID: {question_id}",
                error_code="INVALID_QUESTION_ID",
            )

        selected_answer = risk_repository.get_answer(
            question_id=question_id,
            answer_id=answer_id,
        )

        if selected_answer is None:
            raise BadRequestException(
                message=f"Invalid answer ID: {answer_id}",
                error_code="INVALID_ANSWER_ID",
            )

        score = selected_answer["proposed_score"]
        dimension = question["dimension"]

        if dimension == "willingness":
            willingness_scores.append(score)
        elif dimension == "capacity":
            capacity_scores.append(score)

        answered_questions.add(question_id)

    if len(willingness_scores) != 5 or len(capacity_scores) != 5:
        raise BadRequestException(
            message="All willingness and capacity questions must be answered.",
            error_code="INCOMPLETE_RISK_DIMENSIONS",
        )

    willingness_raw = sum(willingness_scores)
    capacity_raw = sum(capacity_scores)

    willingness_score = ((willingness_raw - 5) / 20) * 100
    capacity_score = ((capacity_raw - 5) / 20) * 100

    return round(
        (willingness_score * 0.5) + (capacity_score * 0.5),
        2,
    )


def get_risk_profile(score: float) -> str:
    """Convert normalized v1 score into the approved risk category."""

    if score < 34:
        return "Conservative"

    if score < 67:
        return "Moderate"

    return "Aggressive"


def create_risk_assessment(
    user_id: int,
    questionnaire_version: str,
    answers: list[dict],
) -> dict:
    """Validate questionnaire version, calculate score and persist assessment."""

    if questionnaire_version != QUESTIONNAIRE_VERSION:
        raise BadRequestException(
            message="Unsupported questionnaire version.",
            error_code="INVALID_QUESTIONNAIRE_VERSION",
        )

    score = calculate_risk_score(answers)
    risk_profile = get_risk_profile(score)

    return risk_repository.create_assessment(
        user_id=user_id,
        questionnaire_version=questionnaire_version,
        score=score,
        risk_profile=risk_profile,
        answers=answers,
    )
