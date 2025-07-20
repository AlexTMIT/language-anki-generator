"""Forvo-based audio retrieval with basic mastering."""
from __future__ import annotations
import tempfile
from pathlib import Path
from urllib.parse import quote_plus

import requests
from pydub import AudioSegment, effects

from ..config import settings

FORVO_URL = (
    "https://apifree.forvo.com/key/{key}/format/json/"
    "action/word-pronunciations/word/{word}/language/{lang}"
)

# Processing constants
GAP_MS = 300
HPF_CUTOFF_HZ = 100
LPF_CUTOFF_HZ = 7500
PEAK_TARGET_DBFS = -3.0


def _fetch_clips(lang: str, word: str, top: int = 3) -> list[str]:
    url = FORVO_URL.format(
        key=settings.FORVO_API_KEY.get_secret_value(),
        word=quote_plus(word),
        lang=lang,
    )
    data = requests.get(url, timeout=15).json()
    items = sorted(data.get("items", []), key=lambda x: x.get("rate", 0), reverse=True)
    print(f"Fetched {len(items)} clips for '{word}' in {lang}")
    return [itm["pathmp3"] for itm in items[:top]]


def _process(seg: AudioSegment) -> AudioSegment:
    seg = seg.high_pass_filter(HPF_CUTOFF_HZ)
    seg = seg.low_pass_filter(LPF_CUTOFF_HZ)
    return effects.normalize(seg, headroom=-PEAK_TARGET_DBFS)


def get_audio_blob(lang: str, word: str):
    clips = _fetch_clips(lang, word)
    if not clips:
        return "", None

    with tempfile.TemporaryDirectory() as tmp:
        segs = []
        for idx, url in enumerate(clips, 1):
            path = Path(tmp) / f"raw_{idx}.mp3"
            data = requests.get(url, timeout=20).content
            path.write_bytes(data)
            segs.append(_process(AudioSegment.from_file(path)))

        gap = AudioSegment.silent(GAP_MS)
        combined = segs[0]
        for seg in segs[1:]:
            combined += gap + seg

        out_name = f"{word.replace(' ', '_')}_{lang}.mp3"
        out_bytes = combined.export(format="mp3", bitrate="192k").read()
        return out_name, out_bytes