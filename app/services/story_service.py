from __future__ import annotations
import re
import time
import random
from typing import Iterable, List, Set, Tuple

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿĀ-žА-Яа-яЁёİıŞşĞğČčŠšŽžÑñÜüÖöÄäß’'-]+", re.U)
BRACED_RE  = re.compile(r"\{([^{}\s][^{}]*?)\}") # captures {word} without spaces


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

        story = self.story_ai.generate_story_text(
            lang=lang, topic=topic, required_words=req_list, target_pct=target_pct
        )
        self._log(f"generate_story: model returned {len(story)} chars in {time.perf_counter() - t0:.2f}s")
        self._log(f"Returned text: {story}")

        # extract {wrapped} forms 
        wrapped_forms = [m.group(1) for m in BRACED_RE.finditer(story)]
        used_exact_set = set(wrapped_forms)
        self._log(f"generate_story: wrapped_known_forms={len(used_exact_set)}")

        return story, used_exact_set

    def highlight_story(self, story_text_with_braces: str, known_used_exact: Iterable[str]) -> Tuple[str, int]:
        t0 = time.perf_counter()

        covered_tokens = 0
        for m in BRACED_RE.finditer(story_text_with_braces):
            covered_tokens += len(TOKEN_RE.findall(m.group(1)))

        # remove braces and wrap for display
        def replacer(m: re.Match) -> str:
            inner = m.group(1)
            return f'<span class="known">{inner}</span>'

        html = BRACED_RE.sub(replacer, story_text_with_braces)

        # compute total tokens
        plain_text = BRACED_RE.sub(lambda m: m.group(1), story_text_with_braces)
        total_tokens = max(1, len(TOKEN_RE.findall(plain_text)))

        coverage = round(100 * covered_tokens / total_tokens)

        self._log(
            f"highlight_story: tokens_total={total_tokens}, tokens_covered={covered_tokens}, "
            f"coverage={coverage}%, took={time.perf_counter() - t0:.2f}s"
        )
        return html, coverage