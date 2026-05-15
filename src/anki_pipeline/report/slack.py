"""Slack reporter — restored to anki-density-tracker format."""
import datetime
import json
import logging

import requests

from .. import config

logger = logging.getLogger(__name__)


def notify_progress(counts: dict[str, dict[str, int]]) -> None:
    """Send weekly progress report to Slack (exact format from anki-density-tracker)."""
    if not config.SLACK_WEBHOOK_URL:
        logger.info("No SLACK_WEBHOOK_URL — skipping Slack notification.")
        return

    now = datetime.datetime.now()

    # 今週の日曜日までの残り日数を計算 (月=0, ..., 日=6)
    days_until_sunday = 6 - now.weekday()
    remaining_days = days_until_sunday + 1 if days_until_sunday > 0 else 1

    # デッキごとのアイコン設定
    deck_icons = {
        "2_EnglishComposition": "📘",
        "3_FluencyTest": "📙",
        "1_Vocabulary": "📕",
    }

    messages = []
    for deck_name, data in counts.items():
        remaining_due = data["remaining_due"]
        total_due_by_sunday = data.get("total_due_by_sunday", remaining_due)
        today_reviewed = data["today_reviewed"]

        # 今日のノルマ（一日の理想的な消化量）を計算
        daily_quota = (total_due_by_sunday + today_reviewed) / remaining_days

        # デッキアイコンの取得
        icon = deck_icons.get(deck_name, "✨")

        # ステータス判定とメッセージの構築
        if remaining_due == 0:
            if total_due_by_sunday == 0:
                status_text = "👑 *Status: 今週の全タスク完了！神レベルの進捗です！*"
            else:
                status_text = "✨ *Status: 現在の期日分はすべて完了！素晴らしい集中力です！*"
        elif today_reviewed >= daily_quota:
            status_text = (
                f"✅ *Status: 今日のノルマ（{daily_quota:.1f}枚）を突破！"
                "この調子で日曜完済を目指しましょう。*"
            )
        else:
            remaining_for_quota = daily_quota - today_reviewed
            status_text = (
                f"🔥 *Status: ノルマまであと {remaining_for_quota:.1f} 枚！"
                "ここが踏ん張りどころです。*"
            )

        deck_msg = (
            f"{icon} *{deck_name}*\n"
            f"🚨 期日切れ未完了: *{remaining_due}* 枚\n"
            f"📅 日曜日までの総タスク: *{total_due_by_sunday}* 枚\n"
            f"📚 本日の学習済: {today_reviewed} 枚\n"
            f"⏳ 日曜日まで残り {remaining_days} 日\n"
            f"{status_text}"
        )
        messages.append(deck_msg)

    if not messages:
        return

    # 時間帯に応じたタイトルを設定
    time_titles = {
        12: "☀️ *昼の進捗確認*",
        17: "🌇 *夕方の進捗確認*",
        21: "🌌 *夜の進捗レポート*",
        23: "🌙 *一日の最終確認*",
    }
    title = time_titles.get(now.hour, "📊 *Anki学習進捗レポート*")

    full_message = f"{title}\n\n" + "\n\n".join(messages)
    logger.info("Sending Slack notification:\n%s", full_message)

    payload = {"text": full_message}
    resp = requests.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    logger.info("Slack notification sent (status: %s)", resp.status_code)
