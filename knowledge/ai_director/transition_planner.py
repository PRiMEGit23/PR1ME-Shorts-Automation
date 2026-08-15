"""Transition planner: the cut grammar between scenes.

Chooses the transition INTO each scene from the emotional delta (fade into
a peak), the comparison emphasis (dissolve to a comparison), and the pacing
(wipe to a fast beat); everything else is a continuity cut.
"""

from __future__ import annotations

from knowledge.ai_director.director_rules import transition_between
from knowledge.visual_intelligence.storyboard import Transition


class TransitionPlanner:
    """Deterministic transition grammar for one plan."""

    def plan(
        self,
        emotions: dict[int, int],
        comparison_emphasis: dict[int, int],
        pacing: dict[int, int],
    ) -> dict[int, Transition]:
        """The transition INTO each scene, keyed by 1-based scene index."""
        transitions: dict[int, Transition] = {}
        for index in emotions:
            transitions[index] = transition_between(
                emotions[index],
                comparison_emphasis=comparison_emphasis.get(index, 3),
                pacing=pacing.get(index, 5),
                is_first=index == 1,
            )
        return transitions
