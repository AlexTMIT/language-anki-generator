from __future__ import annotations
from flask import Blueprint, request, flash, current_app, jsonify, copy_current_request_context
from ..tasks.prefetch import prefetch
from ..services.openai_svc import sanitise, make_json
from app.extensions import socketio


bp = Blueprint("batch", __name__, url_prefix="/batch")

# Deck names
DUPE_DECK = "dupe-check"

@bp.post("/")
def start() -> jsonify:
    sid = request.args.get("sid")
    form = request.form.to_dict()
    lang = form.get("lang") or "Unknown"

    @copy_current_request_context
    def background_task() -> None:
        processor = BatchProcessor(current_app.anki, current_app.caches, sid, lang)
        processor.run(form)

    socketio.start_background_task(background_task)
    return jsonify(started=True)


class BatchProcessor:
    def __init__(self, anki_client, cache_store: dict, sid: str, lang: str) -> None:
        self.anki = anki_client
        self.caches = cache_store
        self.sid = sid
        self.lang = lang

    def push(self, message: str) -> None:
        """Emit a progress message over Socket.IO."""
        socketio.emit("progress", message)
        socketio.sleep(0)

    def run(self, form: dict) -> None:
        """
        Execute the full batch pipeline.
        """
        try:
            words = self._sanitize(form.get("blob", ""))
            words = self._unique(words)
            words, dup_words = self._filter_duplicates(words)
            cards_raw = self._generate_json(words)
            cards, dup_cards = self._filter_duplicates(cards_raw)
            self._prefetch_media(cards[0], form.get("lang"))
            self._store_results(cards, form)
            total_dups = dup_words + dup_cards
            self.push(f"Removed this many duplicates: {total_dups}")
            socketio.emit("done", {"next": f"/picker/?sid={self.sid}"}, to=self.sid)

        except BatchError as err:
            print(f"[BATCH] Error: {err}")
            self.push(f"❌ {err}")

    def _sanitize(self, blob: str) -> list[str]:
        self.push("Sanitising words…")
        try:
            words = sanitise(blob, self.lang)
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
            items = make_json(words, self.lang)
            self.push(f"→ {len(items)} card(s) received")
            return items
        except Exception as exc:
            raise BatchError(f"Card maker failed: {exc}")

    def _filter_duplicates(
        self, items: list[str] | list[dict]
    ) -> tuple[list[str] | list[dict], int]:
        self.push("Removing duplicates in Anki…")
        self.anki.ensure_deck(DUPE_DECK)
        fresh: list[str] | list[dict] = []
        dup_count = 0

        try:
            for it in items:
                base = it["base"] if isinstance(it, dict) else it
                note_id = self.anki.add_minimal_note(
                    DUPE_DECK,
                    current_app.config["ANKI_MODEL"],
                    base,
                )
                if note_id is None:
                    dup_count += 1
                    continue
                self.anki.delete_note(note_id)        # clean up temp note
                fresh.append(it)
        finally:
            self.anki.delete_deck(DUPE_DECK)

        if dup_count:
            flash(f"⚠ Skipped {dup_count} duplicate(s).")
        if not fresh:
            raise BatchError("No new items to add.")

        self.push(f"→ {len(fresh)} new / {dup_count} duplicate(s)")
        return fresh, dup_count

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
