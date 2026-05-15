"""Unified CLI entry point for anki-pipeline.

Subcommands:
  run-all       Full pipeline: close Anki → sync → GTrans → density → report
  run-density   Density tracking only (read → Sheets/Slack)
  run-gtrans    GTrans fetch + write cards only
  check-new     Fast check: count new GTrans items (no Anki launch needed)
  manual-login  Re-authenticate Google Translate session
  sync-only     Just sync Anki collection
"""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from . import config
from .sync import close_anki, is_running, sync, open_anki_collection, ensure_synced_env
from .storage import load_ids, save_ids

logger = logging.getLogger("anki-pipeline")


def setup_logging():
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    level = getattr(logging, config.LOG_LEVEL, logging.INFO)

    # Console handler
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(log_format))

    # File handler (rotating)
    log_path = config.LOGS_DIR / "anki-pipeline.log"
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(str(log_path), maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(logging.Formatter(log_format))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(stream)
    root.addHandler(file_handler)


# ── Density subcommand ──────────────────────────────

def cmd_density(args):
    from .density.stats import (
        get_density_stats, get_maturity_stats, get_daily_study_time, get_new_card_counts,
    )
    from .report.sheets import update_density_stats, update_maturity_stats, update_daily_study_time
    from .report.slack import notify_progress

    if is_running():
        logger.warning("Anki is running — density read requires Anki closed.")
        return 1

    sync()
    with open_anki_collection() as a:
        import datetime
        now = datetime.datetime.now()
        today = datetime.datetime(now.year, now.month, now.day)

        stats = get_density_stats(a, today)
        maturity = get_maturity_stats(a)
        daily = get_daily_study_time(a)
        new_counts = get_new_card_counts(a)

    if stats:
        update_density_stats(stats)
    if maturity:
        update_maturity_stats(maturity)
    if daily:
        update_daily_study_time(daily)
    if config.SLACK_WEBHOOK_URL:
        notify_progress(new_counts)

    logger.info("Density run completed.")
    return 0


# ── GTrans subcommand ───────────────────────────────

def cmd_gtrans(args):
    from .gtrans.scraper import fetch_favorites, ensure_logged_in, delete_favorite_items
    from .gtrans.processor import GeminiProcessor, ProcessedWord, ProcessedSentence
    from .anki_writer import ensure_models_and_decks, add_word_note, add_sentence_note
    from .sync import ensure_synced_env

    # 1. Close Anki + sync
    was_running, a = ensure_synced_env()

    # 2. Fetch favorites
    ensure_logged_in(manual_login=args.manual_login)
    favorites = fetch_favorites(limit=args.limit)
    if not favorites:
        logger.info("No new favorites to process.")
        return 0

    # 3. Filter already-processed
    processed = load_ids(config.PROCESSED_IDS_PATH)
    stale_faves = [f for f in favorites if f.item_id in processed]
    new_faves = [f for f in favorites if f.item_id not in processed]

    # Clean up stale items from Google Translate (already processed in past runs)
    if stale_faves and not args.skip_delete:
        deleted = delete_favorite_items(stale_faves)
        logger.info("Cleaned up %d stale items from Google Translate.", deleted)

    if not new_faves:
        logger.info("All favorites already processed.")
        return 0

    # 4. Gemini processing
    proc = GeminiProcessor()
    ensure_models_and_decks(a)

    added_ids = set()
    for item in new_faves:
        result = proc.process_item(item)
        if result is None:
            continue
        if isinstance(result.data, ProcessedWord):
            note_id = add_word_note(a, result.data)
        else:
            note_id = add_sentence_note(a, result.data)
        if note_id is not None:
            added_ids.add(item.item_id)

    # 5. Persist processed IDs
    processed |= added_ids
    save_ids(config.PROCESSED_IDS_PATH, processed)

    # 6. Delete processed items from Google Translate
    if not args.skip_delete and added_ids:
        items_to_delete = [f for f in new_faves if f.item_id in added_ids]
        deleted = delete_favorite_items(items_to_delete)
        logger.info("Deleted %d items from Google Translate.", deleted)

    # Re-sync if Anki was originally running
    if was_running:
        sync()

    logger.info("GTrans run completed.")
    return 0


# ── Check-new subcommand ────────────────────────────

def cmd_check_new(args):
    from .gtrans.scraper import fetch_favorites

    processed = load_ids(config.PROCESSED_IDS_PATH)
    favorites = fetch_favorites(limit=args.limit)
    new_count = len([f for f in favorites if f.item_id not in processed])
    print(new_count)  # stdout for shell consumption
    return 0


# ── Run-all subcommand ──────────────────────────────

def cmd_run_all(args):
    """Full pipeline: density + gtrans."""
    # Phase 1: GTrans
    logger.info("=== Phase 1: GTrans card creation ===")
    ret = cmd_gtrans(args)
    if ret != 0:
        logger.warning("GTrans phase failed, continuing with density…")

    # Phase 2: Density
    logger.info("=== Phase 2: Density tracking ===")
    # If Anki was closed by gtrans phase, it's still closed — good for density
    ret = cmd_density(args)
    return ret


# ── Manual login ────────────────────────────────────

def cmd_manual_login(args):
    from .gtrans.scraper import ensure_logged_in
    ensure_logged_in(manual_login=True)
    return 0


# ── Sync only ───────────────────────────────────────

def cmd_sync_only(args):
    from .sync import ensure_synced_env
    _, a = ensure_synced_env()
    return 0


# ── Main ────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="anki-pipeline: unified Anki infrastructure")
    sub = parser.add_subparsers(dest="command", required=True)

    p_all = sub.add_parser("run-all", help="Full pipeline (GTrans + density + report)")
    p_all.add_argument("--limit", type=int, default=config.BATCH_LIMIT)
    p_all.add_argument("--manual-login", action="store_true")
    p_all.add_argument("--skip-delete", action="store_true")

    p_density = sub.add_parser("run-density", help="Density tracking only")
    p_density.set_defaults(func=cmd_density)

    p_gtrans = sub.add_parser("run-gtrans", help="GTrans only")
    p_gtrans.add_argument("--limit", type=int, default=config.BATCH_LIMIT)
    p_gtrans.add_argument("--manual-login", action="store_true")
    p_gtrans.add_argument("--skip-delete", action="store_true")

    p_check = sub.add_parser("check-new", help="Count new GTrans items")
    p_check.add_argument("--limit", type=int, default=config.BATCH_LIMIT)

    sub.add_parser("manual-login", help="Re-auth GTranslate session")
    sub.add_parser("sync-only", help="Just sync Anki collection")

    args = parser.parse_args(argv)

    if hasattr(args, "func"):
        return args.func(args)

    # Map command to function
    cmd_map = {
        "run-all": cmd_run_all,
        "run-density": cmd_density,
        "run-gtrans": cmd_gtrans,
        "check-new": cmd_check_new,
        "manual-login": cmd_manual_login,
        "sync-only": cmd_sync_only,
    }
    fn = cmd_map.get(args.command)
    if fn:
        return fn(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
