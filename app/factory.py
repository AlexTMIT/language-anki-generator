import os
from flask import Flask

from .config import settings
from .extensions import caches, socketio
from .services.anki_service import AnkiClient
from .blueprints import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=settings.SECRET_KEY.get_secret_value(),
        ANKI_MODEL=settings.ANKI_MODEL,
    )

    app.anki = (
        AnkiClient(settings.ANKICONNECT_ENDPOINT)
    )
    app.caches = caches
    register_blueprints(app)
    socketio.init_app(app)
    return app