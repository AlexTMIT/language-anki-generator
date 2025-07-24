from __future__ import annotations
import json, os
from flask import Blueprint, request, redirect, url_for, flash, current_app, jsonify, copy_current_request_context
from ..tasks.prefetch import prefetch
from ..services.openai_svc import sanitise, make_json
from app.extensions import socketio

bp = Blueprint("batch", __name__, url_prefix="/batch")

DUPE_DECK  = "dupe-check"
TEST_DECK  = "1TEST_DECK"
TEST_MODE  = os.getenv("L2_TEST_MODE") == "1"   # local media
OFFLINE    = os.getenv("L2_OFFLINE") == "1"     # DummyAnkiClient

@bp.post("/")
def start():
    sid  = request.args.get("sid")
    form = request.form.to_dict()

    @copy_current_request_context
    def task():
        long_job(form, sid)

    socketio.start_background_task(task)
    return jsonify(started=True)

def long_job(form: dict, sid: str) -> None:
    # helper to stream progress
    def push(msg: str):
        socketio.emit("progress", msg, to=sid)
        socketio.sleep(0)

    # 1️⃣ sanitise -------------------------------------------------
    push("Sanitising words…")
    words = sanitise(form["blob"])
    push(f"→ {len(words)} token(s)")

    # 2️⃣ uniques -------------------------------------------------
    push("Filtering unique words…")
    uniq_words = get_unique_words(words)
    push(f"→ {len(uniq_words)} unique")

    # 3️⃣ GPT JSON ------------------------------------------------
    push("Calling GPT for card JSON…")
    items = get_json(uniq_words)
    push(f"→ {len(items)} card(s) received")

    # 4️⃣ de-dupe in Anki ----------------------------------------
    push("Removing duplicates in Anki…")
    uniques, dup_cnt = get_unique_items(current_app.anki, items)
    push(f"→ {len(uniques)} new / {dup_cnt} duplicate(s)")

    # 5️⃣ prefetch media -----------------------------------------
    push("Prefetching media…")
    prefetch(current_app.anki, current_app.caches, uniques[0], form["lang"])
    push("→ Media ready")

    # 6️⃣ store job result into the user’s session ---------------
    current_app.caches["jobs"][sid] = {
        "cards": uniques,
        "deck":  form["deck"],
        "lang":  form["lang"],
    }

    # 7️⃣ let the browser move on --------------------------------
    push("All done! Opening picker…")
    next_url = f"/picker/?sid={sid}"
    socketio.emit("done", {"next": next_url}, to=sid)

def get_sanitised(raw) -> list[str]:
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
    return uniq_words

def get_json(uniq_words: list[str]) -> list[dict]:
    try:
        items = make_json(uniq_words)
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

    return uniques, dup_count
