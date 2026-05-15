"""Density stats — ported from anki-density-tracker."""

import datetime
import logging
from typing import Any

from apyanki.anki import Anki

from .. import config

logger = logging.getLogger(__name__)


def get_density_stats(a: Anki, start_date: datetime.datetime) -> list[dict[str, Any]]:
    """Compute 30-minute-bucket study density grouped by parent deck."""
    start_ms = int(start_date.timestamp() * 1000)
    stats_map: dict[tuple[str, str], dict[str, int]] = {}

    query = """
        SELECT
            (r.id / (1000 * 1800)) * 1800 as bucket_start,
            c.did,
            count(*) as count
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE r.id > ?
        GROUP BY bucket_start, c.did
    """
    rows = a.col.db.all(query, start_ms)
    deck_id_to_name = {v: k for k, v in a.deck_name_to_id.items()}

    for bucket_ts, did, count in rows:
        deck_name = deck_id_to_name.get(did, f"Unknown({did})")
        parent_deck = _get_parent_deck(deck_name)
        if parent_deck:
            dt_str = datetime.datetime.fromtimestamp(bucket_ts).strftime("%Y-%m-%d %H:%M")
            key = (dt_str, parent_deck)
            if key not in stats_map:
                stats_map[key] = {"count": 0}
            stats_map[key]["count"] += count

    stats = []
    for (time_str, deck), data in sorted(stats_map.items()):
        stats.append({"time": time_str, "deck": deck, "count": data["count"]})
    return stats


def get_daily_study_time(a: Anki) -> list[dict[str, Any]]:
    """Daily minutes studied last 30 days."""
    tz = datetime.timezone.utc  # will convert to local
    now = datetime.datetime.now(tz)
    start_date = now - datetime.timedelta(days=30)
    start_ms = int(start_date.timestamp() * 1000)

    stats_map: dict[tuple[str, str], int] = {}

    query = """
        SELECT
            r.id,
            c.did,
            MIN(r.time, 600000) as capped_time
        FROM revlog r
        JOIN cards c ON r.cid = c.id
        WHERE r.id > ?
    """
    rows = a.col.db.all(query, start_ms)
    deck_id_to_name = {v: k for k, v in a.deck_name_to_id.items()}

    for rev_id_ms, did, capped_time in rows:
        rev_time_utc = datetime.datetime.fromtimestamp(rev_id_ms / 1000.0, tz=datetime.timezone.utc)
        rev_time_local = rev_time_utc.astimezone(tz)
        date_str = rev_time_local.strftime("%Y-%m-%d")
        deck_name = deck_id_to_name.get(did, f"Unknown({did})")
        parent_deck = _get_parent_deck(deck_name)
        if parent_deck:
            key = (date_str, parent_deck)
            stats_map[key] = stats_map.get(key, 0) + capped_time

    stats = []
    for (date_str, deck), total_time_ms in sorted(stats_map.items()):
        stats.append({"date": date_str, "deck": deck, "minutes": round(total_time_ms / 60000.0, 2)})
    return stats


def get_maturity_stats(a: Anki) -> list[dict[str, Any]]:
    """Young vs Mature card counts per tracked deck."""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    maturity = []
    for deck_name in config.DECKS_TO_TRACK:
        mature = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl>=21')
        young = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl<21')
        maturity.append({"date": today_str, "deck": deck_name, "young": len(young), "mature": len(mature)})
    return maturity


def get_new_card_counts(a: Anki) -> dict[str, dict[str, int]]:
    """Due-now / due-by-Sunday / today-reviewed per target deck."""
    now = datetime.datetime.now()
    days_until_sunday = 6 - now.weekday()
    start_ms = int(datetime.datetime(now.year, now.month, now.day).timestamp() * 1000)

    counts = {}
    for deck_name in config.TARGET_DECKS:
        due_now = a.col.find_cards(f'deck:"{deck_name}" is:due')

        future_due = []
        if days_until_sunday > 0:
            future_due = a.col.find_cards(
                f'deck:"{deck_name}" prop:due>0 prop:due<={days_until_sunday} -is:new -is:suspended'
            )

        total_due_by_sunday = len(set(due_now) | set(future_due))

        query_today = """
            SELECT count(distinct cid)
            FROM revlog
            WHERE id > ?
            AND cid IN (SELECT id FROM cards WHERE did IN (
                SELECT id FROM decks WHERE name = ? OR name LIKE ?
            ))
        """
        today_reviewed = a.col.db.scalar(query_today, start_ms, deck_name, f"{deck_name}::%")

        counts[deck_name] = {
            "remaining_due": len(due_now),
            "total_due_by_sunday": total_due_by_sunday,
            "today_reviewed": today_reviewed or 0,
        }
    return counts


def _get_parent_deck(deck_name: str) -> str | None:
    for track in config.DECKS_TO_TRACK:
        if deck_name == track or deck_name.startswith(f"{track}::"):
            return track
    return None
