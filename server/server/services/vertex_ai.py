"""Vertex AI (Gemini) integration for daily report generation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class VertexAIService:
    """Wrapper around Vertex AI Gemini model.

    When GCP_PROJECT_ID is not set, returns a dummy report for local
    development without requiring Google Cloud credentials.
    """

    def __init__(self) -> None:
        self._model = None
        self._available = False
        self._init_vertex()

    def _init_vertex(self) -> None:
        project_id = os.environ.get("GCP_PROJECT_ID", "")
        location = os.environ.get("GCP_LOCATION", "asia-northeast1")

        if not project_id:
            logger.warning(
                "GCP_PROJECT_ID not set. Vertex AI disabled; using dummy reports."
            )
            return

        try:
            import vertexai  # type: ignore[import-untyped]
            from vertexai.generative_models import GenerativeModel  # type: ignore[import-untyped]

            vertexai.init(project=project_id, location=location)
            self._model = GenerativeModel("gemini-2.5-flash")
            self._available = True
            logger.info("Vertex AI initialised (project=%s, location=%s)", project_id, location)
        except Exception as exc:
            logger.warning("Vertex AI init failed (%s). Using dummy reports.", exc)

    # ------------------------------------------------------------------

    async def generate_daily_report(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Generate a natural-language daily report from statistics."""
        if not self._available or self._model is None:
            return self._dummy_report(stats)

        prompt = self._build_prompt(stats)
        try:
            response = await asyncio.to_thread(
                self._model.generate_content, prompt
            )
            return self._parse_response(response.text, stats)
        except Exception as exc:
            logger.error("Vertex AI generation failed: %s", exc)
            return self._dummy_report(stats)

    # ------------------------------------------------------------------

    def _build_prompt(self, stats: dict[str, Any]) -> str:
        return f"""あなたは生産性コーチです。以下のユーザーの1日のPC作業データを分析し、改善提案を含むレポートを生成してください。

## 今日のデータ
- 日付: {stats.get('date', 'unknown')}
- 集中時間: {stats.get('focused_minutes', 0)}分
- 眠気時間: {stats.get('drowsy_minutes', 0)}分
- 散漫時間: {stats.get('distracted_minutes', 0)}分
- 離席時間: {stats.get('away_minutes', 0)}分
- アイドル時間: {stats.get('idle_minutes', 0)}分
- 通知回数: {stats.get('notification_count', 0)}回
- 集中ブロック: {stats.get('focus_blocks', [])}
- 使用アプリ: {stats.get('top_apps', [])}

## 出力形式（JSON）
以下のJSON形式で出力してください。JSON以外は出力しないでください。
{{
  "summary": "1-2文の総括。具体的な数値を含めてください。",
  "highlights": ["良かった点を1-3個"],
  "concerns": ["改善が必要な点を1-3個"],
  "tomorrow_tip": "明日試してほしい具体的な1つの行動提案"
}}"""

    def _parse_response(self, text: str, stats: dict[str, Any]) -> dict[str, Any]:
        """Extract JSON from Gemini response (handles ```json blocks)."""
        cleaned = text
        if "```" in cleaned:
            lines = cleaned.split("\n")
            json_lines: list[str] = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini response: %s", text[:200])
            return self._dummy_report(stats)

    def _dummy_report(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Return a plausible placeholder report for local development."""
        focused = stats.get("focused_minutes", 0)
        drowsy = stats.get("drowsy_minutes", 0)
        distracted = stats.get("distracted_minutes", 0)
        total = focused + drowsy + distracted + stats.get("away_minutes", 0) + stats.get("idle_minutes", 0)
        pct = round(focused / total * 100) if total > 0 else 0

        return {
            "summary": (
                f"本日は合計{total:.0f}分の作業時間のうち、"
                f"{focused:.0f}分({pct}%)集中できました。"
                f"（※ダミーレポート: Vertex AI未接続）"
            ),
            "highlights": [
                f"集中時間が{focused:.0f}分確保できています。",
            ],
            "concerns": [
                f"眠気が{drowsy:.0f}分、散漫が{distracted:.0f}分検出されました。"
                if (drowsy + distracted) > 0
                else "特に大きな懸念はありません。",
            ],
            "tomorrow_tip": (
                "午後の眠気対策として、13:00頃に5分間の散歩を取り入れてみましょう。"
            ),
        }
