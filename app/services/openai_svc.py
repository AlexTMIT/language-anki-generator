import os
import json
import time
import pathlib
from openai import OpenAI
from app.extensions import socketio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HERE    = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

SANITISE_INSTRUCTIONS = (PROJECT / "instructions" / "sanitise.txt").read_text()
JSON_INSTRUCTIONS     = (PROJECT / "instructions" / "json_card.txt").read_text()

SANITISER_MODEL   = "gpt-4o-mini-2024-07-18"
SANITISER_TEMP    = 0.3
CARDMAKER_MODEL   = "gpt-4.1-mini"
CARDMAKER_TEMP    = 0.1

TTS_MODEL   = "gpt-4o-mini-tts"
TTS_VOICE   = "ash"
TTS_SPEED   = 1.0
TTS_FORMAT  = "mp3"

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

def sanitise(raw: str, language: str) -> list[str]:
    _push("Sanitising word list…")
    t0 = time.time()

    instr = SANITISE_INSTRUCTIONS.replace("{Language}", language)
    resp = client.chat.completions.create(
        model=SANITISER_MODEL,
        temperature=SANITISER_TEMP,
        messages=[
            {"role": "system",  "content": instr},
            {"role": "user",    "content": raw},
        ],
    )

    elapsed = time.time() - t0
    text    = resp.choices[0].message.content.strip()
    toks    = [tok.strip() for tok in text.split(";") if tok.strip()]

    _push(f"✔ Sanitised → {len(toks)} unique token(s)")
    print(f"[SANITISER] Response: {text} (took {elapsed:.2f}s)")
    return toks


def make_json(words: list[str], lang: str) -> list[dict]:
    _push("Asking AI to create JSON card(s)…")
    t0 = time.time()

    instr = JSON_INSTRUCTIONS.replace("{Language}", lang)
    prompt = ", ".join(words)

    resp = client.chat.completions.create(
        model=CARDMAKER_MODEL,
        temperature=CARDMAKER_TEMP,
        messages=[
            {"role": "system", "content": instr},
            {"role": "user",   "content": prompt},
        ],
    )

    elapsed  = time.time() - t0
    json_str = resp.choices[0].message.content.strip()
    print(f"[CARDMAKER] Response received (took {elapsed:.2f}s)")

    try:
        items = json.loads(json_str)
        _push(f"✔ Received {len(items)} card(s) from GPT")
        print(f"Response JSON: {json_str}")
        return items
    except json.JSONDecodeError as e:
        _push(f"❌ Card-maker JSON parse error: {e}")
        raise RuntimeError(f"Card-maker JSON parse error: {e}")
    
def tts(word: str, lang: str) -> bytes:
    prompt = word.strip()
    if not prompt:
        raise ValueError("Word must be non-empty")

    instructions = (
        "Speak in a regular speaking tone fitting to the context. Keep a natural accent of the language."
        f"The language is {lang}."
    )

    _push(f"Generating TTS for “{word}”…")
    t0 = time.time()

    response = client.audio.speech.create(
        model           = TTS_MODEL,
        input           = prompt,
        voice           = TTS_VOICE,
        speed           = TTS_SPEED,
        response_format = TTS_FORMAT,
        instructions    = instructions,
    )

    elapsed = time.time() - t0
    _push(f"✔ TTS ready ({elapsed:.2f}s)")

    return response.content