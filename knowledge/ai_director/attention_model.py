"""Attention model: predict where eyes will be, before a single render.

Predicts, per scene, the expected viewer attention (0-100, peak-normalized
so the strongest scene scores 100) and the retention score (0-100) from
the director's own decisions - importance, emotion, pacing, reveal order,
motion, and structural roles. Also yields the film-level predicted
attention and the importance-weighted predicted retention.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.ai_director.director_rules import attention_raw, retention_score
from knowledge.ai_director.visual_budget import VisualBudget


@dataclass(frozen=True)
class AttentionPrediction:
    """Predicted attention and retention for the whole film."""

    expected_attention: dict[int, float]
    retention_scores: dict[int, float]
    predicted_attention: float
    predicted_retention: float


class AttentionModel:
    """Deterministic attention / retention prediction from the brief."""

    def predict(
        self,
        *,
        importances: dict[int, int],
        emotions: dict[int, int],
        pacing: dict[int, int],
        reveal_orders: dict[int, int],
        budgets: dict[int, VisualBudget],
        hero_index: int,
        thumbnail_index: int,
    ) -> AttentionPrediction:
        """Predict attention and retention for one complete brief."""
        raw = {
            index: attention_raw(
                importances[index],
                emotions[index],
                pacing[index],
                reveal_orders[index],
                motion_budget=budgets[index].motion_budget,
                is_hero=index == hero_index,
                is_thumbnail=index == thumbnail_index,
            )
            for index in importances
        }
        peak = max(raw.values())
        expected = {
            index: round(value * 100.0 / peak, 1) if peak > 0 else 0.0
            for index, value in raw.items()
        }
        retentions = {
            index: retention_score(
                importances[index],
                emotions[index],
                pacing[index],
                budgets[index].visual_budget,
            )
            for index in importances
        }
        weight_total = sum(importances.values())
        predicted_retention = round(
            sum(retentions[index] * importances[index] for index in retentions)
            / weight_total,
            1,
        )
        return AttentionPrediction(
            expected_attention=expected,
            retention_scores=retentions,
            predicted_attention=round(
                sum(expected.values()) / len(expected), 1
            ),
            predicted_retention=predicted_retention,
        )
