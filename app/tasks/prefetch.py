from ..services.audio_service import get_audio_blob
from ..services.image_service import google_thumbs
from ..services.openai_svc import tts
from app.extensions import socketio
import time as _t

THUMB_CACHE = "thumb"
RAW_CACHE = "thumb_raw"
AUDIO_BLOB_CACHE = "audio_blob"
AUDIO_CACHE = "audio"
def prefetch(anki, caches: dict, card_dict: dict, lang: str) -> None:
    word     = card_dict["base"]
    t_start  = _t.perf_counter()

    for key in (THUMB_CACHE, RAW_CACHE, AUDIO_BLOB_CACHE, AUDIO_CACHE):
        caches.setdefault(key, {})

    # ---------- thumbnails (URLs only) ----------
    thumbs = google_thumbs(card_dict["keyword"])
    caches[THUMB_CACHE][word] = thumbs
    socketio.emit("progress",
                  f"Cached {len(thumbs)} thumbnail URL(s) for “{word}”")

    # ---------- audio ----------
    fname, blob = get_audio_blob(lang, word)
    if not blob:
        blob  = tts(word, lang)
        fname = f"{word}.mp3"
        socketio.emit("progress", "Generated TTS audio")
    else:
        socketio.emit("progress", "Fetched audio from Forvo")

    caches[AUDIO_BLOB_CACHE][word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches[AUDIO_CACHE][word] = f"[sound:{media}]"

    print(f"[timing] prefetch({word}) total {_t.perf_counter()-t_start:5.3f}s")

def load_live_mode_content(anki, caches, card_dict, lang, word):
    caches[THUMB_CACHE][word] = google_thumbs(card_dict["keyword"])
    fname, blob = get_audio_blob(lang, word)
    caches.setdefault(AUDIO_BLOB_CACHE, {})[word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches[AUDIO_CACHE][word] = f"[sound:{media}]"
