from __future__ import annotations

import base64
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

from ..models.card import CardData

import os, pathlib

TEST_MODE = os.getenv("L2_TEST_MODE") == "1"
ASSET_DIR = pathlib.Path(__file__).parent.parent / "test_assets"

MAX_W = 640  # px


# ───────────────── helpers ────────────────────────────────────────
def _download(url: str) -> bytes:
    if TEST_MODE and url.startswith("/static/test/thumbs/"):
        fname = pathlib.Path(url).name
        return (ASSET_DIR / "thumbs" / fname).read_bytes()
    return requests.get(url, timeout=20).content


def _compress(raw: bytes) -> bytes:
    """Resize + recompress large images to ≤640 px wide."""
    try:
        img = Image.open(BytesIO(raw))
        img.thumbnail((MAX_W, MAX_W * 2), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return raw


# ───────────────── main routine ────────────────────────────────────
def save_note(
    *,
    deck: str,
    anki_model: str,
    anki,
    caches: dict,
    card_dict: dict,
    sel_urls: list[str],
    uploads: list[tuple[str, bytes]],
) -> None:
    """Download/attach images, add note.  Synchronous, one card."""
    card = CardData.from_dict(card_dict)
    audio_tag = caches["audio"].get(card.base, "")

    print(f"[SAVE] Start  deck={deck} word={card.base}")

    img_tags: list[str] = []
    actions: list[dict] = []

    # a) remote URLs -------------------------------------------------
    for u in sel_urls[:3]:
        ext   = Path(urlparse(u).path).suffix or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        try:
            raw = _compress(_download(u))
        except Exception as err:
            print(f"Download failed for {u}: {err}")
            continue
        b64 = base64.b64encode(raw).decode()
        actions.append({"action": "storeMediaFile",
                        "params": {"filename": fname, "data": b64}})
        img_tags.append(f'<img src="{fname}">')
    print(f"[SAVE]  images={len(img_tags)} audio_tag={bool(audio_tag)}")

    # b) uploads -----------------------------------------------------
    for name, raw in uploads[: 3 - len(img_tags)]:
        ext   = Path(name).suffix or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        raw   = _compress(raw)
        b64   = base64.b64encode(raw).decode()
        actions.append({"action": "storeMediaFile",
                        "params": {"filename": fname, "data": b64}})
        img_tags.append(f'<img src="{fname}">')

    # c) add note ----------------------------------------------------
    fields = card.to_fields(audio=audio_tag, images=img_tags)
    actions.append({
        "action": "addNote",
        "params": {
            "note": {
                "deckName": deck,
                "modelName": anki_model,
                "fields": fields,
                "options": {"allowDuplicate": False},
                "tags": [],
            }
        },
    })

    try:
        print(f"[SAVE]  -> sending {len(actions)} actions to Anki")
        res = anki.multi(actions)
        if res[-1] is None:
            print(f"Note for “{card.base}” NOT added (duplicate?)")
        print(f"[SAVE]  result={res[-1]}")
    except Exception as err:
        print(f"Failed saving note “{card.base}”: {err}")