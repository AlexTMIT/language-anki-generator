from __future__ import annotations

import json, os
from flask import Blueprint, request, redirect, url_for, flash, session, current_app

from ..tasks.prefetch import prefetch

bp = Blueprint("batch", __name__, url_prefix="/batch")

DUPE_DECK  = "dupe-check"
TEST_DECK  = "1TEST_DECK"
TEST_MODE  = os.getenv("L2_TEST_MODE") == "1"   # local media
OFFLINE    = os.getenv("L2_OFFLINE") == "1"     # DummyAnkiClient


@bp.post("/")
def start() -> str:
    """Parse JSON list → dedupe → prefetch first card → push session."""
    items = parse_json()
    print(f"[BATCH] Received {len(items)} items")

    lang = request.form["lang"]
    anki = current_app.anki
    
    if TEST_MODE and not OFFLINE:
        deck = test_deck_override(anki)
    else:
        deck = request.form["deck"]

    uniques, dup_count = get_unique_items(anki, items)
    print(f"[BATCH] Uniques={len(uniques)} dupes={dup_count}")
    
    prefetch(anki, current_app.caches, uniques[0], lang)
    session.update(cards=uniques, deck=deck, lang=lang, idx=0)

    return redirect(url_for("picker.step"))

def parse_json():
    try:
        items = json.loads(request.form["blob"])
        assert isinstance(items, list)
        return items
    except Exception as err:
        flash(f"<mark>JSON error:</mark> {err}")
        return redirect(url_for("index.index"))

def test_deck_override(anki) -> None:
    anki.delete_deck(TEST_DECK)
    anki.ensure_deck(TEST_DECK)
    return TEST_DECK

def get_unique_items(anki, items: list[dict]):
    anki.ensure_deck(DUPE_DECK)

    uniques: list[dict] = []
    dup_count = 0
    for card in items:
        word = card["base"]
        test_id = anki.add_minimal_note(DUPE_DECK,
                                        current_app.config["ANKI_MODEL"],
                                        word)
        if test_id is None:
            dup_count += 1
            continue
        anki.delete_note(test_id)
        uniques.append(card)

    anki.delete_deck(DUPE_DECK)

    if dup_count:
        flash(f"⚠ Skipped {dup_count} duplicate(s).")
    if not uniques:
        return redirect(url_for("index.index"))

    return uniques, dup_count
