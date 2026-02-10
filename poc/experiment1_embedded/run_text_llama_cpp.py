"""Experiment 1: Text mode with llama-cpp-python (Qwen2.5-3B).

Camera -> Feature JSON -> llama-cpp-python for state classification.
Uses Metal GPU acceleration on Apple Silicon.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from typing import Final

from llama_cpp import Llama

from shared.camera import CameraCapture
from shared.features import FeatureTracker, extract_frame_features
from shared.metrics import MetricsCollector
from shared.prompts import TEXT_SYSTEM_PROMPT, format_text_prompt
from shared.rule_classifier import classify_camera_text

DEFAULT_MODEL_PATH: Final[str] = str(
    Path(__file__).parent.parent / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf"
)
DEFAULT_DURATION: Final[int] = 60
DEFAULT_INTERVAL: Final[int] = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 1: Text mode with llama-cpp-python",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to GGUF model file (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help=f"Total runtime in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"LLM call interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--n-ctx",
        type=int,
        default=2048,
        help="Context window size (default: 2048)",
    )
    return parser.parse_args()


def load_model(model_path: str, n_ctx: int) -> Llama:
    """Load Qwen2.5-3B model with Metal GPU acceleration."""
    print(f"Loading model from {model_path}...")
    model = Llama(
        model_path=model_path,
        n_gpu_layers=-1,
        n_ctx=n_ctx,
        verbose=False,
    )
    print("Model loaded successfully.")
    return model


def run_inference(model: Llama, user_prompt: str) -> dict:
    """Run text inference and return parsed result."""
    response = model.create_chat_completion(
        messages=[
            {"role": "system", "content": TEXT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=256,
        temperature=0.1,
    )
    content = response["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": content, "parse_error": True}


def create_shutdown_handler(should_run: list[bool]):
    """Create a signal handler that sets should_run[0] to False."""
    def handler(_signum, _frame):
        print("\nShutting down...")
        should_run[0] = False
    return handler


def main() -> None:
    args = parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists():
        print(f"Error: Model file not found at {model_path}")
        print("Run 'python download_models.py' first.")
        sys.exit(1)

    model = load_model(str(model_path), args.n_ctx)
    tracker = FeatureTracker()
    metrics = MetricsCollector()

    should_run = [True]
    signal.signal(signal.SIGINT, create_shutdown_handler(should_run))

    print(f"\nRunning for {args.duration}s with {args.interval}s LLM interval...")
    print("-" * 60)

    start_time = time.monotonic()
    last_llm_call = 0.0

    with CameraCapture() as camera:
        metrics.start()

        while should_run[0]:
            elapsed = time.monotonic() - start_time
            if elapsed >= args.duration:
                break

            with metrics.measure_frame():
                frame_result = camera.read_frame()

            frame_features = extract_frame_features(
                frame_result.landmarks,
                frame_result.timestamp,
            )
            snapshot = tracker.update(frame_features)

            now = time.monotonic()
            if now - last_llm_call >= args.interval:
                last_llm_call = now

                # Try rule-based classification first
                rule_result = classify_camera_text(snapshot.to_dict())
                if rule_result is not None:
                    result = {
                        "state": rule_result.state,
                        "confidence": rule_result.confidence,
                        "reasoning": f"[rule] {rule_result.reasoning}",
                    }
                else:
                    features_json = snapshot.to_json()
                    user_prompt = format_text_prompt(features_json)

                    with metrics.measure_llm():
                        result = run_inference(model, user_prompt)

                llm_summary = metrics.get_summary()
                remaining = args.duration - elapsed
                print(
                    f"[{elapsed:5.1f}s / {args.duration}s] "
                    f"State: {result.get('state', 'unknown'):12s} | "
                    f"LLM: {llm_summary.avg_llm_latency_ms:.0f}ms | "
                    f"FPS: {llm_summary.fps:.1f} | "
                    f"Remaining: {remaining:.0f}s"
                )

            time.sleep(0.01)

    summary = metrics.get_summary()
    print("\n" + "=" * 60)
    print("RESULTS: Experiment 1 - Text Mode (llama-cpp-python)")
    print("=" * 60)
    summary.print_report()


if __name__ == "__main__":
    main()
