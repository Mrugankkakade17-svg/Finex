"""
SQLAlchemy models for the versioned risk questionnaire workflow.

The risk questionnaire workflow consists of four entities:

- RiskQuestionnaire: versioned questionnaire definition.
- RiskQuestion: ordered questions belonging to a questionnaire version.
- RiskAssessment: a user's assessment against a specific questionnaire version.
- RiskAssessmentAnswer: an individual answer submitted for an assessment.

These models are intended for the operational PostgreSQL/Lakebase store.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.ports.adapters.lakebase import Base


class RiskQuestionnaire(Base):
    """Represents a versioned risk-assessment questionnaire."""

    __tablename__ = "risk_questionnaires"

    questionnaire_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    version_label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    active_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RiskQuestion(Base):
    """Represents an ordered question within a questionnaire version."""

    __tablename__ = "risk_questions"

    __table_args__ = (
        # A question position must be unique within a questionnaire version.
        # This prevents two questions from occupying the same position.
        UniqueConstraint(
            "questionnaire_id",
            "position",
            name="uq_risk_questions_questionnaire_position",
        ),
    )

    question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "risk_questionnaires.questionnaire_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    text_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    response_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    dimension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    answer_options: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )


class RiskAssessment(Base):
    """Represents a user's risk assessment against a specific version."""

    __tablename__ = "risk_assessments"

    assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "risk_questionnaires.questionnaire_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    willingness_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    capacity_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    total_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RiskAssessmentAnswer(Base):
    """Stores an individual answer submitted for a risk assessment."""

    __tablename__ = "risk_assessment_answers"

    __table_args__ = (
        # Each question can be answered only once per assessment.
        UniqueConstraint(
            "assessment_id",
            "question_id",
            name="uq_risk_assessment_answers_assessment_question",
        ),
    )

    answer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "risk_assessments.assessment_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "risk_questions.question_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    answer_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    numeric_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
