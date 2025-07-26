from ..services.audio_service import get_audio_blob
from ..services.image_service import google_thumbs
from ..services.openai_svc import tts
from app.extensions import socketio
import requests

THUMB_CACHE = "thumb"
RAW_CACHE = "thumb_raw"
AUDIO_BLOB_CACHE = "audio_blob"
AUDIO_CACHE = "audio"

def _download_raw(url: str) -> bytes:
    return requests.get(url, timeout=20).content

def prefetch(anki, caches: dict, card_dict: dict, lang: str) -> None:
    word   = card_dict["base"]

    caches.setdefault(THUMB_CACHE, {})
    caches.setdefault(RAW_CACHE, {})
    caches.setdefault(AUDIO_BLOB_CACHE, {})
    caches.setdefault(AUDIO_CACHE, {})

    # ---------- thumbnails ----------
    thumbs = google_thumbs(card_dict["keyword"])
    caches[THUMB_CACHE][word] = thumbs
    
    for url in thumbs:
        if url not in caches[RAW_CACHE]:
            try:
                caches[RAW_CACHE][url] = _download_raw(url)
            except Exception:
                pass

    socketio.emit("progress",
                  f"Prefetched {len(thumbs)} thumbnail(s) for “{word}”")

    # ---------- audio (Forvo → TTS fallback) ----------
    fname, blob = get_audio_blob(lang, word)
    if not blob:
        blob  = tts(word, lang)
        fname = f"{word}.mp3"
        socketio.emit("progress", "Generated TTS audio")
    else:
        socketio.emit("progress", "Fetched audio from Forvo")

    # ---------- cache + Anki ----------
    caches[AUDIO_BLOB_CACHE][word] = blob or b""
    if blob:
        media_name              = anki.store_media(fname, blob)
        caches[AUDIO_CACHE][word]   = f"[sound:{media_name}]"

def load_live_mode_content(anki, caches, card_dict, lang, word):
    caches[THUMB_CACHE][word] = google_thumbs(card_dict["keyword"])
    fname, blob = get_audio_blob(lang, word)
    caches.setdefault(AUDIO_BLOB_CACHE, {})[word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches[AUDIO_CACHE][word] = f"[sound:{media}]"
