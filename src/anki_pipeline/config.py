import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CREDENTIALS_PATH = PROJECT_ROOT / os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
AUTH_STATE_PATH = DATA_DIR / "auth_state.json"
PROCESSED_IDS_PATH = DATA_DIR / "processed_ids.json"
SELECTORS_PATH = PROJECT_ROOT / "src" / "anki_pipeline" / "gtrans" / "selectors.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Anki ────────────────────────────────────────────
ANKI_BASE = Path(os.path.expanduser(os.environ.get("ANKI_BASE", "~/Library/Application Support/Anki2")))
ANKI_PROFILE = os.environ.get("ANKI_PROFILE", "同期用")

DECKS_TO_TRACK = ["1_Vocabulary", "2_EnglishComposition", "3_FluencyTest"]
TARGET_DECKS = ["2_EnglishComposition", "3_FluencyTest"]

ANKI_WORD_DECK = os.environ.get("ANKI_WORD_DECK_NAME", "1_Vocabulary::GTrans")
ANKI_WORD_MODEL = os.environ.get("ANKI_WORD_NOTE_TYPE", "GTrans-Word")
ANKI_SENTENCE_DECK = os.environ.get("ANKI_SENTENCE_DECK_NAME", "3_FluencyTest::GTrans-Sentence")
ANKI_SENTENCE_MODEL = os.environ.get("ANKI_SENTENCE_NOTE_TYPE", "GTrans-Sentence")

# ── Slack ───────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# ── Google Sheets ──────────────────────────────────
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")

# ── Gemini ─────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# ── Google Translate ────────────────────────────────
GOOGLE_TRANSLATE_FAVORITES_URL = os.environ.get(
    "GOOGLE_TRANSLATE_FAVORITES_URL",
    "https://translate.google.com/saved",
)
PLAYWRIGHT_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() in ("1", "true", "yes")

# ── Runtime ─────────────────────────────────────────
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "50"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
