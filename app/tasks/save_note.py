from __future__ import annotations
import base64
from pathlib import Path
from urllib.parse import urlparse
import uuid
import requests

from io import BytesIO
from PIL import Image

from ..models.card import CardData
from ..extensions import progress, progress_lock

MAX_W = 640
MAX_H = 400

def _download(url: str) -> bytes:
    return requests.get(url, timeout=20).content


def save_note_async(
    sid: str,
    deck: str,
    anki_model: str,
    anki,
    caches: dict,
    card_dict: dict,
    sel_urls: list[str],
    uploads: list[tuple[str, bytes]],
):
    card = CardData.from_dict(card_dict)
    audio_tag = caches["audio"].get(card.base, "")

    img_tags, media_actions = [], []   # collect HTML + rpc actions

    # remote URLs ----------------------------------------------------
    for u in sel_urls[:3]:
        ext = Path(urlparse(u).path).suffix or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        try:
            raw   = _compress(_download(u))
            data   = _compress(raw)
            b64    = base64.b64encode(data).decode()
            media_actions.append(
                {"action": "storeMediaFile",
                "params": {"filename": fname, "data": b64}}
            )
            img_tags.append(f'<img src="{fname}">')   # fname used later
        except Exception as err:
            print(f"DL/store fail for {u}: {err}")

    # local uploads --------------------------------------------------
    for name, raw in uploads[: 3 - len(img_tags)]:
        ext = Path(name).suffix or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        media = anki.store_media(fname, raw)
        img_tags.append(f'<img src="{media}">')

    fields = card.to_fields(audio=audio_tag, images=img_tags)
    media_actions.append(
        {"action": "addNote",
         "params": {
             "note": {
                 "deckName": deck,
                 "modelName": anki_model,
                 "fields": fields,
                 "options": {"allowDuplicate": False},
                 "tags": [],
             }
         }}
    )

    results = anki.multi(media_actions)
    ok = results[-1] is not None

    with progress_lock:
        if sid in progress:
            key = "added" if ok else "dups"
            progress[sid][key] += 1


def _compress(raw: bytes) -> bytes:
    try:
        img = Image.open(BytesIO(raw))
        img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return raw 