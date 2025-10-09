from __future__ import annotations
import base64
from hashlib import md5
import subprocess
import sys
import time
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
        self._ensure_anki_running()

    def _ensure_anki_running(self, retries: int = 5, delay: float = 1.0) -> None:
        """
        Make sure AnkiConnect is reachable. If not, launch Anki once and retry.
        """
        for attempt in range(retries):
            try:
                self._rpc("version")
                return
            except Exception:
                if attempt == 0:
                    print("[ANKI] AnkiConnect not reachable, launching Anki…")
                    try:
                        if sys.platform == "darwin":
                            subprocess.Popen(["open", "-a", "Anki"])
                        elif sys.platform.startswith("win"):
                            # Windows: rely on PATH or file association
                            subprocess.Popen(["cmd", "/c", "start", "", "anki"])
                        else:
                            # Linux: assume 'anki' is in PATH
                            subprocess.Popen(["anki"])
                    except Exception as launch_err:
                        print(f"[ANKI] Failed to launch Anki: {launch_err!r}")
                print(f"[ANKI] Waiting {delay:.1f}s for AnkiConnect (attempt {attempt+1}/{retries})")
                time.sleep(delay)

        raise RuntimeError("Unable to connect to AnkiConnect after launching Anki.")


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

    # get words from a deck
    def find_notes(self, deck: str) -> list[int]:
        return self._rpc("findNotes", query=f'deck:"{deck}"')

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        if not note_ids:
            return []
        return self._rpc("notesInfo", notes=note_ids)

    def get_words(
        self,
        deck: str,
        field_priority: tuple[str, ...] = ("Word", "Expression", "Front", "Back", "Term"),
    ) -> list[str]:
        t0 = time.perf_counter()
        note_ids = self.find_notes(deck)
        notes = self.notes_info(note_ids)

        out: list[str] = []
        for n in notes:
            fields = (n.get("fields") or {})
            val = None
            for fld in field_priority:
                cell = fields.get(fld)
                if cell:
                    v = (cell.get("value") or "").strip()
                    if v:
                        val = v
                        break
            if val:
                out.append(val)

        # de-dupe, case-insensitive
        seen, uniq = set(), []
        for w in out:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                uniq.append(w)

        print(f"[ANKI] get_words: deck='{deck}', notes={len(notes)}, words={len(uniq)}, took={time.perf_counter()-t0:.2f}s")
        return uniq
    
    def get_seen_note_ids(self, deck: str) -> list[int]:
        card_ids = self._rpc("findCards", query=f'deck:"{deck}" -is:new')
        if not card_ids:
            return []
        cards = self._rpc("cardsInfo", cards=card_ids)
        # dedupe notes
        return list({c["note"] for c in cards})

    def _extract_words_from_notes(self, notes: list[dict],
                                field_priority: tuple[str, ...] = ("Word","Expression","Front","Back","Term")
                                ) -> list[str]:
        out: list[str] = []
        for n in notes or []:
            fields = (n.get("fields") or {})
            val = None
            for fld in field_priority:
                cell = fields.get(fld)
                if cell:
                    v = (cell.get("value") or "").strip()
                    if v:
                        val = v
                        break
            if val:
                out.append(val)

        # case-insensitive de-dup
        seen, uniq = set(), []
        for w in out:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                uniq.append(w)
        return uniq

    def get_seen_words(self, deck: str) -> list[str]:
        t0 = time.perf_counter()
        note_ids = self.get_seen_note_ids(deck)
        notes = self.notes_info(note_ids) if note_ids else []
        words = self._extract_words_from_notes(notes)
        print(f"[ANKI] get_seen_words: deck='{deck}', notes={len(notes)}, words={len(words)}, took={time.perf_counter()-t0:.2f}s")
        return words