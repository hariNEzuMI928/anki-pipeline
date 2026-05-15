"""Anki card creation via apy (no AnkiConnect needed)."""

import logging
from typing import Any

from apyanki.anki import Anki

from .gtrans.processor import ProcessedWord, ProcessedSentence
from . import config

logger = logging.getLogger(__name__)


def _ensure_model(a: Anki, name: str, fields: list[str], css: str = "") -> int:
    """Create a note model if it doesn't exist; return model ID."""
    models = a.col.models.all_names_and_ids()
    existing = {m.name: m.id for m in models}
    if name in existing:
        logger.info("Model '%s' already exists (id=%d).", name, existing[name])
        return existing[name]

    model = a.col.models.new(name)
    for fname in fields:
        field = a.col.models.new_field(fname)
        a.col.models.add_field(model, field)

    # Add a basic card template (Front → Back)
    template = a.col.models.new_template("Card 1")
    template["qfmt"] = "{{" + fields[0] + "}}"
    template["afmt"] = "{{FrontSide}}\n\n<hr id=answer>\n\n{{" + fields[1] + "}}"
    a.col.models.add_template(model, template)
    a.col.models.add(model)
    model_id = model["id"]
    logger.info("Created model '%s' (id=%d) with fields: %s", name, model_id, fields)
    return model_id


def _ensure_deck(a: Anki, name: str) -> int:
    """Create deck if it doesn't exist; return deck ID."""
    deck_id = a.deck_name_to_id.get(name)
    if deck_id is not None:
        return deck_id
    # Create via collection
    deck = a.col.decks.new(name)
    a.col.decks.add(deck)
    # Re-read
    a.deck_name_to_id = {d.name: d.id for d in a.col.decks.all_names_and_ids()}
    deck_id = a.deck_name_to_id[name]
    logger.info("Created deck '%s' (id=%d).", name, deck_id)
    return deck_id


def ensure_models_and_decks(a: Anki) -> None:
    """Ensure all required card models and decks exist."""
    # Word model: 6 fields matching GTrans-Word note type
    _ensure_model(
        a, config.ANKI_WORD_MODEL,
        ["単語", "フレーズ", "意味", "フレーズの意味", "単語音声", "フレーズ音声"],
    )
    # Sentence model: 2 fields
    _ensure_model(a, config.ANKI_SENTENCE_MODEL, ["Front", "Back"])

    _ensure_deck(a, config.ANKI_WORD_DECK)
    _ensure_deck(a, config.ANKI_SENTENCE_DECK)


def add_word_note(a: Anki, word: ProcessedWord) -> int | None:
    """Add a word card via apy. Returns note ID or None."""
    deck_id = _ensure_deck(a, config.ANKI_WORD_DECK)
    model_id = _ensure_model(
        a, config.ANKI_WORD_MODEL,
        ["単語", "フレーズ", "意味", "フレーズの意味", "単語音声", "フレーズ音声"],
    )
    try:
        note = a.col.new_note(a.col.models.get(model_id))
        note.fields[0] = word.english_word
        note.fields[1] = word.example_sentence
        note.fields[2] = word.japanese_meaning
        note.fields[3] = word.example_translation
        note.fields[4] = ""
        note.fields[5] = ""
        a.col.add_note(note, deck_id)
        a.col.flush()
        logger.info("Added word note: %s", word.english_word)
        return note.id
    except Exception as e:
        logger.error("Failed to add word note: %s", e)
        return None


def add_sentence_note(a: Anki, sentence: ProcessedSentence) -> int | None:
    """Add a sentence card via apy. Returns note ID or None."""
    deck_id = _ensure_deck(a, config.ANKI_SENTENCE_DECK)
    model_id = _ensure_model(a, config.ANKI_SENTENCE_MODEL, ["Front", "Back"])
    try:
        note = a.col.new_note(a.col.models.get(model_id))
        note.fields[0] = sentence.japanese_sentence
        note.fields[1] = sentence.english_sentence
        a.col.add_note(note, deck_id)
        a.col.flush()
        logger.info("Added sentence note: %s", sentence.japanese_sentence[:40])
        return note.id
    except Exception as e:
        logger.error("Failed to add sentence note: %s", e)
        return None
