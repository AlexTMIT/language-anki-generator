import os, time
from typing import Iterable
from openai import OpenAI
from app.extensions import socketio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4.1"
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
        f"Write a short story in {lang} about '{topic}'. Be creative, but stay coherent and on-topic.\n"
        f"Make natural, heavy use of the following {len(req)} known words, sprinkled across the story:\n"
        f"{', '.join(req)}\n"
        "Whenever you use a word from the list (any inflected/surface form of that word), "
        "wrap the exact surface form with curly braces, e.g., {løber}.\n"
        "Do NOT put braces around punctuation or spaces. Braces must enclose just the word.\n"
        "Use braces consistently for every occurrence of a listed word.\n"
        "It is imperative that the story is grammatically correct.\n"
        "Make the story around 200 words long with paragraphs.\n"
        "Try to use all words given to you.\n"
        "Return ONLY the story text.\n"
    )

    resp = client.chat.completions.create(
        model=MODEL, temperature=TEMP,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        max_tokens=900
    )

    _push(f"✔ Story ready ({time.time()-t0:.2f}s)")
    return resp.choices[0].message.content.strip()