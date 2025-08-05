from flask import Blueprint, render_template, current_app

bp = Blueprint(
    "flashcards", __name__, url_prefix="/create",
    template_folder="../../templates/flashcards",
    static_folder="../../static"
)

@bp.get("/")
def make_flashcards():
    decks = current_app.anki.deck_names()
    return render_template("flashcards/make_flashcards.html", decks=decks)