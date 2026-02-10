"""PC usage analysis via LLM.

Monitors PC usage and sends periodic snapshots to an LLM for
state classification (focused / distracted / idle).

Usage:
    python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
    python -m experiment3_pcusage.run_analysis --backend llama_cpp --duration 300 --interval 30
    python -m experiment3_pcusage.run_analysis --backend mlx --duration 300 --interval 30
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from experiment3_pcusage.monitor import PCUsageMonitor, UsageSnapshot
from shared.metrics import MetricsCollector
from shared.prompts import PC_USAGE_SYSTEM_PROMPT, format_pc_usage_prompt
from shared.rule_classifier import classify_pc_usage


def build_analysis_prompt(snapshot: UsageSnapshot) -> str:
    """Build the user prompt from a snapshot."""
    usage_json = json.dumps(snapshot.to_dict(), indent=2)
    return format_pc_usage_prompt(usage_json)


# --- LLM Backends ---


@dataclass(frozen=True)
class LLMResult:
    """Immutable result from LLM analysis."""

    raw_response: str
    state: str
    confidence: float
    reasoning: str
    latency_ms: float


def _parse_llm_response(raw: str, latency_ms: float) -> LLMResult:
    """Parse LLM JSON response into a structured result."""
    # Try to extract JSON from the response
    text = raw.strip()

    # Handle responses wrapped in markdown code blocks
    if "```" in text:
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                json_lines.append(line)
        text = "\n".join(json_lines).strip()

    try:
        parsed = json.loads(text)
        return LLMResult(
            raw_response=raw,
            state=parsed.get("state", "unknown"),
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=parsed.get("reasoning", ""),
            latency_ms=latency_ms,
        )
    except (json.JSONDecodeError, ValueError):
        return LLMResult(
            raw_response=raw,
            state="unknown",
            confidence=0.0,
            reasoning=f"Failed to parse: {text[:200]}",
            latency_ms=latency_ms,
        )


def analyze_lmstudio(
    system_prompt: str,
    user_prompt: str,
    base_url: str = "http://localhost:1234/v1",
) -> LLMResult:
    """Send analysis request to LM Studio via OpenAI-compatible API."""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key="lm-studio")

    start = time.perf_counter()
    response = client.chat.completions.create(
        model="default",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    raw = response.choices[0].message.content or ""
    return _parse_llm_response(raw, latency_ms)


def analyze_llama_cpp(
    system_prompt: str,
    user_prompt: str,
    model_path: str | None = None,
) -> LLMResult:
    """Send analysis request to llama-cpp-python."""
    from llama_cpp import Llama

    if model_path is None:
        models_dir = Path(__file__).parent.parent / "models"
        model_path = str(
            models_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
        )

    # Use module-level cache to avoid reloading the model
    llm = _get_llama_model(model_path)

    start = time.perf_counter()
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    raw = response["choices"][0]["message"]["content"] or ""
    return _parse_llm_response(raw, latency_ms)


# Simple model cache (module-level)
_llama_model_cache: dict[str, object] = {}


def _get_llama_model(model_path: str) -> object:
    """Get or create a cached Llama model instance."""
    if model_path not in _llama_model_cache:
        from llama_cpp import Llama

        print(f"  Loading model: {model_path}")
        _llama_model_cache[model_path] = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=2048,
            verbose=False,
        )
    return _llama_model_cache[model_path]


def analyze_mlx(
    system_prompt: str,
    user_prompt: str,
    model_path: str | None = None,
) -> LLMResult:
    """Send analysis request to mlx-lm."""
    import mlx_lm
    from mlx_lm.sample_utils import make_sampler

    if model_path is None:
        models_dir = Path(__file__).parent.parent / "models"
        model_path = str(models_dir / "qwen2.5-3b-instruct-4bit")

    model, tokenizer = _get_mlx_model(model_path)

    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )

    start = time.perf_counter()
    raw = mlx_lm.generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=200,
        sampler=make_sampler(temp=0.1),
        verbose=False,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    return _parse_llm_response(raw, latency_ms)


# MLX model cache
_mlx_model_cache: dict[str, tuple] = {}


def _get_mlx_model(model_path: str) -> tuple:
    """Get or create a cached MLX model instance."""
    if model_path not in _mlx_model_cache:
        import mlx_lm

        print(f"  Loading MLX model: {model_path}")
        model, tokenizer = mlx_lm.load(model_path)
        _mlx_model_cache[model_path] = (model, tokenizer)
    return _mlx_model_cache[model_path]


# Backend dispatch
BACKENDS = {
    "lmstudio": analyze_lmstudio,
    "llama_cpp": analyze_llama_cpp,
    "mlx": analyze_mlx,
}


def _check_lmstudio_connection(base_url: str = "http://localhost:1234/v1") -> bool:
    """Check if LM Studio is running and reachable."""
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key="lm-studio")
        client.models.list()
        return True
    except Exception:
        return False


def run_analysis(
    backend: str,
    duration: int,
    interval: int,
) -> list[dict]:
    """Run PC usage monitoring with periodic LLM analysis.

    Returns list of analysis results.
    """
    if backend not in BACKENDS:
        print(f"[ERROR] Unknown backend: {backend}")
        print(f"  Available: {', '.join(BACKENDS.keys())}")
        return []

    # Pre-flight checks
    if backend == "lmstudio":
        print("Checking LM Studio connection...")
        if not _check_lmstudio_connection():
            print("[ERROR] Cannot connect to LM Studio at http://localhost:1234")
            print("  Make sure LM Studio is running with a model loaded.")
            return []
        print("[OK] LM Studio is reachable.\n")

    if backend == "llama_cpp":
        model_path = (
            Path(__file__).parent.parent
            / "models"
            / "qwen2.5-3b-instruct-q4_k_m.gguf"
        )
        if not model_path.exists():
            print(f"[ERROR] Model not found: {model_path}")
            print("  Run: python download_models.py --text-only")
            return []

    if backend == "mlx":
        model_path = (
            Path(__file__).parent.parent / "models" / "qwen2.5-3b-instruct-4bit"
        )
        if not (model_path / "config.json").exists():
            print(f"[ERROR] MLX model not found: {model_path}")
            print("  Run: python download_models.py --text-only")
            return []

    # Setup monitor
    monitor = PCUsageMonitor(window_seconds=60)
    print("Checking permissions...")
    permissions = monitor.check_permissions()
    monitor.print_permission_guidance(permissions)

    analyze_fn = BACKENDS[backend]

    print(f"\nStarting analysis: backend={backend}, duration={duration}s, interval={interval}s")
    print("Press Ctrl+C to stop early.\n")

    stop_event = threading.Event()

    def signal_handler(_sig: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    results: list[dict] = []
    metrics = MetricsCollector()
    metrics.start()
    monitor.start()

    try:
        start_time = time.time()
        analysis_count = 0

        while not stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break

            # Take snapshot
            snapshot = monitor.take_snapshot()
            snapshot_dict = snapshot.to_dict()
            analysis_count += 1

            print(f"[{elapsed:.0f}s] Analysis #{analysis_count}")
            print(f"  App: {snapshot.active_app}")
            print(f"  Idle: {snapshot.idle_seconds}s")
            print(f"  KB/min: {snapshot.keyboard_events_per_min}, Mouse/min: {snapshot.mouse_events_per_min}")
            print(f"  App switches: {snapshot.app_switches_in_window}, Unique apps: {snapshot.unique_apps_in_window}")

            # Try rule-based classification first
            rule_result = classify_pc_usage(snapshot_dict)
            if rule_result is not None:
                print(f"  -> State: {rule_result.state} (confidence: {rule_result.confidence:.2f})")
                print(f"     Reasoning: [rule] {rule_result.reasoning}")
                print(f"     Latency: 0ms (rule-based)")

                results.append({
                    "analysis_number": analysis_count,
                    "elapsed_seconds": round(elapsed, 1),
                    "snapshot": snapshot_dict,
                    "state": rule_result.state,
                    "confidence": rule_result.confidence,
                    "reasoning": f"[rule] {rule_result.reasoning}",
                    "latency_ms": 0.0,
                    "raw_response": "",
                    "source": "rule",
                })
            else:
                # Ambiguous case - use LLM
                user_prompt = build_analysis_prompt(snapshot)
                try:
                    with metrics.measure_llm():
                        result = analyze_fn(
                            system_prompt=PC_USAGE_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                        )
                    print(f"  -> State: {result.state} (confidence: {result.confidence:.2f})")
                    print(f"     Reasoning: {result.reasoning}")
                    print(f"     Latency: {result.latency_ms:.0f}ms")

                    results.append({
                        "analysis_number": analysis_count,
                        "elapsed_seconds": round(elapsed, 1),
                        "snapshot": snapshot_dict,
                        "state": result.state,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "latency_ms": round(result.latency_ms, 1),
                        "raw_response": result.raw_response,
                        "source": "llm",
                    })
                except Exception as e:
                    print(f"  [ERROR] LLM analysis failed: {e}")
                    results.append({
                        "analysis_number": analysis_count,
                        "elapsed_seconds": round(elapsed, 1),
                        "snapshot": snapshot_dict,
                        "state": "error",
                        "error": str(e),
                    })

            print()

            # Wait for next interval
            stop_event.wait(timeout=interval)
    finally:
        monitor.stop()

    # Print summaries
    _print_summary(results)
    metrics.get_summary().print_report()

    return results


def _print_summary(results: list[dict]) -> None:
    """Print a summary of the analysis results."""
    if not results:
        print("No results collected.")
        return

    print(f"\n{'=' * 60}")
    print(f"Analysis Summary ({len(results)} readings)")
    print(f"{'=' * 60}")

    states = [r.get("state", "error") for r in results]
    for state in ("focused", "distracted", "idle", "unknown", "error"):
        count = states.count(state)
        if count > 0:
            pct = count / len(states) * 100
            print(f"  {state:12s}: {count:3d} ({pct:5.1f}%)")

    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    if latencies:
        avg = sum(latencies) / len(latencies)
        p95_idx = int(len(latencies) * 0.95)
        sorted_lat = sorted(latencies)
        p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        print(f"\n  Avg latency:  {avg:.0f}ms")
        print(f"  P95 latency:  {p95:.0f}ms")

    print(f"{'=' * 60}\n")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="PC usage analysis via LLM",
    )
    parser.add_argument(
        "--backend",
        choices=list(BACKENDS.keys()),
        default="lmstudio",
        help="LLM backend (default: lmstudio)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Duration in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Analysis interval in seconds (default: 30)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for analysis CLI."""
    args = parse_args(argv)
    results = run_analysis(
        backend=args.backend,
        duration=args.duration,
        interval=args.interval,
    )

    # Save results to file
    if results:
        from shared.results import ResultsCollector

        collector = ResultsCollector(f"pcusage_{args.backend}")
        for r in results:
            collector.add(
                elapsed_seconds=r.get("elapsed_seconds", 0.0),
                state=r.get("state", "unknown"),
                confidence=r.get("confidence", 0.0),
                reasoning=r.get("reasoning", ""),
                source=r.get("source", "llm"),
                latency_ms=r.get("latency_ms", 0.0),
                raw_response=r.get("raw_response", ""),
                snapshot=r.get("snapshot"),
            )
        collector.save()

    return 0


if __name__ == "__main__":
    sys.exit(main())
