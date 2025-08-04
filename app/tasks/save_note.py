from __future__ import annotations

import base64
import uuid
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Tuple

import requests

from ..models.card import CardData

import eventlet, time as _t

FETCH_POOL = eventlet.GreenPool(size=3)
MAX_W = 640 
AUDIO_MIME_EXT = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3"}

def _download_and_cache(url: str, caches: dict) -> tuple[str, bytes | None, float]:
    """Fetch a URL, validate it's an image, and cache the raw bytes."""
    t0 = _t.perf_counter()
    try:
        resp = requests.get(url, timeout=20)
        elapsed = _t.perf_counter() - t0

        ct = resp.headers.get("Content-Type", "")
        if not ct.startswith("image/"):
            return url, None, elapsed

        raw = resp.content
        if raw.startswith(b"\xFF\xD8") or raw.startswith(b"\x89PNG") or raw.startswith(b"GIF"):
            caches.setdefault("thumb_raw", {})[url] = raw
            return url, raw, elapsed
        else:
            return url, None, elapsed

    except Exception:
        elapsed = _t.perf_counter() - t0
        return url, None, elapsed

def _stage_image(actions: List[dict], img_tags: List[str], raw: bytes, ext: str = ".jpg") -> None:
    """Add storeMedia and img tag actions for a valid image."""
    fname = f"{uuid.uuid4().hex}{ext}"
    b64 = base64.b64encode(raw).decode()
    actions.append({
        "action": "storeMediaFile",
        "params": {"filename": fname, "data": b64},
    })
    img_tags.append(f'<img src="{fname}">')

def _process_images(
    sel_urls: List[str],
    uploads : List[Tuple[str, bytes]],
    actions : List[dict],
    caches  : dict,
) -> List[str]:
    img_tags: List[str] = []
    t_total = _t.perf_counter()

    # ---------- parallel fetch any missing originals ----------
    need_dl = [u for u in sel_urls if u not in caches.get("thumb_raw", {})]
    for url, raw, dt in FETCH_POOL.imap(lambda u: _download_and_cache(u, caches), need_dl):
        sz = len(raw or b"") / 1024
        print(f"[timing]   GET {url[:55]}… {sz:6.1f} KiB in {dt:4.2f}s")

    # ---------- now build note fields ----------
    def try_url(url: str) -> None:
        raw = caches.get("thumb_raw", {}).get(url, b"")
        if raw and len(img_tags) < 3:
            ext = Path(urlparse(url).path).suffix or ".jpg"
            _stage_image(actions, img_tags, raw, ext)

    for url in sel_urls:
        if len(img_tags) >= 3:
            break
        try:
            try_url(url)
        except Exception:
            continue

    for name, data in uploads:
        if len(img_tags) >= 3:
            break
        if data[:2] == b"\xFF\xD8":                   # JPEG magic validation
            ext = Path(name).suffix or ".jpg"
            _stage_image(actions, img_tags, data, ext)

    print(f"[timing] _process_images total {_t.perf_counter()-t_total:4.2f}s")
    return img_tags


def _stage_user_audio(rec_b64: str, actions: List[dict]) -> str:
    """
    Decode user audio and stage storeMedia action if present.
    Returns an [sound:] tag or empty string.
    """
    if not rec_b64.startswith("data:audio"):
        return ""
    try:
        header, b64data = rec_b64.split(",", 1)
        raw = base64.b64decode(b64data)
        if raw:
            mime = header.split(";")[0].split(":")[1]
            ext = AUDIO_MIME_EXT.get(mime, ".webm")
            fname = f"{uuid.uuid4().hex}{ext}"
            actions.append({
                "action": "storeMediaFile",
                "params": {"filename": fname, "data": b64data},
            })
            return f"[sound:{fname}]"
    except Exception:
        pass
    return ""


def save_note(
    *, deck: str, anki_model: str, anki, caches: dict,
    card_dict: dict, sel_urls: List[str],
    uploads: List[Tuple[str, bytes]], rec_b64: str = "",
    lang: str
) -> None:
    card = CardData.from_dict(card_dict)
    actions: List[dict] = []

    print(f"[SAVE] Start deck={deck} word={card.base}")

    full_audio = get_full_audio(caches, rec_b64, card, actions)

    img_tags = _process_images(sel_urls, uploads, actions, caches)
    if not img_tags:
        print(f"[SAVE] no valid images for '{card.base}', skipping.")
        return

    fields = card.to_fields(audio=full_audio, images=img_tags, lang=lang)
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
        }
    })

    try:
        res = anki.multi(actions)
        print(f"[SAVE] result={res[-1]}")
    except Exception as err:
        print(f"[SAVE] failed saving note: {err}")

def get_full_audio(caches, rec_b64, card, actions):
    user_tag = _stage_user_audio(rec_b64, actions)
    cached_tag = caches.get("audio", {}).get(card.base, "")
    full_audio = cached_tag + user_tag
    return full_audio