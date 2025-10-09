import os, time
from typing import Iterable
from openai import OpenAI
from app.extensions import socketio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4.1-mini"
TEMP  = 0.6

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

def generate_story_text(*, lang: str, topic: str,
                        required_words: Iterable[str]) -> str:
    req = [w for w in dict.fromkeys([w.strip() for w in required_words if w.strip()])]
    _push("Generating story…")
    t0 = time.time()

    system = (
        "You are a native, idiomatic storyteller and language tutor. "
        "Write in grammatically correct, natural-sounding {lang} with authentic phrasing and register."
    ).replace("{lang}", lang)
    user = (
        f"Write a short, natural-sounding story in {lang} about: {topic}.\n"
        f"Use the following {len(req)} known words throughout the story (inflect or conjugate naturally):\n"
        f"{', '.join(req)}\n"
        "Wrap every occurrence of these words with { }, e.g. {løber}. "
        "Only wrap the word itself — no spaces or punctuation.\n"
        "Use all words at least once where possible. Grammar must be correct.\n"
        "Length: ~200 words. Use multiple paragraphs separated by blank lines.\n"
        "Return ONLY the story text."
    )

    resp = client.chat.completions.create(
        model=MODEL, temperature=TEMP,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        max_tokens=900
    )

    _push(f"✔ Story ready ({time.time()-t0:.2f}s)")
    return resp.choices[0].message.content.strip()