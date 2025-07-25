from flask import Blueprint, render_template, current_app

bp = Blueprint("index", __name__)

@bp.get("/")
def index():
    decks = current_app.anki.deck_names()

    return render_template(
        "index.html",
        decks=decks,
    )