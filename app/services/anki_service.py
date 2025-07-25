from __future__ import annotations
import base64
from hashlib import md5
from typing import Any

import requests


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

    # ---------- core RPC -----------------------------------------
    def _rpc(self, action: str, **params: Any) -> Any:
        payload = {"action": action, "version": 6, "params": params}
        res = self.session.post(self.url, json=payload, timeout=self.timeout).json()
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
            msg = str(err).lower()
            if "duplicate" in msg or "identical" in msg:
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