"""Persistent storage for processed IDs."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_ids(path: Path) -> set[str]:
    if path.exists():
        try:
            with open(path) as f:
                return set(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", path, e)
    return set()


def save_ids(path: Path, ids: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(list(ids), f)
    logger.info("Saved %d IDs to %s.", len(ids), path)
