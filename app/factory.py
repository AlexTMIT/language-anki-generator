import os
import time
import platform
import subprocess
import requests
from flask import Flask, current_app

from .config import settings
from .extensions import caches, socketio
from .services.anki_service import AnkiClient, DummyAnkiClient
from .blueprints import register_blueprints

TEST      = os.getenv("L2_TEST_MODE") == "1"
OFFLINE   = os.getenv("L2_OFFLINE") == "1"
TEST_DECK = "1TEST_DECK"

ANKI_CONNECT_URL = None  # will be set from settings when app is created

def ensure_anki_running(endpoint: str, timeout: float = 10.0, interval: float = 0.5) -> bool:
    """
    Ensure AnkiConnect at `endpoint` is listening; if not, try to launch Anki
    and poll until it responds or timeout is reached.
    """
    # quick check
    try:
        requests.post(endpoint, json={"action": "version", "version": 6}, timeout=1)
        return True
    except requests.exceptions.RequestException:
        pass

    # not responding: launch native Anki
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(["start", "anki"], shell=True)
    elif system == "Darwin":
        subprocess.Popen(["open", "-a", "Anki"])
    else:
        subprocess.Popen(["anki"])
    current_app.logger.info("Launched Anki, waiting for AnkiConnect...")

    # poll
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.post(endpoint, json={"action": "version", "version": 6}, timeout=1)
            return True
        except requests.exceptions.RequestException:
            time.sleep(interval)

    current_app.logger.error("AnkiConnect did not respond in time.")
    return False


def create_app() -> Flask:
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=settings.SECRET_KEY.get_secret_value(),
        ANKI_MODEL=settings.ANKI_MODEL,
    )

    # ---------------- Anki client -----------------
    endpoint = settings.ANKICONNECT_ENDPOINT
    global ANKI_CONNECT_URL
    ANKI_CONNECT_URL = endpoint
    app.anki = (
        DummyAnkiClient() if TEST and OFFLINE
        else AnkiClient(endpoint)
    )

    if not TEST and not OFFLINE:
        # ensure AnkiConnect is up and running
        with app.app_context():
            if not ensure_anki_running(endpoint):
                app.logger.error("Failed to connect to AnkiConnect. Exiting.")
                raise RuntimeError("AnkiConnect is not available.")

    if TEST and not OFFLINE:
        app.anki.delete_deck(TEST_DECK)
        app.anki.ensure_deck(TEST_DECK)

    # ---------------- shared state ----------------
    app.caches = caches

    # ---------------- blueprints ------------------
    register_blueprints(app)

    # attach Socket.IO
    socketio.init_app(app)
    return app