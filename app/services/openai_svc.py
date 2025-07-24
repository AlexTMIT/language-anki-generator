import os
import json
import time
import pathlib
from openai import OpenAI
from app.extensions import socketio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HERE    = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

JSON_INSTRUCTIONS = (PROJECT / "instructions" / "json_card.txt").read_text()
CARDMAKER_MODEL   = "gpt-4.1-mini"
CARDMAKER_TEMP    = 0.1

def _push(msg: str) -> None:
    socketio.emit("progress", msg)

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