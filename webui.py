import json
from dataclasses import dataclass

from flask import (
    Flask, flash, redirect, render_template_string,
    request, url_for,
)

from anki_client import AnkiClient
from audio_forvo import get_audio_blob

MODEL = "*L2: 2025 Revamp"
anki  = AnkiClient()
app   = Flask(__name__)
app.secret_key = "flash"

HTML = """
<!doctype html>
<title>L2 Flashcard Import</title>
<link rel="stylesheet"
 href="https://cdn.jsdelivr.net/npm/mini.css@3.0.1/dist/mini-default.min.css">

<h3>Batch import to “{{ model }}”</h3>
{% for m in get_flashed_messages() %}
  <div>{{ m|safe }}</div>
{% endfor %}

<form method="post" action="{{ url_for('batch') }}">
  <label>Deck
    <select name="deck">{% for d in decks %}<option>{{ d }}</option>{% endfor %}</select>
  </label>
  <label>Language code
    <select name="lang">
      <option value="bl">bl (Belarusian)</option>
      <option value="dk">dk (Danish)</option>
    </select>
  </label>
  <label>JSON array
    <textarea name="blob" rows="12" required placeholder='[...]'></textarea>
  </label>
  <button type="submit">Import</button>
</form>
"""

# ---------- dataclass & mapping ------------------------------------------
@dataclass
class CardData:
    base: str
    grammar: str
    translation: str
    example: str
    example_translation: str

    @classmethod
    def from_json(cls, d: dict):
        return cls(
            base                = d.get("base", "").strip(),
            grammar             = d.get("grammar", "").strip(),
            translation         = d.get("translation", "").strip(),
            example             = d.get("example", "").strip(),
            example_translation = d.get("example-translation", "").strip(),
        )

    def to_fields(self, audio_tag: str = "") -> dict:
        return {
            "Word":        self.base,
            "Grammar":     self.grammar,
            "Meaning":     self.translation,
            "Sentence":    self.example,
            "Translation": self.example_translation,
            "Audio":       audio_tag,
        }

# ---------- routes --------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML, decks=anki.deck_names(), model=MODEL)

@app.route("/batch", methods=["POST"])
def batch():
    deck = request.form["deck"].strip()
    lang = request.form["lang"].strip()
    raw  = request.form["blob"].strip()

    try:
        items = json.loads(raw)
        assert isinstance(items, list)
    except Exception as e:
        flash(f"<mark>JSON error:</mark> {e}")
        return redirect(url_for("index"))

    added = skipped = 0
    for entry in items:
        card = CardData.from_json(entry)

        # -------- audio ----------
        fname, blob = get_audio_blob(lang, card.base)
        audio_tag = ""
        if blob:
            media_name = anki.store_media(fname, blob)
            audio_tag  = f"[sound:{media_name}]"

        fields = card.to_fields(audio_tag)

        try:
            ok = anki.add_note(deck, MODEL, fields)
            added += 1 if ok else 0
            skipped += 0 if ok else 1
        except Exception as e:
            flash(f"Anki error: {e}")
            break

    flash(f"✅ {added} added &nbsp;|&nbsp; ⚠ {skipped} duplicates")
    return redirect(url_for("index"))