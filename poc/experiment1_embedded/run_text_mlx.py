"""Experiment 1: Text mode with mlx-lm (Qwen2.5-3B-4bit).

Camera -> Feature JSON -> mlx-lm for state classification.
Optimized for Apple Silicon with MLX framework.
"""

from __future__ import annotations

import argparse
import json
import signal
import time
from typing import Final

import mlx_lm
from mlx_lm.sample_utils import make_sampler

from shared.camera import CameraCapture
from shared.features import FeatureTracker, extract_frame_features
from shared.metrics import MetricsCollector
from shared.prompts import TEXT_SYSTEM_PROMPT, format_text_prompt
from shared.rule_classifier import classify_camera_text

DEFAULT_MODEL_NAME: Final[str] = "mlx-community/Qwen2.5-3B-Instruct-4bit"
DEFAULT_DURATION: Final[int] = 60
DEFAULT_INTERVAL: Final[int] = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 1: Text mode with mlx-lm",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f"MLX model name or path (default: {DEFAULT_MODEL_NAME})",
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
        "--max-tokens",
        type=int,
        default=256,
        help="Maximum tokens to generate (default: 256)",
    )
    return parser.parse_args()


def load_model(model_name: str) -> tuple:
    """Load MLX model and tokenizer."""
    print(f"Loading MLX model: {model_name}...")
    model, tokenizer = mlx_lm.load(model_name)
    print("Model loaded successfully.")
    return model, tokenizer


def run_inference(model, tokenizer, user_prompt: str, max_tokens: int) -> dict:
    """Run text inference with mlx-lm and return parsed result."""
    messages = [
        {"role": "system", "content": TEXT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        formatted_prompt = (
            f"<|im_start|>system\n{TEXT_SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    response = mlx_lm.generate(
        model,
        tokenizer,
        prompt=formatted_prompt,
        max_tokens=max_tokens,
        sampler=make_sampler(temp=0.1),
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"raw_response": response, "parse_error": True}


def create_shutdown_handler(should_run: list[bool]):
    """Create a signal handler that sets should_run[0] to False."""
    def handler(_signum, _frame):
        print("\nShutting down...")
        should_run[0] = False
    return handler


def main() -> None:
    args = parse_args()

    model, tokenizer = load_model(args.model_name)
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
                        result = run_inference(model, tokenizer, user_prompt, args.max_tokens)

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
    print("RESULTS: Experiment 1 - Text Mode (mlx-lm)")
    print("=" * 60)
    summary.print_report()


if __name__ == "__main__":
    main()
