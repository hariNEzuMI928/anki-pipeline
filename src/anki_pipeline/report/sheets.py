"""Google Sheets reporter — restored to anki-density-tracker format."""
import logging
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from .. import config

logger = logging.getLogger(__name__)

_SHEET_SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]


def _get_client():
    creds = Credentials.from_service_account_file(
        str(config.CREDENTIALS_PATH), scopes=_SHEET_SCOPE
    )
    return gspread.authorize(creds)


def _get_sheet(sh, title: str, cols: int, header: list[str]):
    """Get existing worksheet or create + insert header."""
    try:
        ws = sh.worksheet(title)
        return ws
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=cols)
        ws.insert_row(header, 1)
        return ws


def _merge_update(ws, rows: list[list], key_cols: int):
    """
    Merge rows into worksheet:
    - Existing rows (matched by first key_cols columns) are updated in place.
    - New rows are appended.
    """
    all_values = ws.get_all_values()
    if not all_values:
        # Empty sheet — write header + data
        return

    existing = {}
    for i, row in enumerate(all_values):
        if len(row) < key_cols:
            continue
        key = tuple(row[c] for c in range(key_cols))
        existing[key] = i + 1  # 1-indexed

    updates = []
    new_rows = []
    for row in rows:
        key = tuple(row[c] for c in range(key_cols))
        if key in existing:
            idx = existing[key]
            # Only update if different
            curr = all_values[idx - 1]
            if row != curr[:len(row)]:
                updates.append({"range": f"A{idx}:{chr(64 + len(row))}{idx}", "values": [row]})
        else:
            new_rows.append(row)

    if updates:
        ws.batch_update(updates)
    if new_rows:
        ws.append_rows(new_rows)

    logger.info("Sheet '%s': %d new, %d updated", ws.title, len(new_rows), len(updates))


# ── Density stats (30-min buckets) ──────────────────────────

def update_density_stats(stats: list[dict[str, Any]]) -> None:
    """Write density stats to 'Anki' sheet (merge strategy)."""
    if not config.SPREADSHEET_ID or not stats:
        logger.info("No SPREADSHEET_ID or stats — skipping.")
        return

    header = ["日時", "デッキ", "枚数"]
    rows = [[s["time"], s["deck"], s["count"]] for s in stats]

    sh = _get_client().open_by_key(config.SPREADSHEET_ID)
    ws = _get_sheet(sh, "Anki", 3, header)

    # Ensure header
    first_row = ws.row_values(1)
    if first_row != header:
        ws.insert_row(header, 1)

    _merge_update(ws, rows, key_cols=2)


# ── Maturity stats (young/mature) ────────────────────────────

def update_maturity_stats(maturity: list[dict[str, Any]]) -> None:
    if not config.SPREADSHEET_ID or not maturity:
        return

    header = ["date", "deck", "young", "mature"]
    rows = [[m["date"], m["deck"], m["young"], m["mature"]] for m in maturity]

    sh = _get_client().open_by_key(config.SPREADSHEET_ID)
    ws = _get_sheet(sh, "Anki_Matured", 4, header)

    first_row = ws.row_values(1)
    if first_row != header:
        ws.insert_row(header, 1)

    _merge_update(ws, rows, key_cols=2)


# ── Daily study time ─────────────────────────────────────────

def update_daily_study_time(stats: list[dict[str, Any]]) -> None:
    if not config.SPREADSHEET_ID or not stats:
        return

    header = ["日付", "デッキ名", "合計学習時間（分）"]
    rows = [[s["date"], s["deck"], s["minutes"]] for s in stats]

    sh = _get_client().open_by_key(config.SPREADSHEET_ID)
    ws = _get_sheet(sh, "Anki_Daily", 3, header)

    first_row = ws.row_values(1)
    if first_row != header:
        ws.insert_row(header, 1)

    _merge_update(ws, rows, key_cols=2)
