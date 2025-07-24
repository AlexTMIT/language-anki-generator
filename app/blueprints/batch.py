from __future__ import annotations
import os
from flask import Blueprint, request, flash, current_app, jsonify, copy_current_request_context
from ..tasks.prefetch import prefetch
from ..services.openai_svc import sanitise, make_json
from app.extensions import socketio


bp = Blueprint("batch", __name__, url_prefix="/batch")

# Environment flags
TEST_MODE = os.getenv("L2_TEST_MODE") == "1"
OFFLINE = os.getenv("L2_OFFLINE") == "1"

# Deck names
DUPE_DECK = "dupe-check"
TEST_DECK = "1TEST_DECK"


@bp.post("/")
def start() -> jsonify:
    """
    Kick off the background batch job.
    """
    sid = request.args.get("sid")
    form = request.form.to_dict()

    @copy_current_request_context
    def background_task() -> None:
        processor = BatchProcessor(current_app.anki, current_app.caches, sid)
        processor.run(form)

    socketio.start_background_task(background_task)
    return jsonify(started=True)


class BatchProcessor:
    """
    Encapsulates batch processing: sanitising, de-duplicating, and preparing cards.
    """

    def __init__(self, anki_client, cache_store: dict, sid: str) -> None:
        self.anki = anki_client
        self.caches = cache_store
        self.sid = sid

    def push(self, message: str) -> None:
        """Emit a progress message over Socket.IO."""
        socketio.emit("progress", message, to=self.sid)
        socketio.sleep(0)

    def run(self, form: dict) -> None:
        """
        Execute the full batch pipeline.
        """
        try:
            words = self._sanitize(form.get("blob", ""))
            unique_words = self._unique(words)
            items = self._generate_json(unique_words)
            cards, duplicates = self._filter_duplicates(items)
            self._prefetch_media(cards[0], form.get("lang"))
            self._store_results(cards, form)
            self.push("All done! Opening picker…")
            socketio.emit("done", {"next": f"/picker/?sid={self.sid}"}, to=self.sid)
        except BatchError as err:
            self.push(f"❌ {err}")
            flash(str(err))

    def _sanitize(self, blob: str) -> list[str]:
        self.push("Sanitising words…")
        try:
            words = sanitise(blob)
            self.push(f"→ {len(words)} token(s)")
            return words
        except Exception as exc:
            raise BatchError(f"Sanitiser failed: {exc}")

    def _unique(self, words: list[str]) -> list[str]:
        self.push("Filtering unique words…")
        seen = set()
        unique_list = [w for w in words if w not in seen and not seen.add(w)]
        self.push(f"→ {len(unique_list)} unique")
        return unique_list

    def _generate_json(self, words: list[str]) -> list[dict]:
        self.push("Calling GPT for card JSON…")
        try:
            items = make_json(words)
            self.push(f"→ {len(items)} card(s) received")
            return items
        except Exception as exc:
            raise BatchError(f"Card maker failed: {exc}")

    def _filter_duplicates(self, items: list[dict]) -> tuple[list[dict], int]:
        self.push("Removing duplicates in Anki…")
        self.anki.ensure_deck(DUPE_DECK)
        new_cards: list[dict] = []
        dup_count = 0

        for card in items:
            note_id = self.anki.add_minimal_note(
                DUPE_DECK,
                current_app.config["ANKI_MODEL"],
                card["base"],
            )
            if note_id is None:
                dup_count += 1
                continue
            self.anki.delete_note(note_id)
            new_cards.append(card)

        self.anki.delete_deck(DUPE_DECK)
        if dup_count:
            flash(f"⚠ Skipped {dup_count} duplicate(s).")
        if not new_cards:
            raise BatchError("No new cards to add.")

        self.push(f"→ {len(new_cards)} new / {dup_count} duplicate(s)")
        return new_cards, dup_count

    def _prefetch_media(self, card: dict, lang: str | None) -> None:
        self.push("Prefetching media…")
        try:
            prefetch(self.anki, self.caches, card, lang)
            self.push("→ Media ready")
        except Exception as exc:
            raise BatchError(f"Media prefetch failed: {exc}")

    def _store_results(self, cards: list[dict], form: dict) -> None:
        self.caches["jobs"][self.sid] = {
            "cards": cards,
            "deck": form.get("deck"),
            "lang": form.get("lang"),
        }


class BatchError(Exception):
    """Indicates a failure in the batch processing pipeline."""
    pass
