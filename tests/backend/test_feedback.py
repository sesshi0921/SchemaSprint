import pytest
from schemasprint_api.feedback import FeedbackOutputError, parse_feedback_output


def test_feedback_output_accepts_only_known_rubric_ids() -> None:
    result = parse_feedback_output(
        '{"contentEn":"Improve the relationship cardinality.",'
        '"mentionedRequirementIds":["r1"]}',
        allowed_requirement_ids={"r1", "r2"},
    )
    assert result.contentEn.startswith("Improve")


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"contentEn":"ok","unexpected":true}',
        '{"contentEn":"ok","mentionedRequirementIds":["unknown"]}',
    ],
)
def test_feedback_output_rejects_malformed_or_unknown_content(raw: str) -> None:
    with pytest.raises(FeedbackOutputError, match="LLM_INVALID_OUTPUT"):
        parse_feedback_output(raw, allowed_requirement_ids={"r1"})
