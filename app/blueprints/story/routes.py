from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ...services.story_service import StoryService
from ...services import story_ai

bp = Blueprint(
    "story", __name__,
    template_folder="../../templates/story",
    static_folder="../../static"
)

@bp.get("/story")
def index():
    decks = current_app.anki.deck_names()
    return render_template("story/story.html", decks=decks)

@bp.post("/story/run")
def run():
    deck = request.form.get("deck", "").strip()
    lang = request.form.get("lang", "").strip()
    known_pct = request.form.get("known_pct", "").strip()
    topic = request.form.get("topic", "").strip()

    if not (deck and lang and known_pct and topic):
        flash("Please complete all fields.", "error")
        return redirect(url_for("story.index"))

    svc = StoryService(anki=current_app.anki, story_ai=story_ai, debug=True)

    pct = int(known_pct)
    try:
        selected = svc.pick_known_words(deck=deck, target_pct=pct, lang=lang)
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("story.index"))
    
    text, used = svc.generate_story(lang=lang, topic=topic, required_words=selected, target_pct=pct)
    html, coverage = svc.highlight_story(text, used)

    return render_template("story/output.html",
                           story_html=html, coverage_pct=coverage,
                           deck=deck, lang=lang, topic=topic)