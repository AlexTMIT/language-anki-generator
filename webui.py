import json
from dataclasses import dataclass

from flask import (
    Flask,
    flash,
    redirect,
    render_template_string,
    request,
    url_for,
)

from anki_client import AnkiClient

MODEL = "*L2: 2025 Revamp"
anki = AnkiClient()
app = Flask(__name__)
app.secret_key = "flash-messages-only"

# ───────────────────────── HTML ──────────────────────────
TEMPLATE = """
<!doctype html>
<title>Flashcard Maker – L2 Batch</title>
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/mini.css@3.0.1/dist/mini-default.min.css">
<h3>Batch import JSON → {{ model }}</h3>

{% with msgs = get_flashed_messages() %}
  {% if msgs %}
    <div class="row">
      <div class="col-sm-12">{{ msgs[0]|safe }}</div>
    </div>
  {% endif %}
{% endwith %}

<form method="post" action="{{ url_for('batch') }}">
  <label>Deck
    <select name="deck">
      {% for d in decks %}
        <option value="{{ d }}">{{ d }}</option>
      {% endfor %}
    </select>
  </label>

  <label>Paste JSON array
    <textarea name="blob" rows="12" required
      placeholder='[{"base": "выцерці", ...}, …]'></textarea>
  </label>

  <button type="submit">Import</button>
</form>
"""

# ───────────────────  dataclass for mapping ──────────────
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
            base=d.get("base", "").strip(),
            grammar=d.get("grammar", "").strip(),
            translation=d.get("translation", "").strip(),
            example=d.get("example", "").strip(),
            example_translation=d.get("example-translation", "").strip(),
        )

    def to_fields(self) -> dict:
        """Return dict matching the *L2: 2025 Revamp field order."""
        return {
            "Word": self.base,
            "Grammar": self.grammar,
            "Meaning": self.translation,
            "Sentence": self.example,
            "Translation": self.example_translation,
            # Image 1/2/3, Audio left blank for now
        }


# ────────────────────  routes ────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template_string(TEMPLATE, decks=anki.deck_names(), model=MODEL)


@app.route("/batch", methods=["POST"])
def batch():
    deck = request.form["deck"].strip()
    blob = request.form["blob"].strip()

    # 1. parse JSON --------------------------------------------------------
    try:
        raw = json.loads(blob)
        assert isinstance(raw, list)
    except Exception as e:
        flash(f"<mark>JSON error:</mark> {e}")
        return redirect(url_for("index"))

    cards = [CardData.from_json(x) for x in raw]

    # 2. push to Anki ------------------------------------------------------
    added, skipped = 0, 0
    try:
        for c in cards:
            ok = anki.add_note(deck, MODEL, c.to_fields())
            added += 1 if ok else 0
            skipped += 0 if ok else 1
    except Exception as e:
        flash(f"<mark>Anki error:</mark> {e}")
        return redirect(url_for("index"))

    # 3. summary -----------------------------------------------------------
    flash(f"✅ {added} added &nbsp;|&nbsp; ⚠ {skipped} duplicates")
    return redirect(url_for("index"))