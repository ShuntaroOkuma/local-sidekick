"""LLM prompt templates for state classification.

Three prompt types:
1. Text mode: facial feature JSON -> state classification
2. Vision mode: webcam image -> state classification
3. PC usage mode: usage metadata -> work state classification

All prompts instruct the LLM to respond in JSON format.
"""

from __future__ import annotations

# --- Text mode prompt (features JSON -> state) ---

TEXT_SYSTEM_PROMPT = """You are a state classifier. Analyze facial data JSON and return a JSON object.

RULES (check in order, return FIRST match):
1. face_detected is false -> state="away", confidence=1.0
2. ANY of: perclos_drowsy is true, yawning is true, ear_average < 0.22, head_pose.pitch > 15 -> state="drowsy"
3. ANY of: |head_pose.yaw| > 20, |head_pose.pitch| > 20, head_yaw_std > 8, gaze_off_screen_ratio > 0.3 -> state="distracted"
4. Otherwise -> state="focused"

Output ONLY: {"state":"...","confidence":0.0-1.0,"reasoning":"brief"}

EXAMPLES:
Input: {"face_detected":true,"ear_average":0.18,"perclos":0.25,"perclos_drowsy":true,"yawning":false,"blinks_per_minute":8,"head_pose":{"pitch":12,"yaw":-2,"roll":1}}
Output: {"state":"drowsy","confidence":0.9,"reasoning":"PERCLOS drowsy flag set, very low EAR"}

Input: {"face_detected":true,"ear_average":0.30,"perclos":0.02,"perclos_drowsy":false,"yawning":false,"blinks_per_minute":16,"head_pose":{"pitch":-3,"yaw":35,"roll":2}}
Output: {"state":"distracted","confidence":0.85,"reasoning":"Head turned significantly to side (yaw=35)"}

Input: {"face_detected":true,"ear_average":0.28,"perclos":0.03,"perclos_drowsy":false,"yawning":false,"blinks_per_minute":17,"head_pose":{"pitch":-5,"yaw":3,"roll":-1}}
Output: {"state":"focused","confidence":0.95,"reasoning":"Eyes open, facing screen, normal blink rate"}"""

TEXT_USER_PROMPT_TEMPLATE = """Analyze the following facial feature data and classify the person's current state.

Current frame features:
{features_json}

Respond with ONLY a JSON object."""


# --- Vision mode prompt (webcam image -> state) ---

VISION_SYSTEM_PROMPT = """You are a state classifier. Analyze the webcam image and return a JSON object.

RULES (check in order, return FIRST match):
1. No person visible -> state="away", confidence=1.0
2. ANY of: eyes half-closed or closed, yawning, head drooping forward, slouched posture -> state="drowsy"
3. ANY of: head turned away from screen (>20 degrees), looking at phone, looking sideways -> state="distracted"
4. Person looking at screen with eyes open and upright posture -> state="focused"

Output ONLY: {"state":"focused"|"drowsy"|"distracted"|"away","confidence":0.0-1.0,"reasoning":"brief visual observation"}"""

VISION_USER_PROMPT = "Analyze this webcam image and classify the person's current state. Respond with ONLY a JSON object."


# --- PC usage mode prompt (usage data -> work state) ---

PC_USAGE_SYSTEM_PROMPT = """You are a work state classifier. Analyze PC usage data JSON and return a JSON object.

RULES (check in STRICT order, return FIRST match):
1. idle_seconds > 30 -> state="idle" (HIGHEST PRIORITY, regardless of cumulative activity rates)
2. is_idle is true -> state="idle"
3. app_switches_in_window > 5 OR unique_apps_in_window > 4 -> state="distracted"
4. keyboard_rate_window > 10 AND active_app is work-related (editor/terminal/IDE) -> state="focused"
5. keyboard_rate_window <= 5 AND mouse_rate_window <= 10 -> state="idle"
6. Otherwise -> assess from overall context

CRITICAL: idle_seconds shows CURRENT inactivity. *_per_min fields may be cumulative session averages. ALWAYS prioritize idle_seconds for detecting current state.

Output ONLY: {"state":"focused"|"distracted"|"idle","confidence":0.0-1.0,"reasoning":"brief"}

EXAMPLES:
Input: {"active_app":"Code","idle_seconds":52.2,"keyboard_events_per_min":129.1,"mouse_events_per_min":339.1,"app_switches_in_window":0}
Output: {"state":"idle","confidence":0.95,"reasoning":"idle_seconds=52.2 exceeds 30s threshold, user currently inactive"}

Input: {"active_app":"Code","idle_seconds":0.5,"keyboard_events_per_min":85.0,"mouse_events_per_min":200.0,"app_switches_in_window":1}
Output: {"state":"focused","confidence":0.9,"reasoning":"Active in Code editor, low idle time, minimal app switching"}

Input: {"active_app":"Safari","idle_seconds":2.0,"keyboard_events_per_min":40.0,"app_switches_in_window":8,"unique_apps_in_window":5}
Output: {"state":"distracted","confidence":0.85,"reasoning":"8 app switches with 5 unique apps indicates fragmented attention"}"""

PC_USAGE_USER_PROMPT_TEMPLATE = """Analyze the following PC usage data and classify the user's current work state.

Current usage snapshot:
{usage_json}

Respond with ONLY a JSON object."""


def format_text_prompt(features_json: str) -> str:
    """Format the text mode user prompt with feature data.

    Args:
        features_json: JSON string of facial features.

    Returns:
        Formatted user prompt string.
    """
    return TEXT_USER_PROMPT_TEMPLATE.format(features_json=features_json)


def format_pc_usage_prompt(usage_json: str) -> str:
    """Format the PC usage mode user prompt with usage data.

    Args:
        usage_json: JSON string of PC usage data.

    Returns:
        Formatted user prompt string.
    """
    return PC_USAGE_USER_PROMPT_TEMPLATE.format(usage_json=usage_json)
