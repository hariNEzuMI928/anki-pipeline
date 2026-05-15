"""Google Translate favorites scraper via Playwright — ported from GTrans-Favorites-to-Anki."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError

from .. import config

logger = logging.getLogger(__name__)

_SELECTORS: Optional[dict[str, str]] = None
_SCRAPER_INSTANCE: Optional["Scraper"] = None


@dataclass
class FavoriteItem:
    text: str
    translation: str
    item_id: str


def _load_selectors(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Scraper:
    def __init__(self):
        global _SELECTORS
        if _SELECTORS is None:
            _SELECTORS = _load_selectors(config.SELECTORS_PATH)
        self.selectors = _SELECTORS

    def ensure_logged_in(self, manual_login: bool = False, timeout_sec: int = 300) -> None:
        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login)
            page = context.new_page()
            try:
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)
                if manual_login:
                    input("Press Enter when logged in…")
                ready = f"{self.selectors['favorites_container']}, {self.selectors['empty_state_indicator']}"
                page.locator(ready).first.wait_for(timeout=timeout_sec * 1000)
                context.storage_state(path=str(config.AUTH_STATE_PATH))
                logger.info("Auth state saved.")
            except TimeoutError as e:
                logger.error("Timeout during login: %s", e)
                page.screenshot(path=str(config.DATA_DIR / f"login_timeout_{datetime.now():%Y%m%d_%H%M%S}.png"))
                raise
            finally:
                page.close()
                context.close()
                browser.close()

    def fetch_favorites(self, limit: Optional[int] = None) -> list[FavoriteItem]:
        items: list[FavoriteItem] = []
        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login=False)
            page = context.new_page()
            try:
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)
                ready = f"{self.selectors['favorites_container']}, {self.selectors['empty_state_indicator']}"
                page.locator(ready).first.wait_for(timeout=30000)

                empty = page.locator(self.selectors["empty_state_indicator"])
                if empty.count() > 0:
                    logger.info("No favorites found.")
                    return []

                elements = page.locator(self.selectors["favorite_item"]).all()
                logger.info("Found %d items.", len(elements))
                for i, el in enumerate(elements):
                    if limit and i >= limit:
                        break
                    try:
                        text_el = el.locator(self.selectors["favorite_item_text"]).first
                        trans_el = el.locator(self.selectors["favorite_item_translation"]).first
                        text = text_el.inner_text().strip()
                        translation = trans_el.inner_text().strip()
                        if text and translation:
                            item_id = hashlib.sha256(f"{text}-{translation}".encode()).hexdigest()
                            items.append(FavoriteItem(text=text, translation=translation, item_id=item_id))
                    except Exception as e:
                        logger.warning("Skipping item %d: %s", i, e)
            except TimeoutError as e:
                logger.error("Timeout fetching favorites: %s", e)
            finally:
                page.close()
                context.close()
                browser.close()
        return items

    def delete_favorite_items(self, items: list[FavoriteItem]) -> int:
        deleted = 0
        if not items:
            return 0
        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login=False)
            page = context.new_page()
            try:
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)
                for item in items:
                    for _ in range(3):
                        try:
                            esc_text = item.text.replace('"', '\\"')
                            sel = f"{self.selectors['favorite_item']}:has-text(\"{esc_text}\")"
                            target = page.locator(sel).first
                            if target.count() == 0:
                                page.reload(wait_until="domcontentloaded")
                                continue
                            target.locator(self.selectors["favorite_item_delete_button"]).first.click()
                            target.wait_for(state="hidden", timeout=5000)
                            deleted += 1
                            break
                        except Exception:
                            page.reload(wait_until="domcontentloaded")
            finally:
                page.close()
                context.close()
                browser.close()
        return deleted

    def delete_favorite_item(self, item: FavoriteItem) -> bool:
        return self.delete_favorite_items([item]) > 0

    def _new_context(self, pw, manual_login: bool = False):
        headless = False if manual_login else config.PLAYWRIGHT_HEADLESS
        browser = pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--disk-cache-size=0"],
        )
        ctx_opts = {"user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        )}
        if config.AUTH_STATE_PATH.exists():
            ctx_opts["storage_state"] = str(config.AUTH_STATE_PATH)
        return browser.new_context(**ctx_opts), browser


def _get_scraper() -> Scraper:
    global _SCRAPER_INSTANCE
    if _SCRAPER_INSTANCE is None:
        _SCRAPER_INSTANCE = Scraper()
    return _SCRAPER_INSTANCE


def ensure_logged_in(manual_login: bool = False, timeout_sec: int = 300) -> None:
    _get_scraper().ensure_logged_in(manual_login, timeout_sec)


def fetch_favorites(limit: Optional[int] = None) -> list[FavoriteItem]:
    return _get_scraper().fetch_favorites(limit)


def delete_favorite_item(item: FavoriteItem) -> bool:
    return _get_scraper().delete_favorite_item(item)


def delete_favorite_items(items: list[FavoriteItem]) -> int:
    return _get_scraper().delete_favorite_items(items)
