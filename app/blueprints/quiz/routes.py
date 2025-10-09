from flask import Blueprint, render_template, current_app

bp = Blueprint(
    "quiz", __name__,
    template_folder="../../templates/quiz",
    static_folder="../../static"
)

@bp.get("/quiz")
def index():
    decks = current_app.anki.deck_names()
    return render_template("quiz/quiz.html", decks=decks)