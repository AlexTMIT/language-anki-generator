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
    sample_size = int(request.form.get("sample_size", "0").strip() or 0)
    topic = request.form.get("topic", "").strip()

    if not (deck and lang and sample_size and topic):
        flash("Please complete all fields.", "error")
        return redirect(url_for("story.index"))

    svc = StoryService(anki=current_app.anki, story_ai=story_ai, debug=True)

    selected = svc.pick_known_words(deck=deck, sample_size=sample_size, lang=lang)
    text, used = svc.generate_story(lang=lang, topic=topic, required_words=selected)
    html, coverage = svc.highlight_story(text, used)

    return render_template("story/output.html",
                           story_html=html, coverage_pct=coverage,
                           deck=deck, lang=lang, topic=topic)