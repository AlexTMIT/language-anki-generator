import secrets
from flask import Blueprint, render_template, current_app, request, redirect, url_for

bp = Blueprint(
    "flashcards",                       # ← endpoint prefix
    __name__,
    url_prefix="/create",               # /create/… URLs
    template_folder="../../templates/flashcards",
    static_folder="../../static",
)

# ─────  make-flashcards page  ──────────────────────────────────────────
@bp.get("/")
def make_flashcards():
    decks = current_app.anki.deck_names()
    sid   = secrets.token_urlsafe(8)          # 12-char room id
    return render_template(
        "flashcards/make_flashcards.html",
        decks=decks,
        sid=sid,
        random_sid=sid,
    )

# ─────  NEW loader page  ───────────────────────────────────────────────
@bp.get("/load")
def load():
    sid = request.args.get("sid")   # grab it safely
    if not sid:                          # refresh / bad URL
        return redirect(url_for("flashcards.make_flashcards"))
    workflow = request.args.get("wf", "flashcards")

    cfg = {
      "flashcards": dict(
          title="Preparing Flashcards",
          subtitle="Loading time varies by internet speed and length of input.",
          steps=[
              ("sanitize",  "Sanitising word list"),
              ("dupes_imm", "Removing immediate duplicates"),
              ("json",      "Generating JSON from words"),
              ("dupes_sub", "Removing subsequent duplicates"),
              ("prefetch",  "Prefetching media"),
              ("init_picker","Initiating image selection"),
          ]),
      "story": dict(
          title="Generating Story",
          subtitle="Turning your deck into a coherent tale…",
          steps=[
              ("pick",   "Collecting known words"),
              ("draft",  "Drafting story"),
              ("audio",  "Synthesising audio"),
          ]),
    }[workflow]

    return render_template(
        "progress.html",
        sid      = sid,
        title    = cfg["title"],
        subtitle = cfg["subtitle"],
        tasks    = [{"id": i, "label": l} for i, l in cfg["steps"]],
    )