from __future__ import annotations
import base64
from typing import Any
import requests
from hashlib import md5

class AnkiClient:
    def __init__(self, endpoint: str = "http://localhost:8765", *, timeout: int = 15):
        self.url     = endpoint
        self.timeout = timeout
        self.session = requests.Session() # keep connection open

    def _rpc(self, action: str, **params: Any) -> Any:
        payload = {"action": action, "version": 6, "params": params}
        res = self.session.post(self.url, json=payload, timeout=self.timeout).json()
        if res.get("error"):
            raise RuntimeError(res["error"])
        return res["result"]

    # public helpers -------------------------------------------------
    def deck_names(self) -> list[str]:
        return self._rpc("deckNames")

    def add_note(self, deck: str, model: str, fields: dict, *, allow_dup: bool=False) -> bool:
        note = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "options": {"allowDuplicate": allow_dup},
            "tags": [],
        }
        print(f"Adding note to deck '{deck}' with model '{model}' and fields: {fields}")
        return self._rpc("addNote", note=note) is not None

    def store_media(self, fname: str, raw: bytes) -> str:
        digest = md5(raw).hexdigest()
        try:
            hit = self._rpc("retrieveMediaFileByHash", hash=digest)
            if hit:
                return hit   # already stored, reuse
        except Exception:
            print("new shidd did nottin")
            pass  # method may not exist; ignore

        b64 = base64.b64encode(raw).decode()
        return self._rpc("storeMediaFile", filename=fname, data=b64)
    
    def ensure_deck(self, name: str) -> None:
        """Create *name* if it doesn't already exist."""
        if name not in self.deck_names():
            self._rpc("createDeck", deck=name)

    # --- helper for duplicate testing --------------------------------
    def add_minimal_note(self, deck: str, model: str, word: str) -> int | None:
        fields = {f: "" for f in (
            "Word", "Grammar", "Meaning",
            "Sentence", "Translation",
            "Audio", "Image 1", "Image 2", "Image 3")}
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

    def multi(self, actions: list[dict]) -> list:
        return self._rpc("multi", actions=actions)