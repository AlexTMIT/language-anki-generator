from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True, slots=True)
class CardData:
    base: str
    grammar: str
    translation: str
    example: str
    example_translation: str
    keyword: str

    @classmethod
    def from_dict(cls, raw: dict) -> "CardData":
        return cls(
            base=raw["base"].strip(),
            grammar=raw["grammar"].strip(),
            translation=raw["translation"].strip(),
            example=raw["example"].strip(),
            example_translation=raw["example-translation"].strip(),
            keyword=raw["keyword"].strip(),
        )

    def to_fields(self, lang: str, audio: str = "", images: Iterable[str] = ()) -> dict:
        imgs = list(images)[:3]  # hard‑cap at 3
        return {
            "Word": self.base if lang != "da" else self.add_danish_verb_article(self.base, self.grammar),
            "Grammar": self.grammar,
            "Meaning": self.translation,
            "Sentence": self.example,
            "Translation": self.example_translation,
            "Audio": audio,
            "Image 1": imgs[0] if len(imgs) > 0 else "",
            "Image 2": imgs[1] if len(imgs) > 1 else "",
            "Image 3": imgs[2] if len(imgs) > 2 else "",
        }

    def add_danish_verb_article(self, word: str, grammar: str) -> str:
        if word.startswith(("at ", "en ", "et ")):
            return word
        elif grammar.lower() == "verb":
            return "at " + word
        else:
            return word
