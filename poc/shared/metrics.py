"""Performance metrics collection for PoC experiments.

Tracks FPS, frame processing time, LLM latency, CPU usage, and memory usage.
Produces summary reports for comparing experiment variants.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass(frozen=True)
class MetricsSummary:
    """Summary of collected performance metrics."""

    duration_seconds: float
    total_frames: int
    fps: float
    avg_frame_time_ms: float
    p95_frame_time_ms: float
    llm_call_count: int
    avg_llm_latency_ms: float
    p95_llm_latency_ms: float
    cpu_percent: float
    memory_mb: float

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "duration_seconds": round(self.duration_seconds, 1),
            "total_frames": self.total_frames,
            "fps": round(self.fps, 1),
            "avg_frame_time_ms": round(self.avg_frame_time_ms, 1),
            "p95_frame_time_ms": round(self.p95_frame_time_ms, 1),
            "llm_call_count": self.llm_call_count,
            "avg_llm_latency_ms": round(self.avg_llm_latency_ms, 1),
            "p95_llm_latency_ms": round(self.p95_llm_latency_ms, 1),
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def print_report(self) -> None:
        """Print a formatted performance report."""
        print("\n=== Performance Report ===")
        print(f"  Duration:          {self.duration_seconds:.1f}s")
        print(f"  Total frames:      {self.total_frames}")
        print(f"  FPS:               {self.fps:.1f}")
        print(f"  Frame time (avg):  {self.avg_frame_time_ms:.1f}ms")
        print(f"  Frame time (P95):  {self.p95_frame_time_ms:.1f}ms")
        print(f"  LLM calls:         {self.llm_call_count}")
        print(f"  LLM latency (avg): {self.avg_llm_latency_ms:.1f}ms")
        print(f"  LLM latency (P95): {self.p95_llm_latency_ms:.1f}ms")
        print(f"  CPU usage:         {self.cpu_percent:.1f}%")
        print(f"  Memory:            {self.memory_mb:.1f}MB")
        print("==========================\n")


class MetricsCollector:
    """Collects and aggregates performance metrics during experiments.

    Usage:
        metrics = MetricsCollector()
        metrics.start()

        # In frame processing loop:
        with metrics.measure_frame():
            process_frame()

        # When calling LLM:
        with metrics.measure_llm():
            response = call_llm()

        summary = metrics.get_summary()
        summary.print_report()
    """

    def __init__(self, max_samples: int = 10000) -> None:
        self._max_samples = max_samples
        self._frame_times: deque[float] = deque(maxlen=max_samples)
        self._llm_latencies: deque[float] = deque(maxlen=max_samples)
        self._cpu_samples: deque[float] = deque(maxlen=max_samples)
        self._start_time: Optional[float] = None
        self._frame_count = 0
        self._llm_count = 0
        self._process = psutil.Process()

    def start(self) -> None:
        """Mark the start of metrics collection."""
        self._start_time = time.monotonic()
        # Initial CPU measurement (first call returns 0.0)
        self._process.cpu_percent()

    def measure_frame(self) -> _TimingContext:
        """Context manager to measure frame processing time.

        Usage:
            with metrics.measure_frame():
                process_frame()
        """
        return _TimingContext(self._record_frame_time)

    def measure_llm(self) -> _TimingContext:
        """Context manager to measure LLM call latency.

        Usage:
            with metrics.measure_llm():
                response = call_llm()
        """
        return _TimingContext(self._record_llm_latency)

    def record_frame(self) -> None:
        """Record a frame without timing (for simple frame counting)."""
        self._frame_count += 1
        self._sample_cpu()

    def get_summary(self) -> MetricsSummary:
        """Compute and return a summary of all collected metrics."""
        if self._start_time is None:
            duration = 0.0
        else:
            duration = time.monotonic() - self._start_time

        fps = self._frame_count / max(duration, 0.001)

        avg_frame_ms = _avg_ms(self._frame_times)
        p95_frame_ms = _percentile_ms(self._frame_times, 95)

        avg_llm_ms = _avg_ms(self._llm_latencies)
        p95_llm_ms = _percentile_ms(self._llm_latencies, 95)

        cpu_pct = _avg(self._cpu_samples) if self._cpu_samples else 0.0
        memory_mb = self._process.memory_info().rss / (1024 * 1024)

        return MetricsSummary(
            duration_seconds=duration,
            total_frames=self._frame_count,
            fps=fps,
            avg_frame_time_ms=avg_frame_ms,
            p95_frame_time_ms=p95_frame_ms,
            llm_call_count=self._llm_count,
            avg_llm_latency_ms=avg_llm_ms,
            p95_llm_latency_ms=p95_llm_ms,
            cpu_percent=cpu_pct,
            memory_mb=memory_mb,
        )

    def _record_frame_time(self, elapsed: float) -> None:
        """Record a frame processing duration."""
        self._frame_times.append(elapsed)
        self._frame_count += 1
        self._sample_cpu()

    def _record_llm_latency(self, elapsed: float) -> None:
        """Record an LLM call duration."""
        self._llm_latencies.append(elapsed)
        self._llm_count += 1

    def _sample_cpu(self) -> None:
        """Sample current CPU usage."""
        try:
            cpu = self._process.cpu_percent()
            if cpu > 0:
                self._cpu_samples.append(cpu)
        except psutil.Error:
            pass


class _TimingContext:
    """Context manager that measures elapsed time and calls a callback."""

    def __init__(self, callback) -> None:  # noqa: ANN001
        self._callback = callback
        self._start: float = 0.0

    def __enter__(self) -> _TimingContext:
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        elapsed = time.monotonic() - self._start
        self._callback(elapsed)


def _avg(values: deque[float]) -> float:
    """Compute average of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _avg_ms(values: deque[float]) -> float:
    """Compute average in milliseconds."""
    return _avg(values) * 1000.0


def _percentile_ms(values: deque[float], percentile: int) -> float:
    """Compute percentile value in milliseconds."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = int(len(sorted_values) * percentile / 100)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx] * 1000.0
