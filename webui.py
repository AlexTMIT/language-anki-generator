from concurrent import futures
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed


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
THUMB_CACHE: dict[str, list[str]] = {}
AUDIO_CACHE: dict[str, str] = {}
EXEC = ThreadPoolExecutor(max_workers=6)   # 6 parallel fetchers

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
img {width:240px;height:135px;object-fit:cover;border:3px solid transparent;cursor:pointer}
img.sel{border-color:#2196f3;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:6px;}
.dropzone{border:2px dashed #888;padding:12px;text-align:center;margin-top:8px;color:#666}
</style>

<h4>{{ word }} ({{ trans }}, {{ gram }}) – pick / drop / paste up to 3 images</h4>

<form id=f method=post enctype=multipart/form-data>
  <div class=grid id=grid>
  {% for u in urls %}
    <label><input type=checkbox name=url value="{{u}}" hidden>
      <img src="{{u}}">
    </label>
  {% endfor %}
  </div>

  <div class="dropzone" id=dz>
    ⇧ Drag images here or paste (⌘V / Ctrl-V) ⇧
    <input type=file id=file name=file multiple accept="image/*" hidden>
  </div>

  <button type=submit id=btn disabled>Continue</button>
</form>

<script>
const max=3;
const grid=document.getElementById('grid');
const btn=document.getElementById('btn');
const fileInput=document.getElementById('file');

function currentCount(){
  return document.querySelectorAll('input[name=url]:checked').length + fileInput.files.length;
}

function toggleBox(box,img){
  if(!box.checked && currentCount()>=max) return;
  box.checked=!box.checked;
  img.classList.toggle('sel',box.checked);
  btn.disabled=currentCount()===0;
  if(currentCount()===max) document.getElementById('f').submit();
}

/* — click on thumbs — */
document.querySelectorAll('label').forEach(lbl=>{
  const box=lbl.querySelector('input');
  const img=lbl.querySelector('img');
  lbl.onclick=e=>{ toggleBox(box,img); };
});

/* — drag-drop local files — */
const dz=document.getElementById('dz');
dz.ondragover=e=>{e.preventDefault(); dz.style.borderColor='#2196f3';};
dz.ondragleave=e=>{dz.style.borderColor='#888';};
dz.ondrop=e=>{
  e.preventDefault(); dz.style.borderColor='#888';
  const dt=new DataTransfer();
  [...fileInput.files].forEach(f=>dt.items.add(f));       // keep existing
  [...e.dataTransfer.files].slice(0,max-currentCount())
       .forEach(f=>dt.items.add(f));
  fileInput.files=dt.files;
  previewFiles(dt.files);
};

/* — paste image from clipboard — */
document.addEventListener('paste',e=>{
  for (const item of e.clipboardData.items){
    if(item.type.startsWith('image') && currentCount()<max){
      const file=item.getAsFile();
      const dt=new DataTransfer();
      [...fileInput.files].forEach(f=>dt.items.add(f));
      dt.items.add(file);
      fileInput.files=dt.files;
      previewFiles([file]);
    }
  }
});

/* show tiny preview for dropped/pasted files */
function previewFiles(files){
  [...files].forEach(f=>{
    const url=URL.createObjectURL(f);
    const img=document.createElement('img');
    img.src=url;
    img.style.border='3px solid #2196f3';
    grid.prepend(img);                // visual feedback
  });
  btn.disabled=currentCount()===0;
  if(currentCount()===max) document.getElementById('f').submit();
}
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

def prefetch(card: dict, lang: str):
    """Background job: fetch audio & thumbs, store in caches."""
    word = card["base"]
    # thumbs
    THUMB_CACHE[word] = google_thumbs(card["keyword"])
    # audio
    fname, blob = get_audio_blob(lang, word)
    AUDIO_CACHE[word] = ""
    if blob:
        media = anki.store_media(fname, blob)
        AUDIO_CACHE[word] = f"[sound:{media}]"

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

    uniques, dup_count, futures = [], 0, []

    for c in cards:
        word = c["base"]
        test_id = anki.add_minimal_note(DUPE_DECK, MODEL, word)
        if test_id is None:
            dup_count += 1
            continue
        anki.delete_note(test_id)
        uniques.append(c)

        # ---------- spawn background prefetch (one per card) ----------
        futures.append(EXEC.submit(prefetch, c, lang))

    # optional: wait so errors surface now
    for f in as_completed(futures):
        try:
            f.result()               # propagate exceptions, if any
        except Exception as e:
            app.logger.warning("Prefetch failed: %s", e)

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
        sel_urls = request.form.getlist("url")       # from checkboxes
        uploaded  = request.files.getlist("file")    # drag/drop or paste

        card = CardData.from_dict(cards[idx])
        lang = session["lang"]
        deck = session["deck"]

        # ----- audio (unchanged) -----
        audio_tag = AUDIO_CACHE.get(card.base)
        if audio_tag is None:
            audio_tag = ""

        # ----- images -----
        img_tags = []

        # 1) URLs (download) – do it in parallel to avoid serial latency
        need = sel_urls[:max(0, 3 - len(img_tags))]
        
        def dl_and_store(u: str) -> str:
            ext   = Path(urlparse(u).path).suffix or ".jpg"
            fname = f"{uuid.uuid4().hex}{ext}"
            raw   = _download(u)                 # remote GET
            media = anki.store_media(fname, raw) # local POST to AnkiConnect
            return f'<img src="{media}">'

        for fut in as_completed([EXEC.submit(dl_and_store, u) for u in need]):
            img_tags.append(fut.result())

        # 2) Uploaded files
        for f in uploaded[:max(0,3-len(img_tags))]:
            raw = f.read()
            ext = Path(f.filename).suffix or ".jpg"
            fname_img = f"{uuid.uuid4().hex}{ext}"
            media_name = anki.store_media(fname_img, raw)
            img_tags.append(f'<img src="{media_name}">')

        fields = card.to_fields(audio=audio_tag, images=img_tags)
        if anki.add_note(deck, MODEL, fields):
            session["added"] += 1          # success
        else:
            session["dups"]  += 1          # duplicate at this late stage

        # ── move to next card or finish ─────────────────────────────
        session["idx"] += 1
        if session["idx"] >= len(cards):
            flash(f"Done! ✅ {session['added']} added | ⚠ {session['dups']} duplicates")
            
            return redirect(url_for("index"))
        else:
            return redirect(url_for("picker"))

    # ---------- GET: show picker -------------------------
    card = CardData.from_dict(cards[idx])

    return render_template_string(
        PAGE_PICK,
        word=card.base,
        trans=card.translation,
        gram=card.grammar,
        urls=THUMB_CACHE.get(card.base)
             or google_thumbs(card.keyword),
    )