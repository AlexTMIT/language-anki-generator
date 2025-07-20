from flask import Flask
from .config import settings
from .extensions import executor, caches
from .services.anki_service import AnkiClient
from .blueprints import register_blueprints

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=settings.SECRET_KEY.get_secret_value(),
        ANKI_MODEL=settings.ANKI_MODEL,
    )

    # attach singletons to app context ---------------------------------
    app.anki = AnkiClient(settings.ANKICONNECT_ENDPOINT)
    app.executor = executor
    app.caches = caches  # type: ignore[attr-defined]

    register_blueprints(app)
    return app