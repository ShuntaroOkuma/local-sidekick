"""Result collection and persistence for all experiments.

Provides a lightweight collector that accumulates per-interval
classification results and writes them to JSON files under results/.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).parent.parent / "results"


@dataclass(frozen=True)
class AnalysisEntry:
    """Single classification result at one interval."""

    analysis_number: int
    elapsed_seconds: float
    state: str
    confidence: float
    reasoning: str
    source: str  # "rule" or "llm"
    latency_ms: float
    raw_response: str = ""
    features: Optional[dict] = None  # text mode only
    snapshot: Optional[dict] = None  # pc usage mode only


class ResultsCollector:
    """Accumulates analysis entries and saves them to a JSON file."""

    def __init__(self, experiment_name: str) -> None:
        self._experiment_name = experiment_name
        self._entries: list[dict] = []
        self._count = 0

    def add(
        self,
        *,
        elapsed_seconds: float,
        state: str,
        confidence: float,
        reasoning: str,
        source: str = "llm",
        latency_ms: float = 0.0,
        raw_response: str = "",
        features: Optional[dict] = None,
        snapshot: Optional[dict] = None,
    ) -> None:
        """Record one classification result."""
        self._count += 1
        entry = {
            "analysis_number": self._count,
            "elapsed_seconds": round(elapsed_seconds, 1),
            "state": state,
            "confidence": confidence,
            "reasoning": reasoning,
            "source": source,
            "latency_ms": round(latency_ms, 1),
        }
        if raw_response:
            entry["raw_response"] = raw_response
        if features is not None:
            entry["features"] = features
        if snapshot is not None:
            entry["snapshot"] = snapshot
        self._entries.append(entry)

    @property
    def count(self) -> int:
        return self._count

    @property
    def entries(self) -> list[dict]:
        return list(self._entries)

    def save(self) -> Optional[Path]:
        """Write collected results to a timestamped JSON file.

        Returns the output file path, or None if no entries.
        """
        if not self._entries:
            return None

        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = RESULTS_DIR / f"{self._experiment_name}_{timestamp}.json"
        with open(output_file, "w") as f:
            json.dump(self._entries, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {output_file} ({self._count} entries)")
        return output_file
