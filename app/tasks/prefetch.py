import pathlib
from ..services.audio_service import get_audio_blob
from ..services.image_service import google_thumbs
from ..services.openai_svc import tts
from app.extensions import socketio

def prefetch(anki, caches: dict, card_dict: dict, lang: str) -> None:
    word   = card_dict["base"]
    caches.setdefault("thumb", {})
    caches.setdefault("audio_blob", {})
    caches.setdefault("audio", {})

    # ---------- thumbnails ----------
    thumbs = google_thumbs(card_dict["keyword"])
    caches["thumb"][word] = thumbs
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
    caches["audio_blob"][word] = blob or b""
    if blob:
        media_name              = anki.store_media(fname, blob)
        caches["audio"][word]   = f"[sound:{media_name}]"

def load_live_mode_content(anki, caches, card_dict, lang, word):
    caches["thumb"][word] = google_thumbs(card_dict["keyword"])
    fname, blob = get_audio_blob(lang, word)
    caches.setdefault("audio_blob", {})[word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches["audio"][word] = f"[sound:{media}]"
