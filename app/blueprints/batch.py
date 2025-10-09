from __future__ import annotations
import secrets
from flask import Blueprint, request, flash, current_app, jsonify, copy_current_request_context, url_for

from app.utils import tracker
from ..tasks.prefetch import prefetch
from ..services.openai_svc import sanitise, make_json
from app.extensions import socketio
from app.utils.tracker import ProgressTracker

bp = Blueprint("batch", __name__, url_prefix="/batch")

# Deck names
DUPE_DECK = "dupe-check"

@bp.post("/")
def start():
    sid = request.args.get("sid") or secrets.token_urlsafe(8)

    form = request.form.to_dict()
    lang = form.get("lang") or "Unknown"

    # queue it for later – picked up when the loader connects
    cache = current_app.caches.setdefault("pending_jobs", {})
    cache[sid] = dict(form=form, lang=lang)

    next_url = url_for("flashcards.load", wf="flashcards", sid=sid)
    return jsonify(next_url=next_url)

class BatchProcessor:
    def __init__(self, anki_client, cache_store: dict, sid: str, lang: str) -> None:
        self.anki = anki_client
        self.caches = cache_store
        self.sid = sid
        self.lang = lang
        self.tracker = ProgressTracker(
            sid,
            [
                ("sanitize",   "Sanitising word list",            None),
                ("dupes_imm",  "Removing immediate duplicates",   None),
                ("json",       "Generating JSON from words",      None),
                ("dupes_sub",  "Removing subsequent duplicates",  None),
                ("prefetch",   "Prefetching media",               2),
                ("init_picker","Initiating image selection",      1),
            ],
        )

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
            words = self._dedupe_words(words)          # returns unique list
            cards_raw = self._generate_json(words)
            cards = self._dedupe_cards(cards_raw)
            self._prefetch_media(cards[:2], form.get("lang"))
            self.tracker.start("init_picker")
            self.tracker.done("init_picker")
            self._store_results(cards, form)
            socketio.emit("done", {"next": f"/picker/?sid={self.sid}"}, to=self.sid)
        except BatchError as err:
            self.tracker.fail("init_picker", err)
            print(f"[BATCH] Error: {err}")

    def _sanitize(self, blob:str) -> list[str]:
        exp = 3 + 0.2 * blob.count(",")          # crude word count
        self.tracker.start("sanitize")
        cancel = self.tracker.interpolate("sanitize", exp)

        try:
            words = sanitise(blob, self.lang)
            self.tracker.set_total("sanitize", 100)
        except Exception as exc:
            self.tracker.fail("sanitize", exc)
            raise BatchError(f"Sanitiser failed: {exc}") from exc
        finally:
            cancel()

        self.tracker.done("sanitize")
        return words

    def _dedupe(self, items, is_card: bool, step_id: str):
        self.tracker.start(step_id)

        self.anki.ensure_deck(DUPE_DECK)
        fresh, dup = [], 0
        total      = len(items)
        self.tracker.set_total(step_id, total)

        try:
            for idx, it in enumerate(items, 1):
                base = it["base"] if is_card else it
                note_id = self.anki.add_minimal_note(
                    DUPE_DECK, current_app.config["ANKI_MODEL"], base
                )
                if note_id is None:
                    dup += 1
                else:
                    self.anki.delete_note(note_id)
                    fresh.append(it)

                self.tracker.progress(step_id, idx, total)

        finally:
            self.anki.delete_deck(DUPE_DECK)

        if not fresh:
            self.tracker.fail(step_id, BatchError("No new items to add."))
            raise BatchError("No new items to add.")

        self.tracker.done(step_id)
        return fresh

    def _dedupe_words(self, words: list[str]) -> list[str]:
        return self._dedupe(words, False, "dupes_imm")

    def _dedupe_cards(self, cards: list[dict]) -> list[dict]:
        return self._dedupe(cards, True,  "dupes_sub")

    def _generate_json(self, words: list[str]) -> list[dict]:
        exp = 20 + 2 * len(words)
        self.tracker.start("json")
        cancel = self.tracker.interpolate("json", exp)

        try:
            items = make_json(words, self.lang)
            self.tracker.set_total("json", 100)
        except Exception as exc:
            self.tracker.fail("json", exc)
            raise BatchError(f"Card maker failed: {exc}") from exc
        finally:
            cancel()

        self.tracker.done("json")
        return items

    def _prefetch_media(self, two_cards:list[dict], lang:str|None):
        self.tracker.start("prefetch")
        total = len(two_cards)
        for idx, card in enumerate(two_cards, 1):
            try:
                prefetch(self.anki, self.caches, card, lang)
                self.tracker.progress("prefetch", idx, total)
            except Exception as exc:
                self.tracker.fail("prefetch", exc)
                raise BatchError(f"Media prefetch failed: {exc}") from exc
        self.tracker.done("prefetch")

    def _store_results(self, cards: list[dict], form: dict) -> None:
        self.caches["jobs"][self.sid] = {
            "cards": cards,
            "deck": form.get("deck"),
            "lang": form.get("lang"),
        }


class BatchError(Exception):
    """Indicates a failure in the batch processing pipeline."""
    pass
