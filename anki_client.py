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
        """Save raw bytes to Anki’s collection and return the stored filename."""
        b64 = base64.b64encode(raw).decode()
        return self._rpc("storeMediaFile", filename=fname, data=b64)