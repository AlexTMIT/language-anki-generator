from flask import Flask, send_from_directory
from . import index, batch, picker

import os, pathlib

TEST_MODE = os.getenv("L2_TEST_MODE") == "1"
ASSET_DIR = pathlib.Path(__file__).parent.parent / "test_assets"

def register_blueprints(app: Flask) -> None:
    app.register_blueprint(index.bp)
    app.register_blueprint(batch.bp)
    app.register_blueprint(picker.bp)

    if TEST_MODE:
        @app.route("/static/test/thumbs/<path:fname>")
        def _test_thumb(fname):
            return send_from_directory(ASSET_DIR / "thumbs", fname)