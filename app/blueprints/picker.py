from __future__ import annotations
from flask import Blueprint, current_app, redirect, render_template, request, url_for, flash
from ..tasks.prefetch import prefetch
from ..tasks.save_note import save_note
from ..models.card import CardData

from app.extensions import socketio

bp = Blueprint("picker", __name__, url_prefix="/picker")


@bp.route("/", methods=["GET", "POST"])
def step():
    sid = request.args.get("sid")
    job = current_app.caches["jobs"].get(sid)

    if job is None:
        flash("Import job not found. Please start again.")
        return redirect(url_for("index.index"))

    cards = job["cards"]
    idx   = job.setdefault("idx", 0)

    # ────────── POST: user clicked “Skip” / “Continue” ──────────
    if request.method == "POST":
        action = request.form.get("action", "keep")

        if action == "keep":
            sel_urls = [u for u in request.form.getlist("url") if u and u != "on"]
            uploads  = [(f.filename, f.read()) for f in request.files.getlist("file")]
            rec_b64  = request.form.get("audio_b64", "")

            socketio.start_background_task(
                save_note,
                deck       = job["deck"],
                anki_model = current_app.config["ANKI_MODEL"],
                anki       = current_app.anki,
                caches     = current_app.caches,
                card_dict  = cards[idx],
                sel_urls   = sel_urls,
                uploads    = uploads,
                rec_b64    = rec_b64,
                lang       = job["lang"],
            )
            flash(f"Added “{cards[idx]['base']}” (processing in background)…")
        else:
            flash(f"Skipped “{cards[idx]['base']}”.")

        # advance to next card
        job["idx"] += 1
        if job["idx"] >= len(cards):
            flash("Done! ✅ All cards processed.")
            # clean up
            current_app.caches["jobs"].pop(sid, None)
            return redirect(url_for("index.index"))

        return redirect(url_for("picker.step", sid=sid))

    # ────────── GET: render picker for current card ──────────────
    card = CardData.from_dict(cards[idx])
    urls = current_app.caches["thumb"].get(card.base, [])

    if idx + 1 < len(cards):
        next_card = cards[idx + 1]
        if next_card["base"] not in current_app.caches.get("thumb", {}):
            socketio.start_background_task(
                prefetch,
                current_app.anki,
                current_app.caches,
                next_card,
                job["lang"],
            )

    return render_template(
        "picker.html",
        word = card.base,
        trans= card.translation,
        gram = card.grammar,
        urls = urls,
    )