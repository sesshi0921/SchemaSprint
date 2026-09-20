from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemasprint_api.learner import (
    CommunityPostCreateModel,
    CommunityPostModel,
    FeedbackModel,
    ReportCreateModel,
    TranslatedContentModel,
)
from schemasprint_api.problems import Locale


def test_community_post_requires_a_bounded_explanation_and_ulid() -> None:
    with pytest.raises(ValidationError):
        CommunityPostCreateModel.model_validate(
            {"submissionId": "not-ulid", "explanation": "x"}
        )
    payload = CommunityPostCreateModel.model_validate(
        {
            "submissionId": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "explanation": "A complete design.",
        }
    )
    assert payload.explanation == "A complete design."


def test_public_content_models_preserve_api_schema_field() -> None:
    post = CommunityPostModel.model_validate(
        {
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
            "submissionId": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "authorDisplayName": "Learner",
            "explanation": "A complete design.",
            "originalExplanation": "A complete design.",
            "sourceLanguage": "en",
            "schema": {"schemaVersion": 1, "tables": [], "relationships": []},
            "moderationState": "approved",
            "problemVersion": 1,
        }
    )
    assert post.model_dump(mode="json", by_alias=True)["schema"]["schemaVersion"] == 1


def test_feedback_translation_and_report_are_strict() -> None:
    feedback = FeedbackModel(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAX",
        version=1,
        content="Feedback",
        contentEn="Feedback",
        translationStatus="unavailable",
        modelVersion="jev-unknown",
        createdAt=datetime.now(UTC),
    )
    assert feedback.sourceLanguage == "en"
    translated = TranslatedContentModel(
        contentKind="feedback",
        contentId=feedback.id,
        contentVersion=1,
        locale=Locale.JA,
        sourceEn=feedback.contentEn,
        content=feedback.contentEn,
        status="pending",
        identifiersPreserved=True,
    )
    assert translated.status == "pending"
    report = ReportCreateModel(
        category="grading", targetId=feedback.id, description="Review this result."
    )
    assert report.category == "grading"
