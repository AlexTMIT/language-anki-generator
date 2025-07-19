import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import (
    Flask, flash, redirect, render_template_string,
    request, session, url_for
)

from anki_client import AnkiClient
from audio_forvo import get_audio_blob

# ───────── Config ────────────────────────────────────────────────────
MODEL = "*L2: 2025 Revamp"
GOOGLE_KEY = os.getenv("GOOGLE_CSE_KEY")
GOOGLE_CX  = os.getenv("GOOGLE_CSE_CX")
assert GOOGLE_KEY and GOOGLE_CX, "Set GOOGLE_CSE_KEY & GOOGLE_CSE_CX env vars"

anki = AnkiClient()
app  = Flask(__name__)
app.secret_key = "l2-secret-for-session"  # any random string

# keep fetched thumbs in RAM for speed (sid → [urls])
CACHE: dict[str, list[str]] = {}

# ───────── HTML templates (inline for brevity) ───────────────────────
PAGE_FORM = """
<!doctype html>
<title>L2 Import</title>
<link rel=stylesheet href=https://cdn.jsdelivr.net/npm/mini.css@3/dist/mini-default.min.css>
<h3>Batch import – {{ model }}</h3>
{% for m in get_flashed_messages() %}<div>{{ m|safe }}</div>{% endfor %}
<form method=post action="{{ url_for('batch') }}">
<label>Deck <select name=deck>
{% for d in decks %}<option>{{d}}</option>{% endfor %}</select></label>
<label>Language <select name=lang>
  <option value=bl>bl (Belarusian)</option>
  <option value=dk>dk (Danish)</option>
</select></label>
<label>JSON <textarea name=blob rows=12 required placeholder='[...]'></textarea></label>
<button type=submit>Start import</button>
</form>
"""

PAGE_PICK = """
<!doctype html>
<title>Choose images – {{ word }}</title>
<link rel=stylesheet href=https://cdn.jsdelivr.net/npm/mini.css@3/dist/mini-default.min.css>
<style>
img {width:120px;height:120px;object-fit:cover;border:3px solid transparent;cursor:pointer}
img.sel{border-color:#2196f3;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;}
</style>
<h4>{{ word }} – pick up to 3 images ({{ picked }}/3)</h4>
<form id=f method=post>
  <div class=grid>
  {% for u in urls %}
    <label><input type=checkbox name=img value="{{u}}" hidden>
      <img src="{{u}}">
    </label>
  {% endfor %}
  </div>
  <button type=submit id=btn disabled>Continue</button>
</form>
<script>
const max=3;
document.querySelectorAll('label').forEach(lbl=>{
  const box=lbl.querySelector('input');
  const img=lbl.querySelector('img');
  lbl.onclick=e=>{
    if(!box.checked && document.querySelectorAll('input:checked').length>=max) return;
    box.checked=!box.checked;
    img.classList.toggle('sel',box.checked);
    btn.disabled=document.querySelectorAll('input:checked').length===0;
    if(document.querySelectorAll('input:checked').length===max){
      document.getElementById('f').submit();
    }
  };
});
</script>
"""

# ───────── helpers ───────────────────────────────────────────────────
@dataclass
class CardData:
    base: str
    grammar: str
    translation: str
    example: str
    example_translation: str
    keyword: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            base=d["base"].strip(),
            grammar=d["grammar"].strip(),
            translation=d["translation"].strip(),
            example=d["example"].strip(),
            example_translation=d["example-translation"].strip(),
            keyword=d["keyword"].strip()
        )

    def to_fields(self, audio="", images=None):
        images = images or []
        return {
            "Word":        self.base,
            "Grammar":     self.grammar,
            "Meaning":     self.translation,
            "Sentence":    self.example,
            "Translation": self.example_translation,
            "Audio":       audio,
            "Image 1":     images[0] if len(images) > 0 else "",
            "Image 2":     images[1] if len(images) > 1 else "",
            "Image 3":     images[2] if len(images) > 2 else "",
        }


def google_thumbs(query: str, k=20) -> list[str]:
    params = {
        "key": GOOGLE_KEY, "cx": GOOGLE_CX, "searchType": "image",
        "safe": "active", "q": query, "num": 10
    }
    r = requests.get("https://customsearch.googleapis.com/customsearch/v1", params=params).json()
    urls = [it["link"] for it in r.get("items", [])]
    return urls[:k]


def _download(url: str) -> bytes:
    return requests.get(url, timeout=20).content


# ───────── Routes ────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE_FORM, decks=anki.deck_names(), model=MODEL)


@app.route("/batch", methods=["POST"])
def batch():
    """Parse JSON list, stash in session, redirect to first picker."""
    try:
        items = json.loads(request.form["blob"])
        assert isinstance(items, list)
        cards = items
    except Exception as e:
        flash(f"<mark>JSON error:</mark> {e}")
        return redirect(url_for("index"))

    deck  = request.form["deck"]
    lang  = request.form["lang"]

    DUPE_DECK = "dupe-check"
    anki.ensure_deck(DUPE_DECK)

    uniques, dup_count = [], 0
    for c in cards:
        test_id = anki.add_minimal_note(DUPE_DECK, MODEL, c["base"])
        if test_id is None:          # duplicate detected
            dup_count += 1
            continue
        # fresh → delete placeholder and keep entry
        anki.delete_note(test_id)
        uniques.append(c)

    if dup_count:
        flash(f"⚠ Skipped {dup_count} duplicate(s) right away.")
    anki.delete_deck(DUPE_DECK)

    if not uniques:
        return redirect(url_for("index"))

    session["cards"] = uniques
    session["deck"]  = deck
    session["lang"]  = lang
    session["idx"]   = 0
    session["added"] = 0
    session["dups"]  = dup_count
    return redirect(url_for("picker"))


@app.route("/picker", methods=["GET", "POST"])
def picker():
    """Image-selection step for current card."""
    if "cards" not in session:
        return redirect(url_for("index"))

    idx  = session["idx"]
    cards= session["cards"]

    # ---------- handle POST (images selected) ------------
    if request.method == "POST":
        sel = request.form.getlist("img")
        card = CardData.from_dict(cards[idx])
        lang = session["lang"]
        deck = session["deck"]

        # audio
        fname, blob = get_audio_blob(lang, card.base)
        audio_tag = ""
        if blob:
            media = anki.store_media(fname, blob)
            audio_tag = f"[sound:{media}]"

        # images
        img_tags = []
        for u in sel[:3]:
            ext = Path(urlparse(u).path).suffix or ".jpg"
            fname_img = f"{uuid.uuid4().hex}{ext}"
            raw = _download(u)
            media_name = anki.store_media(fname_img, raw)
            img_tags.append(f'<img src="{media_name}">')

        fields = card.to_fields(audio=audio_tag, images=img_tags)
        if anki.add_note(deck, MODEL, fields):
            session["added"] += 1
        else:
            session["dups"]  += 1   # extremely rare now—race condition

        # next card
        session["idx"] += 1
        if session["idx"] >= len(cards):
            flash(f"Done! ✅ {session['added']} added | ⚠ {session['dups']} duplicates")
            session.pop("cards")
            return redirect(url_for("index"))
        else:
            return redirect(url_for("picker"))

    # ---------- GET: show picker -------------------------
    card = CardData.from_dict(cards[idx])
    sid = f"{idx}-{card.keyword}"
    if sid not in CACHE:
        CACHE[sid] = google_thumbs(card.keyword)

    return render_template_string(
        PAGE_PICK,
        word=card.base,
        urls=CACHE[sid],
        picked=0,
    )