import os, time
from typing import Iterable
from openai import OpenAI
from app.extensions import socketio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4.1-mini"
TEMP  = 0.8

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

def generate_story_text(*, lang: str, topic: str,
                        required_words: Iterable[str],
                        target_pct: int) -> str:
    req = [w for w in dict.fromkeys([w.strip() for w in required_words if w.strip()])]
    _push("Generating story…")
    t0 = time.time()

    system = "You are a helpful storyteller."
    user = (
        f"Write a short story in {lang} about '{topic}'. Be creative, but stick to the topic.\n"
        f"The story should be made up of {target_pct}% of these user-known words (sprinkle naturally; repetition allowed):\n"
        f"{', '.join(req)}\n\n"
        f"The story should seamlessly incorporate these words without forcing them.\n"
        f"If the story has 100 words, {target_pct} words should be from this list.\n"
        f"You do not HAVE to use all words as long as the story meets the requirements.\n"
        f"If the user does not provide enough known words, the story may not meet the desired percentage, which is, then, fine.\n"
        "Return only the story text—no commentary, no translations."
    )

    resp = client.chat.completions.create(
        model=MODEL, temperature=TEMP,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        max_tokens=900
    )

    _push(f"✔ Story ready ({time.time()-t0:.2f}s)")
    return resp.choices[0].message.content.strip()