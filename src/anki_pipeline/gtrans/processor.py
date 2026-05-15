"""Gemini-based processing of GTranslate favorites — ported from GTrans-Favorites-to-Anki."""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Literal, Optional

import google.genai as genai
from google.api_core.exceptions import GoogleAPIError

from .. import config
from .scraper import FavoriteItem

logger = logging.getLogger(__name__)


@dataclass
class ProcessedWord:
    english_word: str
    example_sentence: str
    japanese_meaning: str
    example_translation: str


@dataclass
class ProcessedSentence:
    japanese_sentence: str
    english_sentence: str


@dataclass
class ProcessedItem:
    item_id: str
    type: Literal["word", "sentence"]
    data: ProcessedWord | ProcessedSentence


class GeminiProcessor:
    MAX_RETRIES = 3

    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
        )

    def process_item(self, item: FavoriteItem, retry_count: int = 0) -> Optional[ProcessedItem]:
        prompt = f"""Given a text and its translation from Google Translate favorites:

- **Text:** {item.text}
- **Translated Text:** {item.translation}

Task:
1. Determine if the text is a 'word/phrase' (not a complete sentence) or a 'sentence' (complete grammatical sentence).
2. If it's a 'word/phrase':
    - Provide a natural, contextually relevant English example sentence.
    - Provide the Japanese meaning of the word/phrase.
    - Provide the Japanese translation of the example sentence.
3. If it's a 'sentence':
    - Use the provided Japanese translation.

Return a JSON object matching this schema:
- For 'word':
  {{
    "type": "word",
    "data": {{
      "english_word": "...",
      "example_sentence": "...",
      "japanese_meaning": "...",
      "example_translation": "..."
    }}
  }}
- For 'sentence':
  {{
    "type": "sentence",
    "data": {{
      "english_sentence": "...",
      "japanese_sentence": "..."
    }}
  }}
"""
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            start = text.index("{")
            end = text.rindex("}")
            data = json.loads(text[start : end + 1])

            item_type = data.get("type")
            item_data = data.get("data")
            if not item_type or not item_data:
                return None

            if item_type == "word":
                return ProcessedItem(
                    item_id=item.item_id,
                    type="word",
                    data=ProcessedWord(
                        english_word=item_data.get("english_word", ""),
                        example_sentence=item_data.get("example_sentence", ""),
                        japanese_meaning=item_data.get("japanese_meaning", ""),
                        example_translation=item_data.get("example_translation", ""),
                    ),
                )
            elif item_type == "sentence":
                return ProcessedItem(
                    item_id=item.item_id,
                    type="sentence",
                    data=ProcessedSentence(
                        japanese_sentence=item_data.get("japanese_sentence", ""),
                        english_sentence=item_data.get("english_sentence", ""),
                    ),
                )
            return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Gemini parse error: %s", e)
            return None
        except GoogleAPIError as e:
            if "429" in str(e) and retry_count < self.MAX_RETRIES:
                delay = 5.0
                m = re.search(r"Please retry in ([\d.]+)s", str(e))
                if m:
                    delay = float(m.group(1))
                time.sleep(delay + 1)
                return self.process_item(item, retry_count + 1)
            logger.error("Gemini API error: %s", e)
            return None
