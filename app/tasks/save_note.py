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
MAX_W            = 640                                # px – resize cap
TEST_MODE        = os.getenv("L2_TEST_MODE") == "1"
ASSET_DIR        = Path(__file__).parent.parent / "test_assets"

# ──────────────────────────────── helpers ────────────────────────────────────
def _download(url: str) -> bytes:
    """Return raw bytes from a URL (test fixtures honoured)."""
    if TEST_MODE and url.startswith("/static/test/thumbs/"):
        return (ASSET_DIR / "thumbs" / Path(url).name).read_bytes()
    return requests.get(url, timeout=20).content


def _compress(data: bytes) -> bytes:
    """Resize + recompress JPEG ≤ MAX_W.  Fallback to original bytes."""
    try:
        img = Image.open(BytesIO(data))
        img.thumbnail((MAX_W, MAX_W * 2), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return data


def _is_valid_image(data: bytes) -> bool:
    """Basic sanity check – readable, non-zero size."""
    if not data:
        return False
    try:
        with Image.open(BytesIO(data)) as im:
            im.load()
            w, h = im.size
            return w > 0 and h > 0
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _prep_image(data: bytes) -> bytes | None:
    """Compress then validate.  Return usable bytes or None."""
    if not data:
        return None
    comp = _compress(data)
    return comp if _is_valid_image(comp) else None


def _stage_image(
    actions: List[dict], img_tags: List[str], data: bytes, ext: str = ".jpg"
) -> None:
    """Push image bytes into Anki `actions` and HTML `img_tags`."""
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
) -> None:
    """
    Download / attach up to three valid images (URLs first, then uploads)
    and create an Anki note.  If *no* valid images remain, the note is skipped.
    """
    card      = CardData.from_dict(card_dict)
    audio_tag = caches["audio"].get(card.base, "")

    print(f"[SAVE] Start  deck={deck} word={card.base}")

    img_tags: List[str] = []
    actions:  List[dict] = []

    # ─── a) remote URLs ────────────────────────────────────────────
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

        _stage_image(actions, img_tags, data, Path(urlparse(url).path).suffix or ".jpg")

    # ─── b) uploads ────────────────────────────────────────────────
    for name, raw in uploads:
        if len(img_tags) >= 3:
            break

        data = _prep_image(raw)
        if data is None:
            print(f"[SAVE]  invalid upload {name!r} (skipped).")
            continue

        _stage_image(actions, img_tags, data, Path(name).suffix or ".jpg")

    print(f"[SAVE]  valid_images={len(img_tags)} audio_tag={bool(audio_tag)}")

    # ─── c) guard – need at least one image ────────────────────────
    if not img_tags:
        print(f"[SAVE]  no valid images for “{card.base}”; note NOT added.")
        return

    # ─── d) add note ───────────────────────────────────────────────
    fields = card.to_fields(audio=audio_tag, images=img_tags)
    actions.append({
        "action": "addNote",
        "params": {
            "note": {
                "deckName":   deck,
                "modelName":  anki_model,
                "fields":     fields,
                "options":    {"allowDuplicate": False},
                "tags":       [],
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