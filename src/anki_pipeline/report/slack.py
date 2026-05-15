"""Slack reporter — ported from anki-density-tracker."""

import json
import logging
from typing import Any

import requests

from .. import config

logger = logging.getLogger(__name__)


def _progress_bar(current: int, total: int, width: int = 10) -> str:
    """Colour-coded progress bar."""
    if total <= 0:
        return "⬜" * width
    ratio = current / total
    filled = min(int(ratio * width), width)
    if ratio >= 0.8:
        bar = "🟩" * filled + "⬜" * (width - filled)
    elif ratio >= 0.5:
        bar = "🟧" * filled + "⬜" * (width - filled)
    else:
        bar = "🟥" * filled + "⬜" * (width - filled)
    return bar


def notify_progress(new_counts: dict[str, dict[str, int]]) -> None:
    """Send weekly progress report to Slack."""
    if not config.SLACK_WEBHOOK_URL:
        logger.info("No SLACK_WEBHOOK_URL — skipping Slack notification.")
        return

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📊 Anki Study Progress"}},
        {"type": "divider"},
    ]

    for deck_name, data in new_counts.items():
        due = data["remaining_due"]
        weekly = data["total_due_by_sunday"]
        reviewed = data["today_reviewed"]
        bar = _progress_bar(reviewed, weekly)

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{deck_name}*\n"
                    f"{bar}\n"
                    f"今日やった数: {reviewed}  /  残り(日曜まで): {due}  /  週の合計課題: {weekly}"
                ),
            },
        })

    payload = {"blocks": blocks}
    resp = requests.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    logger.info("Slack notification sent.")
