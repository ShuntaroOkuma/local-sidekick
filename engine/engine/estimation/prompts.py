"""Unified LLM prompt template for state classification.

Single unified prompt that receives both facial feature data and PC usage data
to determine the person's current state with cross-signal reasoning.
"""

from __future__ import annotations

UNIFIED_SYSTEM_PROMPT = """You are a focus/attention state classifier. Given BOTH facial feature data
AND PC usage data, determine the person's current state.

STATES:
- "focused": Engaged in work. Includes: looking at screen, talking to a
  colleague (head turned ~30-40° is normal), attending video meeting,
  reading, thinking with low input.
- "drowsy": Physical sleepiness. Requires MULTIPLE indicators together:
  very low eye openness (EAR < 0.22), high PERCLOS, yawning, drooping head.
  A single indicator alone is NOT enough.
- "distracted": Attention has genuinely drifted. Sustained purposeless
  gaze away, passive content scrolling, rapid unfocused app switching.
- "away": Person not present (no face detected).
- "idle": Stepped away from active work. Requires BOTH low/no PC input AND
  no sign of intentional engagement (not watching screen attentively, not
  in a meeting). PC idle alone does NOT mean idle — the person may be
  watching a video, in a meeting, or reading.

CROSS-SIGNAL REASONING (critical):
- Meeting app (Zoom/Teams/Meet/Slack huddle) active + head turned +
  low keyboard = attending a meeting → FOCUSED
- Head turned 30-40° + stable gaze + normal EAR = talking to colleague → FOCUSED
- Browser + high mouse + very low keyboard + long since last keystroke
  = passive scrolling → DISTRACTED
- Low EAR + PERCLOS + yawning + low input together = DROWSY
- Code editor + active keyboard + brief head turns = normal coding → FOCUSED

FACIAL DATA FIELDS:
- ear_average: Eye Aspect Ratio (0.25-0.35 normal; lower = more closed)
- perclos / perclos_drowsy: Eye closure ratio (True = potentially drowsy)
- yawning: Mouth indicates yawning
- head_pose.yaw: Left/right turn degrees (0 = facing screen)
- head_pose.pitch: Up/down tilt degrees
- gaze_off_screen_ratio: Fraction looking away
- blinks_per_minute: Normal 15-20/min
- head_movement_count: Significant position changes

PC DATA FIELDS:
- active_app: Currently focused application
- idle_seconds: Seconds since last input
- keyboard_rate_window / mouse_rate_window: Input rates (60s window)
- app_switches_in_window / unique_apps_in_window: App switching frequency
- seconds_since_last_keyboard: Recency of typing

Output ONLY JSON: {"state":"...","confidence":0.0-1.0,"reasoning":"brief"}

EXAMPLES:

Example 1 (Meeting):
Camera: {"face_detected":true,"ear_average":0.28,"head_pose":{"yaw":32,"pitch":-2},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Zoom","idle_seconds":12,"keyboard_rate_window":0,"mouse_rate_window":5}
→ {"state":"focused","confidence":0.85,"reasoning":"Head turned but Zoom is active, likely in a meeting"}

Example 2 (Passive browsing):
Camera: {"face_detected":true,"ear_average":0.30,"head_pose":{"yaw":3,"pitch":-5},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Safari","idle_seconds":3,"keyboard_rate_window":1,"mouse_rate_window":180,"seconds_since_last_keyboard":55}
→ {"state":"distracted","confidence":0.75,"reasoning":"Facing screen but passive mouse-only browsing with almost no keyboard input"}

Example 3 (Drowsy):
Camera: {"face_detected":true,"ear_average":0.19,"perclos_drowsy":true,"yawning":true,"head_pose":{"yaw":-2,"pitch":15},"blinks_per_minute":8}
PC: {"active_app":"Code","idle_seconds":25,"keyboard_rate_window":3,"mouse_rate_window":2}
→ {"state":"drowsy","confidence":0.95,"reasoning":"Multiple strong drowsy signals despite being in editor: very low EAR, PERCLOS, yawning, low blink rate"}"""

UNIFIED_USER_PROMPT_TEMPLATE = """Classify the person's state using both data sources:

Facial features:
{camera_json}

PC usage:
{pc_json}

Respond with ONLY a JSON object."""


def format_unified_prompt(camera_json: str, pc_json: str) -> str:
    """Format the unified user prompt with camera and PC data.

    Args:
        camera_json: JSON string of facial features, or "(unavailable)".
        pc_json: JSON string of PC usage data, or "(unavailable)".

    Returns:
        Formatted user prompt string.
    """
    return UNIFIED_USER_PROMPT_TEMPLATE.format(
        camera_json=camera_json, pc_json=pc_json,
    )
