"""Image QA: evaluates every generated image before it is accepted.

The QA engine sits above the render step. It compares what the vision
pipeline observed (GeneratedImageMetadata) against what was planned (the
EducationalPlan, the VisualStoryboard, and the CompiledPrompt), aggregates
eight scores, decides pass/fail against fixed thresholds, and returns
deterministic repair instructions - it never re-renders anything.
"""

from knowledge.image_qa.engineering_critic import QAContext
from knowledge.image_qa.image_critic import ImageCritic
from knowledge.image_qa.qa_models import (
    IMAGE_QA_VERSION,
    CriticVerdict,
    GeneratedImageMetadata,
    ImageQualityReport,
    IssueSeverity,
    PassFail,
    QACheck,
    QAIssue,
)
from knowledge.image_qa.render_repair import RenderRepairEngine

__all__ = [
    "IMAGE_QA_VERSION",
    "CriticVerdict",
    "GeneratedImageMetadata",
    "ImageCritic",
    "ImageQualityReport",
    "IssueSeverity",
    "PassFail",
    "QAContext",
    "QACheck",
    "QAIssue",
    "RenderRepairEngine",
]