from __future__ import annotations

import base64
import os
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from typing import List, Tuple

import requests
from PIL import Image, UnidentifiedImageError

from ..models.card import CardData

# ────────────────────────────── configuration ────────────────────────────────
MAX_W            = 640  # px – resize cap
TEST_MODE        = os.getenv("L2_TEST_MODE") == "1"
ASSET_DIR        = Path(__file__).parent.parent / "test_assets"
AUDIO_MIME_EXT   = {
    "audio/webm": ".webm",
    "audio/ogg":  ".ogg",
    "audio/mpeg": ".mp3",
}

# ──────────────────────────────── helpers ────────────────────────────────────
def _download(url: str) -> bytes:
    if TEST_MODE and url.startswith("/static/test/thumbs/"):
        return (ASSET_DIR / "thumbs" / Path(url).name).read_bytes()
    return requests.get(url, timeout=20).content

def _compress(data: bytes) -> bytes:
    try:
        img = Image.open(BytesIO(data))
        img.thumbnail((MAX_W, MAX_W * 2), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return data

def _is_valid_image(data: bytes) -> bool:
    if not data:
        return False
    try:
        with Image.open(BytesIO(data)) as im:
            im.load()
            return im.width > 0 and im.height > 0
    except (UnidentifiedImageError, OSError, ValueError):
        return False

def _prep_image(data: bytes) -> bytes | None:
    if not data:
        return None
    comp = _compress(data)
    return comp if _is_valid_image(comp) else None

def _stage_image(
    actions: List[dict],
    img_tags: List[str],
    data: bytes,
    ext: str = ".jpg",
) -> None:
    fname = f"{uuid.uuid4().hex}{ext}"
    actions.append({
        "action": "storeMediaFile",
        "params": {"filename": fname, "data": base64.b64encode(data).decode()},
    })
    img_tags.append(f'<img src="{fname}">')

# ─────────────────────────────── main routine ────────────────────────────────
def save_note(
    *,
    deck: str,
    anki_model: str,
    anki,
    caches: dict,
    card_dict: dict,
    sel_urls: List[str],
    uploads: List[Tuple[str, bytes]],
    rec_b64: str = "",
) -> None:
    card = CardData.from_dict(card_dict)
    cached_audio_tag = caches["audio"].get(card.base, "")
    user_audio_tag   = ""
    actions:   List[dict] = []
    img_tags:  List[str]  = []

    print(f"[SAVE] Start  deck={deck} word={card.base}")

    # ─── 1) user recording (prepended) ───────────────────────────
    if rec_b64:
        try:
            header, b64data = rec_b64.split(",", 1)
            mime = header.split(";")[0].split(":")[1]
            ext  = AUDIO_MIME_EXT.get(mime, ".webm")
            aud_bytes = base64.b64decode(b64data)
            if aud_bytes:
                # store the recorded clip first
                fname = f"{uuid.uuid4().hex}{ext}"
                actions.append({
                    "action": "storeMediaFile",
                    "params": {"filename": fname, "data": b64data},
                })
                user_audio_tag = f"[sound:{fname}]"
            else:
                print("[SAVE]  recorded audio empty, ignored")
        except Exception as err:
            print(f"[SAVE]  bad audio_b64 payload: {err}")

    # ─── 2) remote URL images ─────────────────────────────────────
    for url in sel_urls:
        if len(img_tags) >= 3:
            break
        try:
            raw = _download(url)
        except Exception as err:
            print(f"[SAVE]  download failed for {url}: {err}")
            continue

        data = _prep_image(raw)
        if data is None:
            print(f"[SAVE]  invalid image from {url} (skipped).")
            continue

        ext = Path(urlparse(url).path).suffix or ".jpg"
        _stage_image(actions, img_tags, data, ext)

    # ─── 3) uploaded images ───────────────────────────────────────
    for name, raw in uploads:
        if len(img_tags) >= 3:
            break
        data = _prep_image(raw)
        if data is None:
            print(f"[SAVE]  invalid upload {name!r} (skipped).")
            continue

        ext = Path(name).suffix or ".jpg"
        _stage_image(actions, img_tags, data, ext)

    print(f"[SAVE]  valid_images={len(img_tags)}, audio_cached={bool(cached_audio_tag)}")

    # ─── 4) abort if no images ──────────────────────────────────
    if not img_tags:
        print(f"[SAVE]  no valid images for “{card.base}”; note NOT added.")
        return

    # ─── 5) addNote ─────────────────────────────────────────────
    full_audio_tag = user_audio_tag + cached_audio_tag
    fields = card.to_fields(audio=full_audio_tag, images=img_tags)

    actions.append({
        "action": "addNote",
        "params": {
            "note": {
                "deckName":  deck,
                "modelName": anki_model,
                "fields":    fields,
                "options":   {"allowDuplicate": False},
                "tags":      [],
            }
        },
    })

    try:
        print(f"[SAVE]  -> sending {len(actions)} actions to Anki")
        res = anki.multi(actions)
        if res[-1] is None:
            print(f"[SAVE]  duplicate note for “{card.base}” skipped")
        else:
            print(f"[SAVE]  result={res[-1]}")
    except Exception as err:
        print(f"[SAVE]  failed saving note “{card.base}”: {err}")