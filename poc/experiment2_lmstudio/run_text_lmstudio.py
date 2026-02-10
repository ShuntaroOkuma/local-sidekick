"""Experiment 2: Text mode via LM Studio.

Captures camera frames, extracts facial features, and sends the
feature JSON to LM Studio's OpenAI-compatible API for state classification.

Usage:
    python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Sequence

from openai import OpenAI

from shared.camera import CameraCapture
from shared.features import FeatureTracker, extract_frame_features
from shared.metrics import MetricsCollector
from shared.prompts import TEXT_SYSTEM_PROMPT, format_text_prompt

LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"


def check_lmstudio_connection(base_url: str = LM_STUDIO_BASE_URL) -> bool:
    """Verify LM Studio is running and reachable."""
    try:
        client = OpenAI(base_url=base_url, api_key=LM_STUDIO_API_KEY)
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"[OK] LM Studio connected. Available models: {model_ids}")
        return True
    except Exception as e:
        print(f"[ERROR] Cannot connect to LM Studio at {base_url}: {e}")
        print("  Make sure LM Studio is running with a text model loaded.")
        return False


def classify_state(
    client: OpenAI,
    features_json: str,
) -> dict:
    """Send feature JSON to LM Studio and parse the classification result."""
    user_prompt = format_text_prompt(features_json)

    start = time.perf_counter()
    response = client.chat.completions.create(
        model="default",
        messages=[
            {"role": "system", "content": TEXT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    raw = response.choices[0].message.content or ""
    return _parse_response(raw, latency_ms)


def _parse_response(raw: str, latency_ms: float) -> dict:
    """Parse LLM JSON response into a result dict."""
    text = raw.strip()

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
        return {
            "state": parsed.get("state", "unknown"),
            "confidence": float(parsed.get("confidence", 0.0)),
            "reasoning": parsed.get("reasoning", ""),
            "latency_ms": round(latency_ms, 1),
            "raw_response": raw,
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "state": "unknown",
            "confidence": 0.0,
            "reasoning": f"Failed to parse: {text[:200]}",
            "latency_ms": round(latency_ms, 1),
            "raw_response": raw,
        }


def run_experiment(
    duration: int,
    interval: int,
    base_url: str = LM_STUDIO_BASE_URL,
) -> list[dict]:
    """Run the text-mode LM Studio experiment.

    Returns list of analysis results.
    """
    if not check_lmstudio_connection(base_url):
        return []

    client = OpenAI(base_url=base_url, api_key=LM_STUDIO_API_KEY)
    metrics = MetricsCollector()
    tracker = FeatureTracker()

    stop_event = threading.Event()

    def signal_handler(_sig: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    results: list[dict] = []

    print(f"\nStarting Experiment 2 (text, LM Studio): duration={duration}s, interval={interval}s")
    print("Press Ctrl+C to stop early.\n")

    metrics.start()

    with CameraCapture() as cam:
        start_time = time.time()
        last_llm_call = 0.0
        call_count = 0

        while not stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break

            # Capture frame and extract features
            with metrics.measure_frame():
                result = cam.read_frame()
                features = extract_frame_features(
                    result.landmarks,
                    result.timestamp,
                    frame_width=result.frame.shape[1],
                    frame_height=result.frame.shape[0],
                )
                snapshot = tracker.update(features)

            # LLM call at specified interval
            if elapsed - last_llm_call >= interval:
                last_llm_call = elapsed
                call_count += 1

                features_json = snapshot.to_json()
                print(f"[{elapsed:.0f}s] Analysis #{call_count}")
                print(f"  Face: {snapshot.face_detected}")
                if snapshot.face_detected:
                    print(f"  EAR: {snapshot.ear_average}, PERCLOS: {snapshot.perclos}")
                    if snapshot.head_pose:
                        print(f"  Head: pitch={snapshot.head_pose.pitch:.1f}, yaw={snapshot.head_pose.yaw:.1f}")

                try:
                    with metrics.measure_llm():
                        llm_result = classify_state(client, features_json)

                    print(f"  -> State: {llm_result['state']} (confidence: {llm_result['confidence']:.2f})")
                    print(f"     Reasoning: {llm_result['reasoning']}")
                    print(f"     Latency: {llm_result['latency_ms']:.0f}ms")

                    results.append({
                        "call_number": call_count,
                        "elapsed_seconds": round(elapsed, 1),
                        "features": snapshot.to_dict(),
                        **llm_result,
                    })
                except Exception as e:
                    print(f"  [ERROR] LLM call failed: {e}")
                    results.append({
                        "call_number": call_count,
                        "elapsed_seconds": round(elapsed, 1),
                        "features": snapshot.to_dict(),
                        "state": "error",
                        "error": str(e),
                    })

                print()

            # Small sleep to avoid busy-waiting
            time.sleep(0.01)

    summary = metrics.get_summary()
    summary.print_report()

    # Save results
    if results:
        output_dir = Path(__file__).parent.parent / "results"
        output_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"exp2_text_lmstudio_{timestamp}.json"
        with open(output_file, "w") as f:
            json.dump(
                {"results": results, "metrics": summary.to_dict()},
                f,
                indent=2,
            )
        print(f"Results saved to {output_file}")

    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Experiment 2: Text mode via LM Studio",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="LLM call interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=LM_STUDIO_BASE_URL,
        help=f"LM Studio base URL (default: {LM_STUDIO_BASE_URL})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    run_experiment(
        duration=args.duration,
        interval=args.interval,
        base_url=args.base_url,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
