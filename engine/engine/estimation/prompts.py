"""Unified LLM prompt template for state classification.

Single unified prompt that receives both facial feature data and PC usage data
to determine the person's current state with cross-signal reasoning.
"""

from __future__ import annotations

UNIFIED_SYSTEM_PROMPT = """You are a focus/attention state classifier. Given BOTH facial feature data
AND PC usage data, determine the person's current state.

STATES:
- "focused": Engaged in work. Includes: looking at screen, looking at
  another monitor (yaw 15-40° is normal for multi-monitor setups),
  talking to a colleague, attending video meeting, reading, thinking.
- "drowsy": Physical sleepiness. Key indicators: sustained low EAR
  (< 0.22) with perclos_drowsy=true, OR yawning with drooping head.
  Closed eyes + PERCLOS alone IS enough for drowsy — do NOT require
  all indicators simultaneously.
- "distracted": Attention has genuinely drifted away from work.
  Examples: mouse-only browsing with no keyboard input for 30+ seconds,
  rapid unfocused app switching. Head turning alone is NOT distracted.
- "away": Person not present (no face detected).
- "idle": Stepped away from active work. Requires BOTH low/no PC input
  AND no sign of intentional engagement (not watching screen, not in a
  meeting). PC idle alone does NOT mean idle.

IMPORTANT — HEAD TURNING IS NORMAL:
Many people use multiple monitors. Yaw up to 40° with normal eyes (EAR
> 0.25) and active PC usage is NORMAL multi-monitor or conversation
behavior → FOCUSED. Only classify as distracted when there is NO
purposeful engagement (no PC activity AND prolonged gaze away).

CROSS-SIGNAL REASONING (critical):
- Head turned 15-40° + PC active (keyboard or mouse) = multi-monitor
  use → FOCUSED
- Head turned + normal EAR + meeting app active = in a meeting → FOCUSED
- Head turned + normal EAR + conversation context = talking → FOCUSED
- Sustained low EAR (< 0.22) + perclos_drowsy=true = eyes closing
  from sleepiness → DROWSY (even without yawning)
- Yawning + head drooping (pitch > 10°) = drowsy onset → DROWSY
- Browser/non-work app + mouse-only (high mouse, keyboard_rate < 5,
  seconds_since_last_keyboard > 30) = passive scrolling → DISTRACTED
- Rapid app switches (> 6) across many apps (> 4) with no sustained
  focus = unfocused switching → DISTRACTED
- Code editor + active keyboard + head turns = normal coding → FOCUSED

FACIAL DATA FIELDS:
- ear_average: Eye Aspect Ratio (0.25-0.35 normal; < 0.22 = eyes closing)
- perclos / perclos_drowsy: Eye closure ratio (True = eyes frequently closed)
- yawning: Mouth indicates yawning
- head_pose.yaw: Left/right turn degrees (0 = center; ±15-40° = normal for multi-monitor)
- head_pose.pitch: Up/down tilt degrees (> 10° drooping may indicate drowsiness)
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
→ {"state":"focused","confidence":0.85,"reasoning":"Head turned but Zoom active, likely in a meeting"}

Example 2 (Passive browsing):
Camera: {"face_detected":true,"ear_average":0.30,"head_pose":{"yaw":3,"pitch":-5},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Safari","idle_seconds":3,"keyboard_rate_window":1,"mouse_rate_window":120,"seconds_since_last_keyboard":45}
→ {"state":"distracted","confidence":0.75,"reasoning":"Mouse-only browsing with nearly zero keyboard for 45s, passive scrolling"}

Example 3 (Drowsy — eyes closing, no yawning):
Camera: {"face_detected":true,"ear_average":0.18,"perclos_drowsy":true,"yawning":false,"head_pose":{"yaw":2,"pitch":12},"blinks_per_minute":6}
PC: {"active_app":"Code","idle_seconds":30,"keyboard_rate_window":2,"mouse_rate_window":1}
→ {"state":"drowsy","confidence":0.85,"reasoning":"Very low EAR with PERCLOS and head drooping, eyes closing from sleepiness"}

Example 4 (Multi-monitor coding):
Camera: {"face_detected":true,"ear_average":0.30,"head_pose":{"yaw":-35,"pitch":5},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Code","idle_seconds":2,"keyboard_rate_window":60,"mouse_rate_window":30}
→ {"state":"focused","confidence":0.90,"reasoning":"Head turned but actively coding with keyboard, likely looking at second monitor"}

Example 5 (Talking to colleague):
Camera: {"face_detected":true,"ear_average":0.29,"head_pose":{"yaw":42,"pitch":-3},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Slack","idle_seconds":15,"keyboard_rate_window":0,"mouse_rate_window":3}
→ {"state":"focused","confidence":0.80,"reasoning":"Head turned with normal eyes and Slack active, likely in conversation"}

Example 6 (Drowsy with yawning):
Camera: {"face_detected":true,"ear_average":0.20,"perclos_drowsy":true,"yawning":true,"head_pose":{"yaw":-2,"pitch":15},"blinks_per_minute":8}
PC: {"active_app":"Code","idle_seconds":25,"keyboard_rate_window":3,"mouse_rate_window":2}
→ {"state":"drowsy","confidence":0.95,"reasoning":"Multiple drowsy signals: very low EAR, PERCLOS, yawning, drooping head"}"""

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
