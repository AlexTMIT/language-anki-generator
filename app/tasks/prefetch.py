"""
Prefetch thumbs + audio for ONE card.
If L2_TEST_MODE=1 is set, serve local stub assets.
"""
import os, random, pathlib
from ..services.audio_service import get_audio_blob
from ..services.image_service import google_thumbs
from app.extensions import socketio

TEST_MODE = os.getenv("L2_TEST_MODE") == "1"
OFFLINE    = os.getenv("L2_OFFLINE") == "1"
ASSET_DIR = pathlib.Path(__file__).parent.parent / "test_assets"


def prefetch(anki, caches: dict, card_dict: dict, lang: str) -> None:
    word = card_dict["base"]

    caches.setdefault("thumb", {})
    thumbs = google_thumbs(card_dict["keyword"])
    caches["thumb"][word] = thumbs

    print(f"[PREFETCH] Thumbs={len(thumbs)} for “{word}”")
    socketio.emit("progress", f"Prefetched {len(thumbs)} thumbnail(s) for “{word}”")

    # audio
    fname, blob = get_audio_blob(lang, word)
    caches.setdefault("audio_blob", {})[word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches.setdefault("audio", {})[word] = f"[sound:{media}]"
        socketio.emit("progress", "Audio clip fetched")

def load_live_mode_content(anki, caches, card_dict, lang, word):
    caches["thumb"][word] = google_thumbs(card_dict["keyword"])
    fname, blob = get_audio_blob(lang, word)
    caches.setdefault("audio_blob", {})[word] = blob or b""
    if blob:
        media = anki.store_media(fname, blob)
        caches["audio"][word] = f"[sound:{media}]"

def load_test_mode_content(anki, caches, word):
    thumbs_root = ASSET_DIR / "thumbs"
    thumbs = sorted(thumbs_root.glob("*.jpg"))
    caches["thumb"][word] = [
            f"/static/test/thumbs/{p.name}" for p in random.sample(thumbs, k=6)
        ]

    audio_file = ASSET_DIR / "audio" / "dummy.mp3"
    dummy = audio_file.read_bytes()
    caches.setdefault("audio_blob", {})[word] = dummy
    media = anki.store_media("dummy.mp3", dummy)
    caches["audio"][word] = f"[sound:{media}]"
    return