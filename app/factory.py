import os
from flask import Flask

from .config import settings
from .extensions import caches
from .services.anki_service import AnkiClient, DummyAnkiClient
from .blueprints import register_blueprints

TEST    = os.getenv("L2_TEST_MODE") == "1"
OFFLINE = os.getenv("L2_OFFLINE") == "1"

TEST_DECK = "1TEST_DECK"

def create_app() -> Flask:
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=settings.SECRET_KEY.get_secret_value(),
        ANKI_MODEL=settings.ANKI_MODEL,
    )

    # choose real vs. dummy Anki client
    app.anki = (
        DummyAnkiClient() if TEST and OFFLINE
        else AnkiClient(settings.ANKICONNECT_ENDPOINT)
    )

    if TEST and not OFFLINE:
        app.anki.delete_deck(TEST_DECK)
        app.anki.ensure_deck(TEST_DECK)

    app.caches = caches  # type: ignore[attr-defined]

    register_blueprints(app)
    return app