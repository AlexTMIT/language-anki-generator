import os
import json
import time
import pathlib
from openai import OpenAI

# ────────────────────────────────────────────────────────────────
#  Configuration & load instruction prompts (once at import time)
# ────────────────────────────────────────────────────────────────

# instantiate a dedicated client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# base paths
HERE    = pathlib.Path(__file__).resolve().parent           # …/app/services
PROJECT = HERE.parent.parent                                # …/language-anki-generator

# load system prompts
SANITISE_INSTRUCTIONS = (PROJECT / "instructions" / "sanitise.txt").read_text()
JSON_INSTRUCTIONS     = (PROJECT / "instructions" / "json_card.txt").read_text()

# which models & temps to use
SANITISER_MODEL   = "gpt-4o"
SANITISER_TEMP    = 0.25
CARDMAKER_MODEL   = "gpt-3.5-turbo"
CARDMAKER_TEMP    = 0.10


# ────────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────────

def sanitise(raw: str) -> list[str]:
    """
    Split & clean the user’s raw list into semicolon-delimited tokens.
    Prints input/output lengths, token count, and elapsed time.
    """
    print(f"[SANITISER] Input length: {len(raw)} chars")
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
    print(f"[SANITISER] Output length: {len(text)} chars, {len(toks)} tokens, took {elapsed:.2f}s")
    return toks


def make_json(words: list[str]) -> list[dict]:
    """
    Turn a list of head-words into your JSON card array.
    Prints prompt length, response length, object count, and elapsed time.
    """
    prompt = ", ".join(words)
    print(f"[CARDMAKER] Prompt: {len(words)} words, {len(prompt)} chars")
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
    print(f"[CARDMAKER] Response: {len(json_str)} chars, took {elapsed:.2f}s")

    try:
        items = json.loads(json_str)
        print(f"[CARDMAKER] Parsed {len(items)} JSON objects ✅")
        return items
    except Exception as e:
        print(f"[CARDMAKER] JSON parse error: {e}")
        raise RuntimeError(f"Card-maker JSON parse error: {e}")