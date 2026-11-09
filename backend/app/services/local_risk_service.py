"""Owned drafts and immutable risk history inside one authorized unit of work."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from uuid import uuid4

from ai.risk.contract import (
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    RiskContractError,
    educational_explanation,
    evaluate_risk_contract,
    validate_risk_input,
)
from ai.risk.scoring import RiskScoringEngine

from app.core.exceptions import FinExException
from app.domain.local_application import Clock, LocalStoreUnavailable
from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.ports.local_risk_store import LocalRiskStore
from app.schemas.local_risk import (
    UUID4_PATTERN,
    LocalRiskDraft,
    LocalRiskHistory,
    LocalRiskInput,
    LocalRiskQuestionnaire,
    LocalRiskSubmitRequest,
    LocalSavedRiskAssessment,
    LocalSavedRiskResult,
)
from app.schemas.risk_contract import EducationalExplanation
from app.services.local_authorization import authorized_transaction, utc_clock, utc_now

RULES_BYTE_LIMIT = 64 * 1024
DOCUMENT_BYTE_LIMIT = 128 * 1024
MAX_SEQUENCE = 2**63 - 1
DOCUMENT_FIELDS = frozenset(
    {
        "scope",
        "contract_version",
        "persisted",
        "assessment_id",
        "created_at",
        "input",
        "assessment",
        "explanation",
        "explanation_version",
        "rules_sha256",
        "rules_snapshot",
    }
)


def _json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _reject_constant(_: str) -> object:
    raise ValueError("Non-finite JSON is not supported.")


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON fields are not supported.")
        result[key] = value
    return result


def _stored_json(value: str) -> object:
    if not isinstance(value, str) or len(value.encode("utf-8")) > DOCUMENT_BYTE_LIMIT:
        raise ValueError("Stored risk document has an unsupported shape.")
    return json.loads(value, object_pairs_hook=_unique_fields, parse_constant=_reject_constant)


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Risk time must be UTC-aware.")
    return value


def _text_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Risk time must be UTC text.")
    return _time(datetime.fromisoformat(value))


def _rules_hash(snapshot: object) -> str:
    serialized = _json(snapshot).encode("utf-8")
    if len(serialized) > RULES_BYTE_LIMIT:
        raise ValueError("The rules snapshot exceeds its bounded contract.")
    return hashlib.sha256(serialized).hexdigest()


def _fingerprint(payload: LocalRiskInput) -> str:
    accepted = payload.model_dump(mode="json")
    accepted["answers"] = sorted(accepted["answers"], key=lambda answer: answer["question_id"])
    return hashlib.sha256(_json(accepted).encode("utf-8")).hexdigest()


def _semantic_input(payload: LocalRiskInput, engine: RiskScoringEngine, *, complete: bool) -> None:
    try:
        validate_risk_input(payload.model_dump(mode="json"), engine, require_complete=complete)
    except RiskContractError as exc:
        raise FinExException(message=str(exc), error_code=exc.code, status_code=400) from None
    except Exception:
        raise _risk_unavailable() from None


def _risk_unavailable() -> FinExException:
    return FinExException(
        message="The approved educational assessment is currently unavailable.",
        error_code="RISK_ASSESSMENT_UNAVAILABLE",
        status_code=503,
    )


def _not_found() -> FinExException:
    return FinExException(
        message="The saved risk assessment was not found.",
        error_code="RISK_ASSESSMENT_NOT_FOUND",
        status_code=404,
    )


def _result(
    payload: LocalRiskInput, engine: RiskScoringEngine, now: datetime | str
) -> LocalSavedRiskResult:
    calculated = evaluate_risk_contract(
        payload.model_dump(mode="json"), calculated_at=now, engine=engine
    )
    calculated.setdefault("informational_tension", None)
    return LocalSavedRiskResult.model_validate(calculated, strict=True)


class LocalRiskService:
    def __init__(self, store: LocalRiskStore, clock: Clock = utc_clock) -> None:
        self.store = store
        self.clock = clock
        self._engine: RiskScoringEngine | None = None

    def _approved_engine(self) -> RiskScoringEngine:
        try:
            if self._engine is None:
                # Copy/validate once; no request can mutate the shared rules.
                candidate = RiskScoringEngine.from_config(RiskScoringEngine().config)
                _rules_hash(candidate.config)
                self._engine = candidate
            return self._engine
        except Exception:
            raise _risk_unavailable() from None

    def questionnaire(self, token: str) -> LocalRiskQuestionnaire:
        with authorized_transaction(self.store, token, self.clock, onboarding_required=True):
            engine = self._approved_engine()
            try:
                return LocalRiskQuestionnaire.model_validate(
                    {
                        "questions": [
                            {
                                "question_id": question["question_id"],
                                "dimension": question["dimension"],
                                "text": question["text"],
                                "options": [
                                    {"code": option["code"], "label": option["label"]}
                                    for option in question["answers"]
                                ],
                            }
                            for question in engine.config["questions"]
                        ],
                        "rules_sha256": _rules_hash(engine.config),
                        "limitation": {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE},
                    },
                    strict=True,
                )
            except Exception:
                raise _risk_unavailable() from None

    def draft(self, token: str) -> LocalRiskDraft:
        with authorized_transaction(self.store, token, self.clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            record = transaction.get_risk_draft(session.user.id)
            if record is None:
                return LocalRiskDraft(answers=[], updated_at=None)
            engine = self._approved_engine()
            try:
                if record.user_id != session.user.id:
                    raise ValueError("Risk draft ownership does not match.")
                payload = LocalRiskInput.model_validate(
                    {
                        "questionnaire_id": record.questionnaire_id,
                        "questionnaire_version": record.questionnaire_version,
                        "answers": _stored_json(record.answers_json),
                    },
                    strict=True,
                )
                validate_risk_input(payload.model_dump(mode="json"), engine, require_complete=False)
                return LocalRiskDraft(
                    answers=payload.answers, updated_at=_time(record.updated_at).isoformat()
                )
            except Exception:
                raise LocalStoreUnavailable() from None

    def save_draft(self, token: str, payload: LocalRiskInput) -> LocalRiskDraft:
        with authorized_transaction(
            self.store, token, self.clock, write=True, onboarding_required=True
        ) as (session, transaction):
            engine = self._approved_engine()
            _semantic_input(payload, engine, complete=False)
            now = utc_now(self.clock)
            record = LocalRiskDraftRecord(
                user_id=session.user.id,
                questionnaire_id=payload.questionnaire_id,
                questionnaire_version=payload.questionnaire_version,
                answers_json=_json([answer.model_dump(mode="json") for answer in payload.answers]),
                updated_at=now,
            )
            transaction.save_risk_draft(record)
            return LocalRiskDraft(answers=payload.answers, updated_at=now.isoformat())

    def submit(self, token: str, payload: LocalRiskSubmitRequest) -> LocalSavedRiskAssessment:
        with authorized_transaction(
            self.store, token, self.clock, write=True, onboarding_required=True
        ) as (session, transaction):
            engine = self._approved_engine()
            accepted = LocalRiskInput.model_validate(
                payload.model_dump(mode="json", exclude={"idempotency_key"}), strict=True
            )
            _semantic_input(accepted, engine, complete=True)
            fingerprint = _fingerprint(accepted)
            previous = transaction.get_risk_assessment_by_key(
                session.user.id, payload.idempotency_key
            )
            if previous is not None:
                original = self._restore(previous, session.user.id)
                if previous.idempotency_key != payload.idempotency_key:
                    raise LocalStoreUnavailable()
                if previous.request_fingerprint != fingerprint:
                    raise FinExException(
                        message="Use a new retry key for a different complete assessment.",
                        error_code="IDEMPOTENCY_CONFLICT",
                        status_code=409,
                    )
                return original
            now = utc_now(self.clock)
            try:
                result = _result(accepted, engine, now)
                explanation = EducationalExplanation.model_validate(
                    educational_explanation(result.model_dump(mode="json", exclude_none=True)),
                    strict=True,
                )
                saved = LocalSavedRiskAssessment.model_validate(
                    {
                        "assessment_id": str(uuid4()),
                        "created_at": now.isoformat(),
                        "input": accepted,
                        "assessment": result,
                        "explanation": explanation,
                        "rules_sha256": _rules_hash(engine.config),
                        "rules_snapshot": engine.config,
                    },
                    strict=True,
                )
                document_json = _json(saved.model_dump(mode="json"))
                if len(document_json.encode("utf-8")) > DOCUMENT_BYTE_LIMIT:
                    raise ValueError("The assessment exceeds its bounded contract.")
            except Exception:
                raise _risk_unavailable() from None
            inserted = transaction.insert_risk_assessment(
                LocalRiskAssessmentRecord(
                    assessment_id=saved.assessment_id,
                    user_id=session.user.id,
                    idempotency_key=payload.idempotency_key,
                    request_fingerprint=fingerprint,
                    document_json=document_json,
                    created_at=now,
                )
            )
            return self._restore(inserted, session.user.id)

    def _restore(self, record: LocalRiskAssessmentRecord, user_id: str) -> LocalSavedRiskAssessment:
        try:
            if (
                record.user_id != user_id
                or re.fullmatch(UUID4_PATTERN, record.assessment_id) is None
                or re.fullmatch(UUID4_PATTERN, record.idempotency_key) is None
                or re.fullmatch(r"[0-9a-f]{64}", record.request_fingerprint) is None
                or type(record.sequence) is not int
                or not 1 <= record.sequence <= MAX_SEQUENCE
            ):
                raise ValueError("Stored risk record binding does not match.")
            document = _stored_json(record.document_json)
            if not isinstance(document, dict) or set(document) != DOCUMENT_FIELDS:
                raise ValueError("Stored risk document has an unsupported shape.")
            saved = LocalSavedRiskAssessment.model_validate(document, strict=True)
            if (
                document["persisted"] is not True
                or saved.assessment_id != record.assessment_id
                or _text_time(saved.created_at) != _time(record.created_at)
                or saved.assessment.calculated_at != saved.created_at
                or saved.explanation.calculated_at != saved.created_at
                or _fingerprint(saved.input) != record.request_fingerprint
                or _rules_hash(saved.rules_snapshot) != saved.rules_sha256
            ):
                raise ValueError("Stored risk document binding does not match.")
            # Verify against this record's rules/time, never today's source.
            engine = RiskScoringEngine.from_config(saved.rules_snapshot)
            expected = _result(saved.input, engine, saved.created_at)
            if expected.model_dump(mode="json") != saved.assessment.model_dump(mode="json"):
                raise ValueError("Stored risk result is inconsistent.")
            explanation = educational_explanation(
                expected.model_dump(mode="json", exclude_none=True)
            )
            if explanation != saved.explanation.model_dump(mode="json"):
                raise ValueError("Stored risk explanation is inconsistent.")
            return saved
        except Exception:
            raise LocalStoreUnavailable() from None

    def history(
        self, token: str, *, before: int | None = None, limit: int = 20
    ) -> LocalRiskHistory:
        if (
            type(limit) is not int
            or not 1 <= limit <= 50
            or (before is not None and (type(before) is not int or not 1 <= before <= MAX_SEQUENCE))
        ):
            raise FinExException(
                message="Request validation failed.", error_code="VALIDATION_ERROR", status_code=422
            )
        with authorized_transaction(self.store, token, self.clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            records = transaction.list_risk_assessments(
                session.user.id, before=before, limit=limit + 1
            )
            if len(records) > limit + 1:
                raise LocalStoreUnavailable()
            cursor = before or MAX_SEQUENCE + 1
            saved: list[LocalSavedRiskAssessment] = []
            for record in records:
                if type(record.sequence) is not int or not 0 < record.sequence < cursor:
                    raise LocalStoreUnavailable()
                saved.append(self._restore(record, session.user.id))
                cursor = record.sequence
            has_more = len(saved) > limit
            return LocalRiskHistory(
                items=saved[:limit],
                next_cursor=str(records[limit - 1].sequence) if has_more else None,
            )

    def assessment(self, token: str, assessment_id: str) -> LocalSavedRiskAssessment:
        if re.fullmatch(UUID4_PATTERN, assessment_id) is None:
            raise FinExException(
                message="Request validation failed.", error_code="VALIDATION_ERROR", status_code=422
            )
        with authorized_transaction(self.store, token, self.clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            record = transaction.get_risk_assessment(session.user.id, assessment_id)
            if record is None:
                raise _not_found()
            if record.assessment_id != assessment_id:
                raise LocalStoreUnavailable()
            return self._restore(record, session.user.id)
