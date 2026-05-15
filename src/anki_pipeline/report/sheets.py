"""Google Sheets reporter — ported from anki-density-tracker."""

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


def _get_or_create_worksheet(sh, title: str, cols: int) -> Any:
    """Get existing worksheet or create + append header."""
    try:
        ws = sh.worksheet(title)
        return ws
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=cols)
        return ws


def update_density_stats(stats: list[dict[str, Any]]) -> None:
    """Write density stats to Sheets."""
    if not config.SPREADSHEET_ID or not stats:
        logger.info("No SPREADSHEET_ID or stats to write — skipping Sheets.")
        return
    client = _get_client()
    sh = client.open_by_key(config.SPREADSHEET_ID)
    ws = _get_or_create_worksheet(sh, "density", 3)
    header = [["time", "deck", "count"]]
    rows = [[s["time"], s["deck"], s["count"]] for s in stats]
    ws.clear()
    ws.update(header + rows, value_input_option="USER_ENTERED")
    logger.info("Updated density sheet: %d rows", len(rows))


def update_maturity_stats(maturity: list[dict[str, Any]]) -> None:
    if not config.SPREADSHEET_ID or not maturity:
        return
    client = _get_client()
    sh = client.open_by_key(config.SPREADSHEET_ID)
    ws = _get_or_create_worksheet(sh, "maturity", 4)
    header = [["date", "deck", "young", "mature"]]
    rows = [[m["date"], m["deck"], m["young"], m["mature"]] for m in maturity]
    ws.clear()
    ws.update(header + rows, value_input_option="USER_ENTERED")
    logger.info("Updated maturity sheet: %d rows", len(rows))


def update_daily_study_time(stats: list[dict[str, Any]]) -> None:
    if not config.SPREADSHEET_ID or not stats:
        return
    client = _get_client()
    sh = client.open_by_key(config.SPREADSHEET_ID)
    ws = _get_or_create_worksheet(sh, "study_time", 3)
    header = [["date", "deck", "minutes"]]
    rows = [[s["date"], s["deck"], s["minutes"]] for s in stats]
    ws.clear()
    ws.update(header + rows, value_input_option="USER_ENTERED")
    logger.info("Updated study_time sheet: %d rows", len(rows))
