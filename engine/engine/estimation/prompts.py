"""Unified LLM prompt template for state classification.

Single unified prompt that receives both facial feature data and PC usage data
to determine the person's current state with cross-signal reasoning.
"""

from __future__ import annotations

UNIFIED_SYSTEM_PROMPT = """Classify the person's state from facial and PC data.

STATES: focused, drowsy, distracted, away
DEFAULT: If unsure, choose "focused". Focused is the normal working state.

RULES:
- "focused": DEFAULT state. Working, reading, meeting, conversation, multi-monitor use. Head turned up to 60° is normal (multi-monitor, talking). No PC input can still be focused (watching video, meeting, reading). Slightly low EAR (0.22-0.27) without other drowsy signs = focused.
- "drowsy": REQUIRES multiple strong signals together: very low EAR (<0.22) AND perclos_drowsy=true, or yawning with low EAR. One weak signal alone is NEVER enough for drowsy.
- "distracted": Rapid app switching (>6 switches, >4 apps). Head turning alone is NOT distracted.
- "away": No face detected.

Output ONLY: {"state":"...","confidence":0.0-1.0,"reasoning":"brief"}

EXAMPLES:
Cam:{"ear_average":0.28,"head_pose":{"yaw":32},"perclos_drowsy":false,"yawning":false} PC:{"active_app":"Zoom","keyboard_rate_window":0,"mouse_rate_window":5}
→ {"state":"focused","confidence":0.85,"reasoning":"Zoom meeting, head turned"}

Cam:{"ear_average":0.18,"perclos_drowsy":true,"yawning":false,"head_pose":{"yaw":2,"pitch":12}} PC:{"active_app":"Code","keyboard_rate_window":2}
→ {"state":"drowsy","confidence":0.85,"reasoning":"Very low EAR with PERCLOS"}

Cam:{"ear_average":0.24,"head_pose":{"yaw":5,"pitch":8},"perclos_drowsy":false,"yawning":false} PC:{"active_app":"Safari","idle_seconds":95,"is_idle":true}
→ {"state":"focused","confidence":0.75,"reasoning":"Reading or watching, no drowsy signs"}

Cam:{"ear_average":0.25,"head_pose":{"yaw":-48},"perclos_drowsy":false,"yawning":false} PC:{"active_app":"Code","keyboard_rate_window":40}
→ {"state":"focused","confidence":0.80,"reasoning":"Multi-monitor coding, eyes open"}

Cam:{"ear_average":0.30,"head_pose":{"yaw":-35},"perclos_drowsy":false,"yawning":false} PC:{"active_app":"Code","keyboard_rate_window":60,"mouse_rate_window":30}
→ {"state":"focused","confidence":0.90,"reasoning":"Active coding, second monitor"}"""

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
