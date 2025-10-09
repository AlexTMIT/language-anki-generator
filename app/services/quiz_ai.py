import os, json, time
from typing import List, Tuple
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o"
TEMP  = 0.6

def _call(messages, max_tokens=900, temperature=TEMP):
    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL, temperature=temperature, max_tokens=max_tokens, messages=messages
    )
    txt = resp.choices[0].message.content.strip()
    return txt, time.time() - t0

def _sys(lang:str) -> str:
    return (
        "You are a precise language tutor. "
        f"Write native, CEFR-appropriate {lang}. "
        "Always return STRICT JSON. No preambles or comments."
    )

def _pjson(s:str):
    try: return json.loads(s)
    except Exception as e: raise RuntimeError(f"AI JSON parse error: {e}\nRAW: {s[:400]}...")

def gen_vocab_quiz(*, lang:str, level:str, known_words:List[str], n:int) -> list:
    sys = _sys(lang)
    user = (
        f"CEFR level: {level}. Create {n} multiple-choice vocabulary questions in {lang}.\n"
        "Use ONLY the provided known words for targets and to craft plausible distractors:\n"
        f"{', '.join(known_words)}\n"
        'Each item format: {"kind":"vocab","prompt":"...","choices":["A","B","C","D"],"answer":"B","extra":{"explanation":"..."}}.\n'
        "Return a JSON array of items."
    )
    raw, _ = _call([{"role":"system","content":sys},{"role":"user","content":user}], max_tokens=800)
    return _pjson(raw)

def gen_reading_quiz(*, lang:str, level:str, n:int, words:int=100) -> Tuple[str, list]:
    sys = _sys(lang)
    user = (
        f"CEFR level: {level}. Write a {words}-word passage in {lang}. "
        "It may resemble a short news item, story, email, or customer complaint, or something else entirely. "
        "Separate paragraphs with blank lines.\n"
        f"Then create {n} comprehension questions with short answers.\n"
        'Return JSON: {"passage":"...","items":[{"kind":"reading","prompt":"...","answer":"..."}]}'
    )
    raw, _ = _call([{"role":"system","content":sys},{"role":"user","content":user}], max_tokens=1000)
    obj = _pjson(raw)
    return obj["passage"], obj["items"]

def gen_morph_quiz(*, lang:str, level:str, known_words:List[str], n:int) -> list:
    sys = _sys(lang)
    user = (
        f"CEFR level: {level}. Create {n} cloze questions that test conjugation/inflection in {lang}.\n"
        "Use ONLY these known words as the target lemmas (inflect them appropriately in context):\n"
        f"{', '.join(known_words)}\n"
        'Each item format: {"kind":"morph","prompt":"Sentence with ____","answer":"correct_form","extra":{"lemma":"lemma","explanation":"..."}}.\n'
        "Return a JSON array of items."
    )
    raw, _ = _call([{"role":"system","content":sys},{"role":"user","content":user}], max_tokens=900)
    return _pjson(raw)

def gen_translate_quiz(*, lang:str, level:str, n:int, direction:str="L1->L2") -> list:
    sys = _sys(lang)
    instruct = (
        f"CEFR level: {level}. Create {n} short sentences for translation ({direction}). "
        "Keep them diverse but level-appropriate.\n"
        'Return JSON array with: {"kind":"translate","prompt":"source sentence","answer":"ideal translation"}.\n'
    )
    raw, _ = _call([{"role":"system","content":sys},{"role":"user","content":instruct}], max_tokens=900)
    return _pjson(raw)

def eval_translation(*, lang:str, level:str, source:str, candidate:str) -> dict:
    sys = _sys(lang)
    user = (
        f"Evaluate a learner translation at CEFR {level}.\n"
        f"Source: {source}\n"
        f"Candidate: {candidate}\n"
        'Return JSON: {"ok": true|false, "errors": ["issue 1","issue 2", ...]}. '
        "Only list errors; be concise and specific."
    )
    raw, _ = _call([{"role":"system","content":sys},{"role":"user","content":user}], max_tokens=300)
    return _pjson(raw)