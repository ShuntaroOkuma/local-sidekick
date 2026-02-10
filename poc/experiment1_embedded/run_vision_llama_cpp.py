"""Experiment 1: Vision mode with llama-cpp-python (Qwen2-VL-2B).

Camera frame -> base64 JPEG -> llama-cpp-python vision model for state classification.
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
from shared.metrics import MetricsCollector
from shared.prompts import build_vision_prompt

DEFAULT_MODEL_PATH: Final[str] = str(
    Path.home() / ".cache" / "local-sidekick" / "models" / "qwen2-vl-2b-instruct-q4_k_m.gguf"
)
DEFAULT_CLIP_MODEL_PATH: Final[str] = str(
    Path.home() / ".cache" / "local-sidekick" / "models" / "qwen2-vl-2b-instruct-mmproj.gguf"
)
DEFAULT_DURATION: Final[int] = 120
DEFAULT_INTERVAL: Final[int] = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 1: Vision mode with llama-cpp-python",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to GGUF model file (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--clip-model-path",
        type=str,
        default=DEFAULT_CLIP_MODEL_PATH,
        help=f"Path to CLIP/mmproj GGUF file (default: {DEFAULT_CLIP_MODEL_PATH})",
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
        default=4096,
        help="Context window size (default: 4096)",
    )
    return parser.parse_args()


def load_model(model_path: str, clip_model_path: str, n_ctx: int) -> Llama:
    """Load Qwen2-VL-2B model with vision support and Metal GPU."""
    print(f"Loading vision model from {model_path}...")
    print(f"Loading CLIP model from {clip_model_path}...")

    clip_path = Path(clip_model_path)
    if not clip_path.exists():
        print(f"Warning: CLIP model not found at {clip_model_path}")
        print("Vision capabilities may be limited.")

    model = Llama(
        model_path=model_path,
        chat_handler=None,
        n_gpu_layers=-1,
        n_ctx=n_ctx,
        verbose=False,
    )
    print("Vision model loaded successfully.")
    return model


def run_vision_inference(model: Llama, base64_image: str, prompt: str) -> dict:
    """Run vision inference with base64-encoded image."""
    data_uri = f"data:image/jpeg;base64,{base64_image}"

    response = model.create_chat_completion(
        messages=[
            {
                "role": "system",
                "content": "You are a state classification assistant analyzing webcam images. Always respond in JSON.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                ],
            },
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

    model = load_model(str(model_path), args.clip_model_path, args.n_ctx)
    camera = CameraCapture()
    metrics = MetricsCollector(experiment_name="exp1_vision_llama_cpp")

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
            frame, _landmarks = camera.read_frame()
            frame_time = time.time() - frame_start
            metrics.record_frame(frame_time)

            now = time.time()
            if now - last_llm_call >= args.interval:
                last_llm_call = now

                base64_image = camera.get_frame_as_base64()
                if base64_image is None:
                    print(f"[{elapsed:5.1f}s] No frame available, skipping...")
                    continue

                prompt = build_vision_prompt()

                llm_start = time.time()
                result = run_vision_inference(model, base64_image, prompt)
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
        print("RESULTS: Experiment 1 - Vision Mode (llama-cpp-python)")
        print("=" * 60)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
