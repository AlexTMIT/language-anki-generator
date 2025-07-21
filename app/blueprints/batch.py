from __future__ import annotations
import json
import uuid
from concurrent.futures import as_completed

from flask import Blueprint, request, redirect, url_for, flash, session, current_app

from ..tasks.prefetch import prefetch
from ..extensions import progress, progress_lock

bp = Blueprint("batch", __name__, url_prefix="/batch")

DUPE_DECK = "dupe-check"


@bp.post("/")
def start():
    try:
        items = json.loads(request.form["blob"])
        assert isinstance(items, list), "Expecting a JSON list."
    except Exception as err:
        flash(f"<mark>JSON error:</mark> {err}")
        return redirect(url_for("index.index"))

    deck = request.form["deck"]
    lang = request.form["lang"]

    anki = current_app.anki
    anki.ensure_deck(DUPE_DECK)

    uniques, dup_count, futures = [], 0, []
    for c in items:
        word = c["base"]
        test_id = anki.add_minimal_note(DUPE_DECK, current_app.config["ANKI_MODEL"], word)
        if test_id is None:
            dup_count += 1
            continue
        anki.delete_note(test_id)
        uniques.append(c)
        futures.append(
            current_app.executor.submit(
                prefetch,
                current_app.anki,
                current_app.caches,
                c,
                lang,
            )
        )

    try:
        futures[0].result(timeout=5)
    except Exception as err:
        current_app.logger.warning("Prefetch failed: %s", err)

    if dup_count:
        flash(f"⚠ Skipped {dup_count} duplicate(s) right away.")
    anki.delete_deck(DUPE_DECK)

    if not uniques:
        return redirect(url_for("index.index"))

    sid = uuid.uuid4().hex
    with progress_lock:
        progress[sid] = {"added": 0, "dups": dup_count, "total": len(uniques)}

    session.update(sid=sid, cards=uniques, deck=deck, lang=lang, idx=0)
    return redirect(url_for("picker.step"))