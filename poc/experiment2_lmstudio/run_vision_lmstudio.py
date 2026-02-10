"""Experiment 2: Vision mode with LM Studio API.

Camera frame -> base64 data URI -> LM Studio Vision API for state classification.
Requires LM Studio running locally with a vision model loaded.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from typing import Final

import openai

from shared.camera import CameraCapture
from shared.metrics import MetricsCollector
from shared.prompts import build_vision_prompt

DEFAULT_BASE_URL: Final[str] = "http://localhost:1234/v1"
DEFAULT_API_KEY: Final[str] = "lm-studio"
DEFAULT_DURATION: Final[int] = 120
DEFAULT_INTERVAL: Final[int] = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 2: Vision mode with LM Studio",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"LM Studio API base URL (default: {DEFAULT_BASE_URL})",
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
    return parser.parse_args()


def check_lmstudio_connection(client: openai.OpenAI) -> bool:
    """Verify LM Studio is running and a vision model is loaded."""
    try:
        models = client.models.list()
        model_list = list(models)
        if not model_list:
            print("Error: LM Studio is running but no model is loaded.")
            print("Please load a vision-capable model in LM Studio first.")
            return False
        print(f"Connected to LM Studio. Available models:")
        for m in model_list:
            print(f"  - {m.id}")
        print("\nNote: Ensure a vision-capable model is loaded for image analysis.")
        return True
    except openai.APIConnectionError:
        print(f"Error: Cannot connect to LM Studio.")
        print("Please ensure LM Studio is running with the server enabled.")
        return False


def run_vision_inference(client: openai.OpenAI, base64_image: str, prompt: str) -> dict:
    """Run vision inference via LM Studio API with base64 image."""
    data_uri = f"data:image/jpeg;base64,{base64_image}"

    response = client.chat.completions.create(
        model="default",
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
    content = response.choices[0].message.content
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

    client = openai.OpenAI(
        base_url=args.base_url,
        api_key=DEFAULT_API_KEY,
    )

    if not check_lmstudio_connection(client):
        sys.exit(1)

    camera = CameraCapture()
    metrics = MetricsCollector(experiment_name="exp2_vision_lmstudio")

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
                try:
                    result = run_vision_inference(client, base64_image, prompt)
                except openai.APIConnectionError:
                    print(f"[{elapsed:5.1f}s] LM Studio connection lost, retrying...")
                    continue
                except openai.APIError as e:
                    print(f"[{elapsed:5.1f}s] API error: {e}")
                    continue
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
        print("RESULTS: Experiment 2 - Vision Mode (LM Studio)")
        print("=" * 60)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
