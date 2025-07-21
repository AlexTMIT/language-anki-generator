from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, request, \
                  session, url_for, flash

from ..tasks.prefetch import prefetch
from ..tasks.save_note import save_note
from ..models.card import CardData

bp = Blueprint("picker", __name__, url_prefix="/picker")


@bp.route("/", methods=["GET", "POST"])
def step():
    if "cards" not in session:
        return redirect(url_for("index.index"))

    idx  = session["idx"]
    cards = session["cards"]

    # ───── POST: user picked images ────────────────────────────────
    if request.method == "POST":
        action   = request.form.get("action", "keep")

        if action == "keep":
            sel_urls = request.form.getlist("url")
            uploads  = [(f.filename, f.read())
                        for f in request.files.getlist("file")]
            rec_b64    = request.form.get("audio_b64", "")

            save_note(
                deck=session["deck"],
                anki_model=current_app.config["ANKI_MODEL"],
                anki=current_app.anki,
                caches=current_app.caches,
                card_dict=cards[idx],
                sel_urls=sel_urls,
                uploads=uploads,
                rec_b64=rec_b64,
            )
            flash(f"Added “{cards[idx]['base']}”.")
        else:
            print(f"Skipping card {idx} with base {cards[idx]['base']}")
            flash(f"Skipped “{cards[idx]['base']}”.")

        # advance to next card
        session["idx"] += 1
        if session["idx"] >= len(cards):
            flash("Done! ✅ All cards processed.")
            return redirect(url_for("index.index"))

        # Prefetch next card (synchronous, no threads)
        next_card = cards[session["idx"]]
        prefetch(current_app.anki, current_app.caches,
                 next_card, session["lang"])

        return redirect(url_for("picker.step"))

    # ───── GET: show picker for current card ───────────────────────
    card = CardData.from_dict(cards[idx])
    urls = current_app.caches["thumb"].get(card.base, [])

    return render_template(
        "picker.html",
        word=card.base,
        trans=card.translation,
        gram=card.grammar,
        urls=urls,
    )