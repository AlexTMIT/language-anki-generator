from ..services.audio_service import get_audio_blob
from ..services.image_service import google_thumbs


def prefetch(anki, caches: dict, card_dict: dict, lang: str) -> None:
    """Background job: fetch audio & thumbnails, store in shared caches."""
    word = card_dict["base"]

    # thumbnails
    caches["thumb"][word] = google_thumbs(card_dict["keyword"])

    # audio
    fname, blob = get_audio_blob(lang, word)
    caches["audio"][word] = ""
    if blob:
        media = anki.store_media(fname, blob)
        caches["audio"][word] = f"[sound:{media}]"