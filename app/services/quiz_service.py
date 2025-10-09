from __future__ import annotations
import time, random, base64
from typing import Any, Dict, List, Literal

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
                            n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        sample = self._pick_seen_words(deck, k=n*4) 
        t0 = time.perf_counter()
        items = self.ai.gen_vocab_quiz(lang=lang, level=level, known_words=sample, n=n)
        self._log(f"vocab: q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {"kind": "vocab", "lang": lang, "level": level, "items": items, "meta": {"source_words": sample}}

    def generate_reading_quiz(self, *, lang: str, level: str,
                              n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        t0 = time.perf_counter()
        passage, items = self.ai.gen_reading_quiz(lang=lang, level=level, n=n, words=100)
        self._log(f"reading: chars={len(passage)}, q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {"kind": "reading", "lang": lang, "level": level, "items": items, "meta": {"passage": passage}}

    def generate_listening_quiz(self, *, lang: str, level: str,
                                n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        # same as reading + optional TTS
        bundle = self.generate_reading_quiz(lang=lang, level=level, n=n)
        audio_b64 = None
        if self.tts:
            try:
                raw = self.tts(bundle["meta"]["passage"], lang)
                audio_b64 = "data:audio/mp3;base64," + base64.b64encode(raw).decode()
            except Exception as e:
                self._log(f"TTS failed: {e}")
        bundle["kind"] = "listening"
        bundle["meta"]["audio"] = audio_b64
        return bundle

    def generate_morph_quiz(self, *, deck: str, lang: str, level: str,
                            n: int = DEFAULT_NUM_Q) -> Dict[str, Any]:
        sample = self._pick_seen_words(deck, k=n*3)
        t0 = time.perf_counter()
        items = self.ai.gen_morph_quiz(lang=lang, level=level, known_words=sample, n=n)
        self._log(f"morph: q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {"kind": "morph", "lang": lang, "level": level, "items": items, "meta": {"source_words": sample}}

    def generate_translate_quiz(self, *, lang: str, level: str,
                                n: int = DEFAULT_NUM_Q, direction: str = "L1->L2") -> Dict[str, Any]:
        t0 = time.perf_counter()
        items = self.ai.gen_translate_quiz(lang=lang, level=level, n=n, direction=direction)
        self._log(f"translate: q={len(items)} in {time.perf_counter()-t0:.2f}s")
        return {"kind": "translate", "lang": lang, "level": level, "items": items, "meta": {"direction": direction}}