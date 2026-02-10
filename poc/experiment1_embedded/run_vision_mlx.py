"""Experiment 1: Vision mode with mlx-vlm (Qwen2-VL-2B-4bit).

Camera frame -> PIL Image -> mlx-vlm for state classification.
Optimized for Apple Silicon with MLX framework.
"""

from __future__ import annotations

import argparse
import json
import signal
import time
from typing import Final

import cv2
import numpy as np
from PIL import Image

from shared.camera import CameraCapture
from shared.metrics import MetricsCollector
from shared.prompts import VISION_USER_PROMPT
from shared.rule_classifier import classify_camera_vision

DEFAULT_MODEL_NAME: Final[str] = "mlx-community/Qwen2-VL-2B-Instruct-4bit"
DEFAULT_DURATION: Final[int] = 120
DEFAULT_INTERVAL: Final[int] = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 1: Vision mode with mlx-vlm",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f"MLX vision model name or path (default: {DEFAULT_MODEL_NAME})",
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
    """Load MLX vision model and processor."""
    print(f"Loading MLX vision model: {model_name}...")
    from mlx_vlm import load as vlm_load

    model, processor = vlm_load(model_name)
    print("Vision model loaded successfully.")
    return model, processor


def frame_to_pil(frame: np.ndarray) -> Image.Image:
    """Convert BGR OpenCV frame to RGB PIL Image."""
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_frame)


def run_vision_inference(
    model,
    processor,
    image: Image.Image,
    max_tokens: int,
) -> dict:
    """Run vision inference with mlx-vlm and return parsed result."""
    from mlx_vlm import generate as vlm_generate

    result = vlm_generate(
        model,
        processor,
        prompt=VISION_USER_PROMPT,
        image=image,
        max_tokens=max_tokens,
        temperature=0.1,
    )

    # mlx_vlm returns (text, stats_dict) tuple
    response = result[0] if isinstance(result, tuple) else result

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

    model, processor = load_model(args.model_name)
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

            now = time.monotonic()
            if now - last_llm_call >= args.interval:
                last_llm_call = now

                # Rule-based pre-check: skip VLM if no face detected
                rule_result = classify_camera_vision(frame_result.face_detected)
                if rule_result is not None:
                    result = {
                        "state": rule_result.state,
                        "confidence": rule_result.confidence,
                        "reasoning": f"[rule] {rule_result.reasoning}",
                    }
                else:
                    if frame_result.frame is None:
                        print(f"[{elapsed:5.1f}s] No frame available, skipping...")
                        continue

                    pil_image = frame_to_pil(frame_result.frame)

                    with metrics.measure_llm():
                        result = run_vision_inference(
                            model, processor, pil_image, args.max_tokens
                        )

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
    print("RESULTS: Experiment 1 - Vision Mode (mlx-vlm)")
    print("=" * 60)
    summary.print_report()


if __name__ == "__main__":
    main()
