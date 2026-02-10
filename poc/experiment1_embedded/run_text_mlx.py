"""Experiment 1: Text mode with mlx-lm (Qwen2.5-3B-4bit).

Camera -> Feature JSON -> mlx-lm for state classification.
Optimized for Apple Silicon with MLX framework.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from typing import Final

import mlx_lm

from shared.camera import CameraCapture
from shared.features import FeatureTracker
from shared.metrics import MetricsCollector
from shared.prompts import build_text_prompt

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


def run_inference(model, tokenizer, prompt: str, max_tokens: int) -> dict:
    """Run text inference with mlx-lm and return parsed result."""
    messages = [
        {"role": "system", "content": "You are a state classification assistant. Always respond in JSON."},
        {"role": "user", "content": prompt},
    ]

    if hasattr(tokenizer, "apply_chat_template"):
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        formatted_prompt = f"<|im_start|>system\nYou are a state classification assistant. Always respond in JSON.<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

    response = mlx_lm.generate(
        model,
        tokenizer,
        prompt=formatted_prompt,
        max_tokens=max_tokens,
        temp=0.1,
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
    camera = CameraCapture()
    tracker = FeatureTracker()
    metrics = MetricsCollector(experiment_name="exp1_text_mlx")

    should_run = [True]
    signal.signal(signal.SIGINT, create_shutdown_handler(should_run))

    print(f"\nRunning for {args.duration}s with {args.interval}s LLM interval...")
    print("-" * 60)

    start_time = time.time()
    last_llm_call = 0.0

    try:
        camera.start()

        while should_run[0]:
            elapsed = time.time() - start_time
            if elapsed >= args.duration:
                break

            frame_start = time.time()
            frame, landmarks = camera.read_frame()
            frame_time = time.time() - frame_start
            metrics.record_frame(frame_time)

            if landmarks is not None:
                features = tracker.update(landmarks)
            else:
                features = tracker.get_no_face_features()

            now = time.time()
            if now - last_llm_call >= args.interval:
                last_llm_call = now
                prompt = build_text_prompt(features)

                llm_start = time.time()
                result = run_inference(model, tokenizer, prompt, args.max_tokens)
                llm_time = time.time() - llm_start
                metrics.record_llm_call(llm_time)

                remaining = args.duration - elapsed
                print(
                    f"[{elapsed:5.1f}s / {args.duration}s] "
                    f"State: {result.get('state', 'unknown'):12s} | "
                    f"LLM: {llm_time:.2f}s | "
                    f"FPS: {metrics.current_fps:.1f} | "
                    f"Remaining: {remaining:.0f}s"
                )

            time.sleep(0.01)

    finally:
        camera.stop()
        summary = metrics.get_summary()
        print("\n" + "=" * 60)
        print("RESULTS: Experiment 1 - Text Mode (mlx-lm)")
        print("=" * 60)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
