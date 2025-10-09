from __future__ import annotations
import re
import time
import random
from typing import Iterable, List, Set, Tuple

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿĀ-žА-Яа-яЁёİıŞşĞğČčŠšŽžÑñÜüÖöÄäß’'-]+", re.U)


class StoryService:
    def __init__(self, *, anki, story_ai, debug: bool = False):
        self.anki = anki
        self.story_ai = story_ai
        self.debug = debug

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[StoryService] {msg}")

    def _words_in_text(self, text: str) -> Set[str]:
        return {t.lower() for t in TOKEN_RE.findall(text)}

    def pick_known_words(self, *, deck: str, target_pct: int, lang: str) -> List[str]:
        t0 = time.perf_counter()
        words: List[str] = []
        words = self.anki.get_words(deck)

        # normalize, dedupe
        seen, pool = set(), []
        for w in words:
            w = (w or "").strip()
            lw = w.lower()
            if w and lw not in seen:
                seen.add(lw)
                pool.append(w)

        random.shuffle(pool)
        sample_size = min(80, max(20, len(pool) // 5))  # 20 to 80 words
        sample = pool[:sample_size]

        took = time.perf_counter() - t0
        self._log(
            f"pick_known_words: raw={len(words)}, dedup={len(pool)}, "
            f"sample_size={sample_size}, took={took:.2f}s (deck='{deck}', lang='{lang}')"
        )

        if not sample:
            raise RuntimeError(
                "No words found in the selected deck. "
                "Verify deck name and field mapping (Word/Expression/Front/Back/Term)."
            )

        return sample

    def generate_story(
        self,
        *,
        lang: str,
        topic: str,
        required_words: Iterable[str],
        target_pct: int,
    ) -> Tuple[str, Set[str]]:
        t0 = time.perf_counter()
        req_list = list(required_words)
        self._log(
            f"generate_story: calling model with req_words={len(req_list)}, "
            f"target_pct={target_pct}, lang='{lang}', topic='{topic}'"
        )

        text = self.story_ai.generate_story_text(
            lang=lang, topic=topic, required_words=req_list, target_pct=target_pct
        )
        self._log(f"generate_story: model returned {len(text)} chars in {time.perf_counter() - t0:.2f}s")

        used_tokens = self._words_in_text(text)
        req_set = set(req_list)
        used_req = {w for w in req_set if w.lower() in used_tokens}
        self._log(f"generate_story: used_required={len(used_req)} / {len(req_set)} matched in story")

        return text, used_req

    def highlight_story(self, story_text: str, known_used: Iterable[str]) -> Tuple[str, int]:
        t0 = time.perf_counter()
        known = {w.lower() for w in known_used}

        tokens = TOKEN_RE.findall(story_text)
        total = max(1, len(tokens))
        covered = sum(1 for t in tokens if t.lower() in known)
        pct = round(100 * covered / total)

        def repl(m: re.Match) -> str:
            tok = m.group(0)
            return f'<span class="known">{tok}</span>' if tok.lower() in known else tok

        html = TOKEN_RE.sub(repl, story_text)
        # paragraphize
        html = "<p>" + "</p><p>".join(s.strip() for s in html.split("\n") if s.strip()) + "</p>"

        self._log(
            f"highlight_story: tokens={total}, covered={covered}, coverage={pct}%, "
            f"took={time.perf_counter() - t0:.2f}s"
        )
        return html, pct