from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote_plus

import requests
from pydub import AudioSegment, effects

# ---------- constants -----------------------------------------------------
FORVO_URL = (
    "https://apifree.forvo.com/key/{key}/format/json/"
    "action/word-pronunciations/word/{word}/language/{lang}"
)
GAP_MS = 300
HPF_CUTOFF_HZ = 100
LPF_CUTOFF_HZ = 7500
PEAK_TARGET_DBFS = -3.0

# ---------- utils ---------------------------------------------------------
def _load_api_key() -> str:
    if (k := os.environ.get("FORVO_API_KEY")):
        return k
    raise RuntimeError("FORVO_API_KEY not set in environment.")

def _fetch_top3(key: str, lang: str, word: str) -> list[dict]:
    url = FORVO_URL.format(key=key, word=quote_plus(word), lang=lang)
    data = requests.get(url, timeout=15).json()
    items = sorted(data.get("items", []), key=lambda x: x.get("rate", 0), reverse=True)
    return items[:3]

def _clarity(seg: AudioSegment) -> AudioSegment:
    seg = seg.high_pass_filter(HPF_CUTOFF_HZ)
    seg = seg.low_pass_filter(LPF_CUTOFF_HZ)
    seg = effects.normalize(seg, headroom=-PEAK_TARGET_DBFS)
    return seg

def get_audio_blob(lang: str, word: str) -> tuple[str, bytes] | tuple[str, None]:
    """
    Return (filename, mp3-bytes)  OR  ("", None) if nothing found.
    filename is suitable for storeMediaFile (no spaces).
    """
    key = _load_api_key()
    clips = _fetch_top3(key, lang, word)
    if not clips:
        return "", None

    with tempfile.TemporaryDirectory() as tmpdir:
        segs = []
        for idx, itm in enumerate(clips, 1):
            path = Path(tmpdir) / f"raw_{idx}.mp3"
            with requests.get(itm["pathmp3"], timeout=20) as r:
                r.raise_for_status()
                path.write_bytes(r.content)
            segs.append(_clarity(AudioSegment.from_file(path)))

        # concatenate with gaps
        gap = AudioSegment.silent(duration=GAP_MS)
        combined = AudioSegment.empty()
        for i, s in enumerate(segs):
            combined += s
            if i < len(segs) - 1:
                combined += gap

        out_name = f"{word.replace(' ', '_')}_{lang}.mp3"
        out_bytes = combined.export(format="mp3", bitrate="192k").read()
        return out_name, out_bytes