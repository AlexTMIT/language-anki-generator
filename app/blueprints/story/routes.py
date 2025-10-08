from flask import Blueprint, render_template, current_app

bp = Blueprint(
    "story", __name__,
    template_folder="../../templates/story",
    static_folder="../../static"
)

@bp.get("/story")
def index():
    decks = current_app.anki.deck_names()
    return render_template("story/story.html", decks=decks)