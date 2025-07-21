from flask import Blueprint, render_template, current_app
import os, pathlib

bp = Blueprint("index", __name__)

TEST_MODE = os.getenv("L2_TEST_MODE") == "1"
ASSET_DIR = pathlib.Path(__file__).parent.parent / "test_assets"

@bp.get("/")
def index():
    sample_json = ""
    if TEST_MODE:
        try:
            sample_json = (ASSET_DIR / "test_cards.json").read_text()
        except FileNotFoundError:
            sample_json = "[\n  { \"base\": \"demo\", ... }\n]"

    decks = current_app.anki.deck_names()
    if TEST_MODE and "1TEST_DECK" not in decks:
        decks.append("1TEST_DECK")

    return render_template(
        "index.html",
        decks=decks,
        sample_json=sample_json
    )