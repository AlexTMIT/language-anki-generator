from flask import (
    Flask,
    redirect,
    render_template_string,
    request,
    url_for,
    flash,
)
from anki_client import AnkiClient

MODEL = "Basic"
anki = AnkiClient()
app = Flask(__name__)
app.secret_key = "just-for-flash-messages"   # any random string

TEMPLATE = """
<!doctype html>
<title>Flashcard Maker</title>
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/mini.css@3.0.1/dist/mini-default.min.css">
<h3>Add a single card</h3>
{{ get_flashed_messages()[0] if get_flashed_messages() else "" }}
<form method="post" action="{{ url_for('add') }}">
  <label>Deck
    <select name="deck">
      {% for d in decks %}
        <option value="{{ d }}">{{ d }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Word <input name="word" required></label>
  <label>Meaning <input name="meaning" required></label>
  <button type="submit">Add</button>
</form>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(TEMPLATE, decks=anki.deck_names())

@app.route("/add", methods=["POST"])
def add():
    deck, word, meaning = (
        request.form["deck"].strip(),
        request.form["word"].strip(),
        request.form["meaning"].strip(),
    )
    if not all((deck, word, meaning)):
        flash("All fields required.")
        return redirect(url_for("index"))

    ok = False
    try:
        ok = anki.add_note(deck, MODEL, {"Front": word, "Back": meaning})
    except Exception as e:
        flash(f"Anki error: {e}")
    else:
        flash("✓ Added!" if ok else "Duplicate – skipped")

    return redirect(url_for("index"))