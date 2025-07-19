import requests

class AnkiClient:
    def __init__(self, endpoint: str = "http://localhost:8765"):
        self.url = endpoint

    # ---- internal helper -------------------------------------------------
    def _rpc(self, action: str, **params):
        payload = {"action": action, "version": 6, "params": params}
        response = requests.post(self.url, json=payload, timeout=20).json()
        if response.get("error"):
            raise RuntimeError(f"AnkiConnect error: {response['error']}")
        return response["result"]

    # ---- public API ------------------------------------------------------
    def deck_names(self) -> list[str]:
        return self._rpc("deckNames")

    def add_note(
        self,
        deck: str,
        model: str,
        fields: dict[str, str],
        allow_dup: bool = False,
    ) -> bool:
        note = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "options": {"allowDuplicate": allow_dup},
            "tags": [],
        }
        # returns note ID (int) on success, None on duplicate
        return self._rpc("addNote", note=note) is not None