import requests
import base64

class AnkiClient:
    def __init__(self, endpoint: str = "http://localhost:8765"):
        self.url = endpoint

    def _rpc(self, action: str, **params):
        payload = {"action": action, "version": 6, "params": params}
        r = requests.post(self.url, json=payload, timeout=15).json()
        if r.get("error"):
            raise RuntimeError(r["error"])
        return r["result"]

    # public helpers -------------------------------------------------------
    def deck_names(self) -> list[str]:
        return self._rpc("deckNames")

    def add_note(self, deck: str, model: str, fields: dict, allow_dup=False) -> bool:
        note = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,   
            "options": {"allowDuplicate": allow_dup},
            "tags": [],
        }
        return self._rpc("addNote", note=note) is not None
    
    def store_media(self, fname: str, raw: bytes) -> str:
        b64 = base64.b64encode(raw).decode()
        return self._rpc("storeMediaFile", filename=fname, data=b64)
    
    def has_note_with_word(self, model: str, word: str) -> bool:
        query = f'note:"{model}" Word:"{word}"'
        ids = self._rpc("findNotes", query=query)
        return bool(ids)
    
    # -------- duplicate test via dummy deck -----------------------------
    def ensure_deck(self, name: str):
        if name not in self.deck_names():
            self._rpc("createDeck", deck=name)

    def add_minimal_note(self, deck: str, model: str, word: str) -> int | None:
        fields = {f: "" for f in ("Word", "Grammar", "Meaning",
                                "Sentence", "Translation",
                                "Audio", "Image 1", "Image 2", "Image 3")}
        fields["Word"] = word
        try:
            return self._rpc("addNote", note={
                "deckName": deck,
                "modelName": model,
                "fields": fields,
                "options": {"allowDuplicate": False},
                "tags": ["dupe-check"]
            })
        except RuntimeError as e:
            # AnkiConnect signals duplicates with this exact message
            if "duplicate" in str(e):
                return None          # tell caller “already exists”
            raise                   # real error → re-raise

    def delete_note(self, note_id: int):
        self._rpc("deleteNotes", notes=[note_id])

    def delete_deck(self, name: str):
        if name in self.deck_names():
            self._rpc("deleteDecks", decks=[name], cardsToo=True)