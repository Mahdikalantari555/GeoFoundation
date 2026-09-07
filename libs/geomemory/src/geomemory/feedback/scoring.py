"""MemoryScorer — rule-based confidence scoring 0–20."""

from __future__ import annotations

from typing import Any


class MemoryScorer:
    """Compute confidence from multi-signal feedback.

    Rules (spec):
      base 5 +3 per confirming (+6 cap) +2 per retrieval usage (+4 cap)
      +3 if multiple actors agree (+3 cap) -5 per rejection -3 per contradictory
    Thresholds: >=14 verified, >=8 supported, else proposed.
    """

    def score(
        self,
        *,
        confirming: int = 0,
        retrieval_usage: int = 0,
        multiple_actors: bool = False,
        rejections: int = 0,
        contradictions: int = 0,
        base: float = 5.0,
    ) -> float:
        s = base
        s += min(confirming * 3, 6)
        s += min(retrieval_usage * 2, 4)
        if multiple_actors:
            s += 3
        s -= rejections * 5
        s -= contradictions * 3
        return float(max(0.0, min(20.0, s)))

    def state_for(self, score: float) -> str:
        if score >= 14:
            return "verified"
        if score >= 8:
            return "supported"
        return "proposed"

    def compute_from_payload(self, payload: dict[str, Any]) -> float:
        return self.score(
            confirming=int(payload.get("confirming", 0)),
            retrieval_usage=int(payload.get("retrieval_usage", 0)),
            multiple_actors=bool(payload.get("multiple_actors", False)),
            rejections=int(payload.get("rejections", 0)),
            contradictions=int(payload.get("contradictions", 0)),
        )

    def weight_for_state(self, state: str) -> float:
        return {"verified": 0.8, "supported": 0.4, "proposed": 0.1}.get(state, 0.1)
