from __future__ import annotations
import os
import time, random, base64
from typing import Any, Dict, List, Literal

from flask import current_app, url_for

QuizType = Literal["vocab", "reading", "listening", "morph", "translate"]
DEFAULT_NUM_Q = 10

class QuizService:
    def __init__(self, *, anki, quiz_ai, tts_func=None):
        self.anki = anki
        self.ai = quiz_ai
        self.tts = tts_func

    def _log(self, msg: str) -> None:
        print(f"[QuizService] {msg}")

    def _pick_seen_words(self, deck: str, k: int) -> List[str]:
        words = self.anki.get_seen_words(deck)
        if not words:
            raise RuntimeError("Deck has no seen (non-new) cards.")
        random.shuffle(words)
        return words[:min(k, len(words))]

    def generate_vocab_quiz(self, *, deck: str, lang: str, level: str,
                         quiz_lang: str, n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        sample = self._pick_seen_words(deck, k=n) 
        t0 = time.perf_counter()
        items = self.ai.gen_vocab_quiz(lang=lang, level=level, known_words=sample, n=n, quiz_lang=quiz_lang)
        self._log(f"vocab: q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {
            "kind": "vocab",
            "lang": lang,
            "level": level,
            "items": items,
            "meta": {"source_words": sample, "quiz_lang": quiz_lang, "n": n},
        }

    def generate_reading_quiz(self, *, lang: str, level: str, quiz_lang: str,
                          n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        t0 = time.perf_counter()
        passage, items = self.ai.gen_reading_quiz(lang=lang, level=level, n=n, words=180, quiz_lang=quiz_lang)
        self._log(f"reading: chars={len(passage)}, q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {
            "kind": "reading",
            "lang": lang,
            "level": level,
            "items": items,
            "meta": {"passage": passage, "quiz_lang": quiz_lang, "n": n}
        }
    
    def grade_reading_quiz(self, *, lang: str, passage: str, items: list, user_answers: list[str]) -> list:
        return self.ai.eval_reading_batch(lang=lang, passage=passage, items=items, user_answers=user_answers)
    
    def generate_listening_quiz(self, *, lang: str, level: str, quiz_lang: str, n: int = DEFAULT_NUM_Q) -> dict:
        t0 = time.perf_counter()
        passage, items = self.ai.gen_reading_quiz(lang=lang, level=level, n=n, words=120, quiz_lang=quiz_lang)

        audio_url = None
        try:
            raw = self.tts(passage, lang) 
            static_root = os.path.join(current_app.root_path, "static")
            tmp_dir = os.path.join(static_root, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            out_path = os.path.join(tmp_dir, "listening.mp3")
            with open(out_path, "wb") as f:
                f.write(raw)
            audio_url = url_for("static", filename="tmp/listening.mp3")
        except Exception as e:
            self._log(f"TTS failed: {e}")

        self._log(f"listening: chars={len(passage)}, q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {
            "kind": "listening",
            "lang": lang,
            "level": level,
            "items": items,
            "meta": {"passage": passage, "audio": audio_url, "quiz_lang": quiz_lang, "n": n},
        }