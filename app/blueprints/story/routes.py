from flask import Blueprint, flash, redirect, render_template, current_app, request, url_for

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

    svc = StoryService(
        anki=current_app.anki,
        openai_svc=current_app.openai_svc
    )

    try:
        pct = int(known_pct)
        selected_words = svc.pick_known_words(deck=deck, target_pct=pct, lang=lang)
        story_text, used_words = svc.generate_story(
            lang=lang, topic=topic, required_words=selected_words, target_pct=pct
        )
        highlighted_html, coverage = svc.highlight_story(story_text, used_words)

        return render_template(
            "story/output.html",
            story_html=highlighted_html,
            coverage_pct=coverage,
            deck=deck,
            lang=lang,
            topic=topic
        )
    except Exception as e:
        flash(f"Story generation failed: {e}", "error")
        return redirect(url_for("story.index"))