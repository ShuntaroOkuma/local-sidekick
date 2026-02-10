"""LLM prompt templates for state classification.

Three prompt types:
1. Text mode: facial feature JSON -> state classification
2. Vision mode: webcam image -> state classification
3. PC usage mode: usage metadata -> work state classification

All prompts instruct the LLM to respond in JSON format.
"""

from __future__ import annotations

# --- Text mode prompt (features JSON -> state) ---

TEXT_SYSTEM_PROMPT = """You are a real-time human state classifier. You analyze facial feature data from a webcam and classify the person's current state.

You MUST respond with ONLY a JSON object in the following format:
{
  "state": "focused" | "drowsy" | "distracted",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation of key indicators"
}

Classification rules:
- "focused": Eyes open (EAR > 0.20), face pointing forward (yaw/pitch within +/-15 degrees), normal blink rate (15-20/min)
- "drowsy": Eyes closing frequently (PERCLOS > 0.15), low EAR, yawning detected (MAR > 0.6), slow blinks, head drooping (pitch increasing)
- "distracted": Head turned away (large yaw/pitch), frequent head movements, looking away from screen

If face_detected is false, respond with:
{
  "state": "away",
  "confidence": 1.0,
  "reasoning": "No face detected in frame"
}"""

TEXT_USER_PROMPT_TEMPLATE = """Analyze the following facial feature data and classify the person's current state.

Current frame features:
{features_json}

Respond with ONLY a JSON object."""


# --- Vision mode prompt (webcam image -> state) ---

VISION_SYSTEM_PROMPT = """You are a real-time human state classifier. You analyze a webcam image and classify the person's current state.

You MUST respond with ONLY a JSON object in the following format:
{
  "state": "focused" | "drowsy" | "distracted",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation based on visual observations"
}

Visual indicators:
- "focused": Person looking at screen, eyes open, upright posture, alert expression
- "drowsy": Eyes half-closed or closed, yawning, head drooping, slouching
- "distracted": Looking away from screen, turned head, fidgeting, using phone

If no person is visible:
{
  "state": "away",
  "confidence": 1.0,
  "reasoning": "No person visible in frame"
}"""

VISION_USER_PROMPT = "Analyze this webcam image and classify the person's current state. Respond with ONLY a JSON object."


# --- PC usage mode prompt (usage data -> work state) ---

PC_USAGE_SYSTEM_PROMPT = """You are a work state classifier. You analyze PC usage metadata to determine the user's current work state.

You MUST respond with ONLY a JSON object in the following format:
{
  "state": "focused" | "distracted" | "idle",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation of key indicators"
}

Classification rules:
- "focused": Steady use of work-related apps (editor, terminal, IDE), minimal app switching, consistent keyboard/mouse activity
- "distracted": Frequent app switching (>5 switches/min), visiting non-work apps (social media, news, messaging), fragmented attention
- "idle": No keyboard/mouse activity for >30 seconds, high idle time

Key indicators:
- keyboard_events_per_min: High = active typing
- mouse_events_per_min: High = active navigation
- app_switches_in_window: High = context switching (distraction signal)
- unique_apps_in_window: High = fragmented attention
- idle_seconds: High = user is away or passive
- active_app: Work apps (editors, terminals, IDEs) vs non-work apps (browsers on social media, messaging)"""

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
