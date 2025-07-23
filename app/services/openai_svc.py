import os
import json
import time
import pathlib
from openai import OpenAI
from app.extensions import socketio

# ────────────────────────────────────────────────────────────────
#  Configuration & load instruction prompts (once at import time)
# ────────────────────────────────────────────────────────────────

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HERE    = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

SANITISE_INSTRUCTIONS = (PROJECT / "instructions" / "sanitise.txt").read_text()
JSON_INSTRUCTIONS     = (PROJECT / "instructions" / "json_card.txt").read_text()

SANITISER_MODEL   = "gpt-3.5-turbo"
SANITISER_TEMP    = 0.3
CARDMAKER_MODEL   = "gpt-4o"
CARDMAKER_TEMP    = 0.1

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

# ────────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────────

def sanitise(raw: str) -> list[str]:
    print(f"[SANITISER] Input: {raw}")
    print(f"[SANITISER] Input length: {len(raw)} chars")
    _push("Sanitising word list…")
    t0 = time.time()

    resp = client.chat.completions.create(
        model=SANITISER_MODEL,
        temperature=SANITISER_TEMP,
        messages=[
            {"role": "system",  "content": SANITISE_INSTRUCTIONS},
            {"role": "user",    "content": raw},
        ],
    )

    elapsed = time.time() - t0
    text    = resp.choices[0].message.content.strip()
    toks    = [tok.strip() for tok in text.split(";") if tok.strip()]
    print(f"[SANITISER] Response: {text}")
    print(f"[SANITISER] Output length: {len(text)} chars, {len(toks)} tokens, took {elapsed:.2f}s")
    _push(f"✔ Sanitised → {len(toks)} unique token(s)")
    return toks


def make_json(words: list[str]) -> list[dict]:
    _push("Asking AI to create JSON card(s)…")
    prompt = ", ".join(words)
    print(f"[CARDMAKER] Prompt: {words}, {len(prompt)} chars")
    t0 = time.time()

    resp = client.chat.completions.create(
        model=CARDMAKER_MODEL,
        temperature=CARDMAKER_TEMP,
        messages=[
            {"role": "system", "content": JSON_INSTRUCTIONS},
            {"role": "user",   "content": prompt},
        ],
    )

    elapsed  = time.time() - t0
    json_str = resp.choices[0].message.content.strip()
    print(f"[CARDMAKER] Response: {json_str}, took {elapsed:.2f}s")

    try:
        items = json.loads(json_str)
        print(f"[CARDMAKER] Parsed {len(items)} JSON objects ✅")
        _push(f"✔ Received {len(items)} card(s) from GPT")
        return items
    except Exception as e:
        print(f"[CARDMAKER] JSON parse error: {e}")
        _push(f"❌ Card-maker JSON parse error: {e}")
        raise RuntimeError(f"Card-maker JSON parse error: {e}")