"""Anki sync + state management via apy."""

import logging
import subprocess
import shutil
from pathlib import Path
from apyanki.anki import Anki

from . import config

logger = logging.getLogger(__name__)


def find_anki_pids() -> list[int]:
    """Return PIDs of running Anki processes."""
    try:
        out = subprocess.check_output(["pgrep", "-x", "Anki"], stderr=subprocess.STDOUT)
        return [int(pid) for pid in out.decode().strip().split()]
    except (subprocess.CalledProcessError, ValueError):
        return []


def is_running() -> bool:
    return len(find_anki_pids()) > 0


def close_anki(timeout: int = 15) -> bool:
    """Gracefully quit Anki via AppleScript. Returns True if was running."""
    pids = find_anki_pids()
    if not pids:
        return False
    logger.info("Anki is running (PIDs: %s). Attempting graceful quit…", pids)
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Anki" to quit saving yes'],
            timeout=timeout,
        )
        logger.info("Anki quit signal sent.")
    except subprocess.TimeoutExpired:
        logger.warning("AppleScript timed out — forcing kill")
        for pid in pids:
            subprocess.run(["kill", "-9", str(pid)], timeout=5)
    return True


def get_apy_path() -> Path:
    """Resolve apy binary via mise shim or venv."""
    apy = shutil.which("apy")
    if apy:
        return Path(apy)
    # fallback: see if it's in a project venv
    for venv in [Path.cwd() / ".venv", config.PROJECT_ROOT / ".venv"]:
        candidate = venv / "bin" / "apy"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("apy not found on PATH nor in .venv/bin/apy")


def sync() -> None:
    """Run apy sync to pull/push collection."""
    apy = get_apy_path()
    cmd = [str(apy), "-b", str(config.ANKI_BASE), "-p", config.ANKI_PROFILE, "sync"]
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    logger.info("Sync completed.")


def open_anki_collection() -> Anki:
    """Open a direct apy connection (Anki must NOT be running)."""
    return Anki(base_path=str(config.ANKI_BASE), profile=config.ANKI_PROFILE)


def ensure_synced_env() -> tuple[bool, Anki]:
    """Close Anki if running, sync, return (was_running, Anki handle)."""
    was_running = close_anki()
    sync()
    return was_running, open_anki_collection()
