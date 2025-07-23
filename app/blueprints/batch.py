from __future__ import annotations
import json, os
from flask import Blueprint, request, redirect, url_for, flash, session, current_app, jsonify
from ..tasks.prefetch import prefetch
from ..services.openai_svc import sanitise, make_json
from app.extensions import socketio

bp = Blueprint("batch", __name__, url_prefix="/batch")

DUPE_DECK  = "dupe-check"
TEST_DECK  = "1TEST_DECK"
TEST_MODE  = os.getenv("L2_TEST_MODE") == "1"   # local media
OFFLINE    = os.getenv("L2_OFFLINE") == "1"     # DummyAnkiClient

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

@bp.post("/")
def start() -> str:
    raw = request.form["blob"]

    words = get_sanitised(raw)
    if not words:
        return redirect(url_for("index.index"))
    
    uniq_words = get_unique_words(words)

    items = get_json(uniq_words)
    if not items:
        return redirect(url_for("index.index"))
    print(items)

    print(f"[BATCH] Card-maker returned {len(items)} objects")

    lang = request.form["lang"]
    anki = current_app.anki
    
    if TEST_MODE and not OFFLINE:
        deck = test_deck_override(anki)
    else:
        deck = request.form["deck"]

    uniques = get_unique_items(anki, items)
    _push("Prefetching first card…")
    prefetch(anki, current_app.caches, uniques[0], lang)
    session.update(cards=uniques, deck=deck, lang=lang, idx=0)

    return jsonify({"next": url_for("picker.step")})

def get_sanitised(raw) -> list[str]:
    _push("Sanitising words…")
    try:
        return sanitise(raw)
    except Exception as err:
        flash(f"OpenAI sanitiser error: {err}")
        return []
    
def get_unique_words(words: list[str]) -> list[str]:
    seen, uniq_words = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); uniq_words.append(w)
    print(f"[BATCH] Sanitiser → {len(uniq_words)} unique words")
    _push(f"{len(uniq_words)} unique words.")
    return uniq_words

def get_json(uniq_words: list[str]) -> list[dict]:
    _push("Generating card JSON…")
    try:
        items = make_json(uniq_words)
        _push(f"Received {len(items)} card(s).")
        return items
    except Exception as err:
        flash(f"OpenAI card-maker error: {err}")
        return []

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

    _push(f"Added {len(uniques)} unique card(s).")
    _push(f"Skipped {dup_count} duplicate(s).")

    return uniques
