from __future__ import annotations
import random, re
from typing import Iterable, List, Set, Tuple

TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿĀ-žА-Яа-яЁёİıŞşĞğČčŠšŽžÑñÜüÖöÄäß’'-]+", re.U)

class StoryService:
    def __init__(self, *, anki, story_ai):
        self.anki = anki
        self.story_ai = story_ai

    def pick_known_words(self, *, deck: str, target_pct: int, lang: str) -> List[str]:
        words: List[str] = []

        if hasattr(self.anki, "get_words"):
            words = self.anki.get_words(deck)
        elif hasattr(self.anki, "deck_words"):
            words = self.anki.deck_words(deck)
        elif hasattr(self.anki, "find_notes"):        
            notes = self.anki.find_notes(deck)
            for n in notes:
                for fld in ("Word", "Front", "Back"):
                    v = (n.get("fields", {}).get(fld, {}).get("value") if isinstance(n, dict) else None)
                    if v: words.append(v)

        # normalize, dedupe
        seen, pool = set(), []
        for w in words:
            w = (w or "").strip()
            lw = w.lower()
            if w and lw not in seen:
                seen.add(lw)
                pool.append(w)

        # sample a reasonable subset
        random.shuffle(pool)
        sample_size = min(80, max(20, len(pool)//5))  # tweak if you want
        return pool[:sample_size]

    def generate_story(self, *, lang: str, topic: str,
                       required_words: Iterable[str], target_pct: int) -> Tuple[str, Set[str]]:
        text = self.story_ai.generate_story_text(
            lang=lang, topic=topic, required_words=required_words, target_pct=target_pct
        )
        used = self._words_in_text(text)
        req_set = {w for w in required_words}
        used_req = {w for w in req_set if w.lower() in used}
        return text, used_req

    def highlight_story(self, story_text: str, known_used: Iterable[str]) -> Tuple[str, int]:
        known = {w.lower() for w in known_used}
        toks = TOKEN_RE.findall(story_text)
        total = max(1, len(toks))
        covered = sum(1 for t in toks if t.lower() in known)
        pct = round(100 * covered / total)

        def repl(m):
            tok = m.group(0)
            return f'<span class="known">{tok}</span>' if tok.lower() in known else tok

        html = TOKEN_RE.sub(repl, story_text)
        html = "<p>" + "</p><p>".join(s.strip() for s in html.split("\n") if s.strip()) + "</p>"
        return html, pct

    def _words_in_text(self, text: str) -> Set[str]:
        return {t.lower() for t in TOKEN_RE.findall(text)}