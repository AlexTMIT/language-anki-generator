from __future__ import annotations
import base64
from hashlib import md5
from typing import Any

import requests


# ────────────────────────────────────────────────────────────────
# Real AnkiConnect client (unchanged network behaviour)
# ────────────────────────────────────────────────────────────────
class AnkiClient:
    def __init__(
        self,
        endpoint: str = "http://localhost:8765",
        *,
        timeout: int = 15,
    ):
        self.url = endpoint
        self.timeout = timeout
        self.session = requests.Session()  # keep TCP connection open
        self.session.headers["Connection"] = "close"

    # ---------- core RPC -----------------------------------------
    def _rpc(self, action: str, **params: Any) -> Any:
        payload = {"action": action, "version": 6, "params": params}
        res = self.session.post(self.url, json=payload, timeout=self.timeout).json() # connection reset by peer error here
        if res.get("error"):
            raise RuntimeError(res["error"])
        return res["result"]

    # ---------- helpers ------------------------------------------
    def deck_names(self) -> list[str]:
        return self._rpc("deckNames")

    def add_note(
        self, deck: str, model: str, fields: dict, *, allow_dup: bool = False
    ) -> bool:
        note = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "options": {"allowDuplicate": allow_dup},
            "tags": [],
        }
        return self._rpc("addNote", note=note) is not None

    def store_media(self, fname: str, raw: bytes) -> str:
        # skip upload if identical hash already stored
        digest = md5(raw).hexdigest()
        try:
            hit = self._rpc("retrieveMediaFileByHash", hash=digest)
            if hit:
                return hit
        except Exception:
            pass  # older AnkiConnect: just continue to upload

        b64 = base64.b64encode(raw).decode()
        return self._rpc("storeMediaFile", filename=fname, data=b64)

    def ensure_deck(self, name: str) -> None:
        if name not in self.deck_names():
            self._rpc("createDeck", deck=name)

    # duplicate-check helper
    def add_minimal_note(self, deck: str, model: str, word: str) -> int | None:
        fields = {f: "" for f in (
            "Word", "Grammar", "Meaning",
            "Sentence", "Translation", "Audio",
            "Image 1", "Image 2", "Image 3")}
        fields["Word"] = word
        try:
            return self._rpc("addNote", note={
                "deckName": deck,
                "modelName": model,
                "fields": fields,
                "options": {"allowDuplicate": False},
                "tags": ["dupe-check"],
            })
        except RuntimeError as err:
            if "duplicate" in str(err).lower():
                return None
            raise

    def delete_note(self, note_id: int) -> None:
        self._rpc("deleteNotes", notes=[note_id])

    def delete_deck(self, name: str) -> None:
        self._rpc("deleteDecks", decks=[name], cardsToo=True)

    # batch
    def multi(self, actions):
        print("[ANKI] multi call:", [a["action"] for a in actions])
        out = self._rpc("multi", actions=actions)
        print("[ANKI] multi result:", out)
        return out

# ────────────────────────────────────────────────────────────────
# Dummy client for L2_TEST_MODE=1 (no Anki required)
# ────────────────────────────────────────────────────────────────
class DummyAnkiClient:
    """In-memory stub: mimics enough of AnkiConnect for TEST mode."""

    def __init__(self):
        self.decks = {"1TEST_DECK"}
        self.media: dict[str, bytes] = {}
        self.notes: list[dict] = []

    # ---- deck helpers -------------------------------------------
    def deck_names(self) -> list[str]:
        return list(self.decks)

    def ensure_deck(self, name: str) -> None:
        self.decks.add(name)

    # ---- media ---------------------------------------------------
    def store_media(self, fname: str, raw: bytes) -> str:
        self.media[fname] = raw
        return fname

    # ---- note helpers -------------------------------------------
    def add_note(self, *args, **kwargs) -> bool:
        """
        Accept either:
          • add_note(deck, model, fields)
          • add_note(note= {...})   (keyword style used by multi())
        """

        print("[DUMMY] add_note", "kwargs" if kwargs else "positional")

        if kwargs:  # keyword style
            note = kwargs.get("note") or kwargs
            self.notes.append(note)
        else:       # positional style
            deck, model, fields = args[:3]
            self.notes.append(
                {"deckName": deck, "modelName": model, "fields": fields}
            )
        return True

    def add_minimal_note(self, *_, **__) -> int | None:
        # Always pretend word is unique in TEST mode
        return 1

    def delete_note(self, note_id: int) -> None:
        pass

    def delete_deck(self, name: str) -> None:
        self.decks.discard(name)

    # ---- batch ---------------------------------------------------
    def multi(self, actions: list[dict]) -> list:
        results = []
        for act in actions:
            if act["action"] == "storeMediaFile":
                p = act["params"]
                self.store_media(p["filename"], b"dummy")
                results.append(p["filename"])
            elif act["action"] == "addNote":
                self.add_note(note=act["params"]["note"])
                results.append(1)
            else:
                results.append(None)
        return results