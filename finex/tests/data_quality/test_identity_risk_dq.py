import csv
from pathlib import Path


FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "fixtures"
    / "identity_risk_dq"
)


def load_csv(filename: str) -> list[dict[str, str]]:
    path = FIXTURE_DIR / filename

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_profile_completeness():
    profiles = load_csv("user_profiles_fixture.csv")

    required_fields = [
        "user_id",
        "first_name",
        "last_name",
        "phone",
        "date_of_birth",
        "country",
    ]

    invalid_profiles = [
        profile
        for profile in profiles
        if any(not profile[field].strip() for field in required_fields)
    ]

    assert len(invalid_profiles) == 1
    assert invalid_profiles[0]["user_id"] == "2"


def test_duplicate_identity():
    users = load_csv("users_fixture.csv")

    emails = {}
    duplicates = []

    for user in users:
        email = user["email"].strip().lower()

        if email in emails:
            duplicates.append(user)
        else:
            emails[email] = user["user_id"]

    assert len(duplicates) == 1
    assert duplicates[0]["user_id"] == "3"


def test_consent_status():
    consents = load_csv("user_consents_fixture.csv")

    invalid_consents = [
        consent
        for consent in consents
        if (
            not consent["user_id"].strip()
            or consent["is_consented"].strip().lower() != "true"
            or not consent["consent_type"].strip()
            or not consent["consent_version"].strip()
        )
    ]

    assert len(invalid_consents) == 1
    assert invalid_consents[0]["user_id"] == "2"


def test_orphan_risk_answers():
    assessments = load_csv("risk_assessments_fixture.csv")
    questions = load_csv("risk_questions_fixture.csv")
    answers = load_csv("risk_assessment_answers_fixture.csv")

    assessment_ids = {
        assessment["assessment_id"].strip()
        for assessment in assessments
    }

    question_ids = {
        question["question_id"].strip()
        for question in questions
    }

    orphan_answers = [
        answer
        for answer in answers
        if (
            answer["assessment_id"].strip() not in assessment_ids
            or answer["question_id"].strip() not in question_ids
        )
    ]

    assert len(orphan_answers) == 2

    assert orphan_answers[0]["answer_id"] == "2"
    assert orphan_answers[1]["answer_id"] == "3"