import os, json, time
from typing import List, Tuple
from openai import OpenAI
from textwrap import dedent

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini-2024-07-18"
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

def gen_vocab_quiz(*, lang: str, level: str, known_words: List[str], n: int, quiz_lang: str) -> list:
    sys = _sys(lang)
    kw = known_words[:n]

    user = dedent(f"""
    CEFR {level}. Create EXACTLY {n} vocabulary questions in {lang}.
    Write all PROMPTS in {quiz_lang}. For multiple-choice, write CHOICES in {lang}.
    Use ONLY these lemmas across prompts/distractors (each at least once overall):
    {", ".join(kw)}

    Mix ALL types:
    - mc        : 4-choice meaning/definition (same POS; near-miss distractors)
    - translate : short sentence translation (free text)
    - cloze     : one blank '____' testing inflection/conjugation of the lemma

    Difficulty scaling (hard rule):
    - A1–A2: concrete topics; simple clauses; minimal idioms. Translate 6–10 tokens.
    - B1: everyday/abstract mix; one subordinate clause OK; modest idioms. Translate 10–16 tokens.
    - B2: more abstract; 1–2 subordinate clauses; natural idioms. Translate 12–18 tokens.
    - C1–C2: nuanced/academic; complex syntax; richer idioms. Translate 16–24 tokens.

    CLOZE constraints (hard rule):
    - The blank MUST correspond to an inflected/derived form of the item’s lemma.
    - The sentence MUST include enough disambiguating cues (collocation, role in sentence, surrounding semantics) so that ONLY that lemma reasonably fits.
    - Avoid underspecified stems like “Det nye ____ er dyrt.” Provide unique cues, e.g. domain/role/collocate (“armbånds____ der viser tiden” → *ur*).
    - Do NOT reveal the lemma; do NOT add hints like “(meaning …)”.

    MC constraints:
    - Exactly 4 choices; all plain strings (no “A:” labels).
    - Same part of speech; 3 plausible near-misses from the same semantic field.
    - Unambiguous single correct choice.

    TRANSLATE constraints:
    - Always a short sentence (not a single word); no proper-noun only items.
    - Natural, idiomatic and level-appropriate for {level}.

    Return ONE JSON object only (no code fences, no comments):
    {{
    "kind":"vocab",
    "q_amount":{n},
    "questions":[
        {{"type":"mc","lemma":"...","pos":"...","prompt":"...","choices":["...","...","...","..."]}},
        {{"type":"translate","lemma":"...","pos":"...","prompt":"..."}},
        {{"type":"cloze","lemma":"...","pos":"...","prompt":"Sentence with ____"}}
    ]
    }}

    Rules: plain strings, idiomatic sentences, correct JSON. For cloze, ensure the lemma is uniquely inferable from context; reject vague stems.
    """)

    raw, _ = _call(
        [{"role":"system","content":sys},{"role":"user","content":user}],
        max_tokens=1400, temperature=0.6,
    )
    obj = _pjson(raw)
    qs  = obj["questions"]
    out = []
    for q in qs[:n]:
        out.append({
            "type": q["type"],
            "lemma": q.get("lemma",""),
            "pos": q.get("pos",""),
            "prompt": q["prompt"],
            "choices": q.get("choices") if q["type"] == "mc" else None,
        })
    return out

def eval_vocab_batch(*, lang: str, items: list, user_answers: list[str]) -> list:
    assert len(items) == len(user_answers)

    payload = []
    for it, ans in zip(items, user_answers):
        entry = {
            "t": it["type"][0],  # 'm', 't', 'c'
            "p": it["prompt"],
            "a": ans
        }
        if it["type"] == "mc":
            entry["c"] = it["choices"]
        if it["type"] == "cloze":
            entry["l"] = it.get("lemma")
        payload.append(entry)

    sys = f"You are a strict {lang} language quiz grader."
    user = (
        "For each item, decide if the user's answer is correct.\n"
        "Rules:\n"
        "- m (multiple choice): pick the most fitting choice as canonical, mark ok true if matches user.\n"
        "- t (translation): mark ok true if meaning matches; accept close synonyms.\n"
        "- c (cloze): mark ok true if user answer is a valid inflected form of the lemma.\n"
        'Return JSON array: [{"ok":true|false,"canonical":"..."}].\n'
        "No explanations, no commentary."
    )

    raw, _ = _call(
        [{"role":"system","content":sys},
         {"role":"user","content":user},
         {"role":"user","content":json.dumps(payload, ensure_ascii=False)}],
        max_tokens=600,
        temperature=0.2
    )
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