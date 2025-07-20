from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, flash

from ..extensions import progress, progress_lock
from ..tasks.save_note import save_note_async
from ..services.image_service import google_thumbs
from ..models.card import CardData

bp = Blueprint("picker", __name__, url_prefix="/picker")


@bp.route("/", methods=["GET", "POST"])
def step():
    if "cards" not in session:
        return redirect(url_for("index.index"))

    idx = session["idx"]
    cards = session["cards"]

    if request.method == "POST":
        sel_urls = request.form.getlist("url")
        uploads = [(f.filename, f.read()) for f in request.files.getlist("file")]

        current_app.executor.submit(
            save_note_async,
            session["sid"],
            session["deck"],
            current_app.config["ANKI_MODEL"],
            current_app.anki,
            current_app.caches,
            cards[idx],
            sel_urls,
            uploads,
        )

        session["idx"] += 1
        if session["idx"] >= len(cards):
            with progress_lock:
                p = progress.get(session["sid"], {})
                added = p.get("added", 0)
                dups = p.get("dups", 0)
                total = p.get("total", len(cards))

            if added + dups < total:
                flash(f"Cards are still saving in the background… {added}/{total} done so far. You can safely leave this page.")
            else:
                flash(f"Done! ✅ {added} added | ⚠ {dups} duplicates")
                with progress_lock:
                    progress.pop(session["sid"], None)
            return redirect(url_for("index.index"))

        return redirect(url_for("picker.step"))

    card = CardData.from_dict(cards[idx])
    urls = current_app.caches["thumb"].get(card.base) or google_thumbs(card.keyword)
    return render_template(
        "picker.html",
        word=card.base,
        trans=card.translation,
        gram=card.grammar,
        urls=urls,
    )