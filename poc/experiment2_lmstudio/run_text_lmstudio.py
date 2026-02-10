"""Experiment 2: Text mode with LM Studio API.

Camera -> Feature JSON -> LM Studio OpenAI-compatible API for state classification.
Requires LM Studio running locally with a model loaded.
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
from shared.features import FeatureTracker, extract_frame_features
from shared.metrics import MetricsCollector
from shared.prompts import TEXT_SYSTEM_PROMPT, format_text_prompt
from shared.rule_classifier import classify_camera_text

DEFAULT_BASE_URL: Final[str] = "http://localhost:1234/v1"
DEFAULT_API_KEY: Final[str] = "lm-studio"
DEFAULT_DURATION: Final[int] = 60
DEFAULT_INTERVAL: Final[int] = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Experiment 2: Text mode with LM Studio",
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
    """Verify LM Studio is running and a model is loaded."""
    try:
        models = client.models.list()
        model_list = list(models)
        if not model_list:
            print("Error: LM Studio is running but no model is loaded.")
            print("Please load a model in LM Studio first.")
            return False
        print("Connected to LM Studio. Available models:")
        for m in model_list:
            print(f"  - {m.id}")
        return True
    except openai.APIConnectionError:
        print("Error: Cannot connect to LM Studio.")
        print("Please ensure LM Studio is running with the server enabled.")
        return False


def run_inference(client: openai.OpenAI, user_prompt: str) -> dict:
    """Run text inference via LM Studio API and return parsed result."""
    response = client.chat.completions.create(
        model="default",
        messages=[
            {"role": "system", "content": TEXT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
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

                    try:
                        with metrics.measure_llm():
                            result = run_inference(client, user_prompt)
                    except openai.APIConnectionError:
                        print(f"[{elapsed:5.1f}s] LM Studio connection lost, retrying...")
                        continue
                    except openai.APIError as e:
                        print(f"[{elapsed:5.1f}s] API error: {e}")
                        continue

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
    print("RESULTS: Experiment 2 - Text Mode (LM Studio)")
    print("=" * 60)
    summary.print_report()


if __name__ == "__main__":
    main()
