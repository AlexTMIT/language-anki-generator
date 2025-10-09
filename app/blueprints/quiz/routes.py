from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from app.services.quiz_service import QuizService
from app.services import quiz_ai
from app.services.openai_svc import tts as openai_tts

bp = Blueprint(
    "quiz", __name__,
    template_folder="../../templates/quiz",
    static_folder="../../static"
)

@bp.get("/quiz")
def index():
    decks = current_app.anki.deck_names()
    return render_template("quiz/quiz.html", decks=decks)

@bp.post("/quiz/start")
def start():
    deck = request.form.get("deck", "").strip()
    lang = request.form.get("lang", "").strip()
    level = request.form.get("level", "").strip()
    qtype = request.form.get("qtype", "").strip()

    if not (lang and level and qtype):
        flash("Please complete all fields.", "error")
        return redirect(url_for("quiz.index"))

    svc = QuizService(anki=current_app.anki, quiz_ai=quiz_ai, tts_func=openai_tts)

    if qtype != "vocab":
        flash("Only Vocabulary Practice is implemented right now.", "error")
        return redirect(url_for("quiz.index"))

    bundle = svc.generate_vocab_quiz(deck=deck, lang=lang, level=level, n=10)
    session["quiz_bundle"] = bundle

    return render_template(
        "quiz/vocab_run.html",
        title="Quiz: Vocabulary Practice",
        deck=deck,
        lang=lang,
        level=level,
        items=bundle["items"]
    )

@bp.post("/quiz/grade")
def grade():
    bundle = session.get("quiz_bundle")
    if not bundle:
        flash("Quiz session expired. Please start again.", "error")
        return redirect(url_for("quiz.index"))

    items = bundle["items"]
    user_answers = {}
    correct = 0
    graded_rows = []

    for idx, item in enumerate(items, start=1):
        key = f"q{idx}"
        user_ans = (request.form.get(key) or "").strip()
        user_answers[key] = user_ans

        # answers can be string or list[str]
        correct_ans = item.get("answer")
        if isinstance(correct_ans, list):
            is_right = user_ans.lower() in [a.strip().lower() for a in correct_ans]
            canonical = correct_ans[0]
        else:
            is_right = user_ans.lower() == str(correct_ans).strip().lower()
            canonical = correct_ans

        if is_right:
            correct += 1

        graded_rows.append({
            "n": idx,
            "prompt": item.get("prompt", ""),
            "choices": item.get("choices"),
            "user": user_ans,
            "answer": canonical,
            "ok": is_right,
            "explanation": (item.get("extra") or {}).get("explanation")
        })

    score = f"{correct} / {len(items)}"
    return render_template(
        "quiz/vocab_results.html",
        title="Quiz: Vocabulary Practice",
        rows=graded_rows,
        score=score
    )