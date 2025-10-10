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
    CEFR {level}. Create EXACTLY {n} mixed vocabulary questions.
    Target language (L2): {lang}. Quiz UI language: {quiz_lang}.

    Use ONLY these lemmas across the quiz (each appears at least once overall):
    {", ".join(kw)}

    Types to include:
      1) "mc": multiple choice of MEANINGS in {quiz_lang}.
         Return: {{"type":"mc","lemma":"<L2 lemma>","meaning":"<meaning in {quiz_lang}>","distractors":["d1","d2","d3"]}}
         Rules: meaning/distractors are plain strings in {quiz_lang}; NEVER include the lemma (or any surface form) in choices.

      2) "translate": short sentence to translate FROM {quiz_lang} INTO {lang}.
         Return: {{"type":"translate","source":"<sentence in {quiz_lang}>"}} 
         (UI will say "Translate this sentence into {lang}: …".)

      3) "cloze": VERB-ONLY cloze in {lang} with exactly one blank "____".
         The correct answer is an INFLECTED verb form (NOT infinitive).
         Return: {{"type":"cloze","lemma":"<L2 verb lemma>","sentence":"<{lang} sentence with ____>","morph":{{"tense":"...","person":"...","number":"...","mood":"..."}}}}

    Difficulty scaling:
      - A1–A2: simple clauses; concrete topics; short translate (6–10 tokens).
      - B1: one subordinate clause allowed; 10–16 tokens.
      - B2: 1–2 subordinates; 12–18 tokens.
      - C1–C2: complex/nuanced; 16–24 tokens.

    HARD rules:
      - EXACTLY {n} items total; mix all three types.
      - All JSON values are plain strings/arrays/objects; no code fences; no comments.
      - For "mc", choices are meanings in {quiz_lang} only (no lemma/surface forms).
      - For "cloze", sentence MUST be in {lang}; answer must be an inflected form of the lemma.
      - For "translate", source sentence is in {quiz_lang} (to be translated into {lang}).

    Return ONE STRICT JSON object:
    {{
      "kind":"vocab",
      "q_amount":{n},
      "questions":[
        {{"type":"mc","lemma":"...","meaning":"...","distractors":["...","...","..."]}},
        {{"type":"translate","source":"..."}},
        {{"type":"cloze","lemma":"...","sentence":"...","morph":{{"tense":"...","person":"...","number":"...","mood":"..."}}}}
      ]
    }}
    """)

    raw, _ = _call(
        [{"role":"system","content":sys},{"role":"user","content":user}],
        max_tokens=1100, temperature=0.6,
    )
    obj = _pjson(raw)
    qs  = obj.get("questions", [])

    normalized = []
    for q in qs[:n]:
        qtype = q.get("type")

        if qtype == "mc":
            lemma = q.get("lemma", "").strip()
            meaning = q.get("meaning", "").strip()
            distractors = [d for d in (q.get("distractors") or []) if isinstance(d, str)]
            # guard: 4 choices total, and no lemma leakage into choices
            choices = [meaning] + distractors
            choices = [c for c in choices if c][:4]
            lemma_low = lemma.lower()
            if not lemma or len(choices) != 4 or any(lemma_low in c.lower() for c in choices):
                continue
            # Build the prompt ourselves so the lemma is always visible
            prompt = f"What does ‘{lemma}’ mean?"
            normalized.append({
                "type": "mc",
                "prompt": prompt,
                "choices": choices,
                "lemma": lemma,
            })

        elif qtype == "translate":
            src = (q.get("source") or "").strip()
            if not src:
                continue
            prompt = f"Translate this sentence into {lang}: {src}"
            normalized.append({
                "type": "translate",
                "prompt": prompt,
            })

        elif qtype == "cloze":
            lemma = (q.get("lemma") or "").strip()
            sent  = (q.get("sentence") or "").strip()
            morph = q.get("morph") or {}
            if not lemma or "____" not in sent:
                continue

            # compact morph hint for display
            feats = []
            for key in ("tense","person","number","mood","aspect","voice"):
                if morph.get(key):
                    feats.append(str(morph[key]))
            morph_hint = "verb • " + " • ".join(feats) if feats else "verb"

            normalized.append({
                "type": "cloze",
                "prompt": sent,         # in L2 (lang)
                "lemma": lemma,         # shown as "Inflect/conjugate: <lemma>"
                "morph_hint": morph_hint,
            })

    return normalized

def eval_vocab_batch(*, lang: str, items: list, user_answers: list[str]) -> list:
    assert len(items) == len(user_answers)

    payload = []
    for it, ans in zip(items, user_answers):
        entry = {"t": it["type"][0], "p": it["prompt"], "a": ans}
        if it["type"] == "mc":
            entry["c"] = it["choices"] 
        if it["type"] == "cloze":
            entry["l"] = it.get("lemma") 
        payload.append(entry)

    sys = f"You are a careful but fair {lang} quiz grader. Return STRICT JSON only."

    user = (
        "Grade each item in the provided list. For every item, output one object with:\n"
        '  {"ok": true|false, "canonical": "<non-empty string>", "explanation": "<very short or empty>"}\n'
        "Rules per type:\n"
        "- m (multiple choice): Choose the ONE correct option FROM the provided list `c`. "
        "Set `canonical` to that exact option string (copy verbatim). Mark `ok` true iff the user's answer exactly matches that option; "
        "however treat minor case/diacritics/punctuation/whitespace differences as correct. Do not invent new options.\n"
        "- t (translation): `canonical` should be a concise, natural target sentence. "
        "Mark `ok` true if the user's answer preserves meaning; ignore minor case/diacritics/punctuation/whitespace differences. "
        "Only mark false for real errors (wrong words, grammar that flips meaning, missing essential content). "
        "If `ok` is true, set `explanation` to empty.\n"
        "- c (cloze): The expected answer is a SINGLE inflected verb form of lemma `l` (NOT the base). "
        "Set `canonical` to that inflected form. Mark `ok` true iff the user's answer matches it, "
        "again ignoring minor case/diacritics/punctuation/whitespace differences.\n"
        "General:\n"
        "- Be consistent. No commentary. JSON array only. If correct, prefer an empty explanation."
    )

    raw, _ = _call(
        [{"role":"system","content":sys},
         {"role":"user","content":user},
         {"role":"user","content":json.dumps(payload, ensure_ascii=False)}],
        max_tokens=500,
        temperature=0.2,
    )
    return _pjson(raw)

def gen_reading_quiz(*, lang: str, level: str, n: int, words: int = 180, quiz_lang: str = "English") -> tuple[str, list]:
    sys = _sys(lang)
    user = dedent(f"""
    CEFR {level}. Write a ~{words}-word passage in {lang}. Separate paragraphs with blank lines.
    Then create EXACTLY {n} comprehension questions that test understanding (mix of multiple-choice and short-answer).

    Constraints:
    - Multiple-choice (type "mc"): 4 choices, plain strings, in {quiz_lang}. Set "answer" to the exact correct choice string.
    - Short-answer (type "short"): concise question, set "answer" to a short canonical answer in {quiz_lang}.
    - All questions must be answerable ONLY from the passage (no outside knowledge).
    - Keep questions clear and unambiguous.

    Return ONE STRICT JSON object (no code fences, no comments):
    {{
      "passage":"<the passage in {lang}>",
      "questions":[
        {{"type":"mc","prompt":"<question in {quiz_lang}>","choices":["...","...","...","..."],"answer":"<one of the choices>"}},
        {{"type":"short","prompt":"<question in {quiz_lang}>","answer":"<short canonical answer>"}}
      ]
    }}
    """)

    raw, _ = _call([{"role": "system", "content": sys},
                    {"role": "user",   "content": user}],
                   max_tokens=1600, temperature=0.6)

    obj = _pjson(raw)
    passage = (obj.get("passage") or "").strip()
    qs = obj.get("questions") or []

    # normalize
    out = []
    for q in qs[:n]:
        qtype = q.get("type")
        if qtype == "mc":
            choices = q.get("choices") or []
            ans = (q.get("answer") or "").strip()
            if len(choices) == 4 and ans in choices:
                out.append({
                    "type": "mc",
                    "prompt": q.get("prompt", "").strip(),
                    "choices": choices,
                    "answer": ans
                })
        else:
            # short-answer
            ans = (q.get("answer") or "").strip()
            if ans:
                out.append({
                    "type": "short",
                    "prompt": q.get("prompt", "").strip(),
                    "answer": ans
                })

    return passage, out


def eval_reading_batch(*, lang: str, passage: str, items: list, user_answers: list[str]) -> list:
    packed = []
    for it, ans in zip(items, user_answers):
        entry = {
            "t": "m" if it["type"] == "mc" else "s",
            "q": it["prompt"],
            "a": ans
        }
        if it["type"] == "mc":
            entry["c"] = it["choices"]
            entry["k"] = it["answer"]
        else:
            entry["k"] = it["answer"]
        packed.append(entry)

    sys = f"You are a careful but fair {lang} reading-comprehension grader. Return STRICT JSON only."
    user = (
        "You will receive a passage and a list of items with user answers.\n"
        "Grade EACH item using ONLY the passage content (no outside knowledge).\n"
        "For each item, output an object: "
        '{"ok": true|false, "canonical": "<gold answer>", "explanation": "<very short or empty>"}\n'
        "Rules:\n"
        "- m (multiple choice): canonical MUST be exactly one of the provided choices 'c' and equal to 'k'. "
        "Mark ok true iff the user's answer matches that choice, but treat minor case/diacritics/punctuation/whitespace differences as correct.\n"
        "- s (short): canonical is the concise key answer 'k'. Mark ok true if the user's answer matches in meaning; "
        "ignore minor case/diacritics/punctuation/whitespace differences. If correct, leave explanation empty.\n"
        "Output a JSON array only. No comments."
    )

    raw, _ = _call(
        [{"role":"system","content":sys},
         {"role":"user","content":"PASSAGE:\n" + passage},
         {"role":"user","content":user},
         {"role":"user","content":json.dumps(packed, ensure_ascii=False)}],
        max_tokens=900, temperature=0.0
    )
    return _pjson(raw)

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