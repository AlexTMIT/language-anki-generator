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
    deck  = (request.form.get("deck")  or "").strip()
    lang  = (request.form.get("lang")  or "").strip()
    level = (request.form.get("level") or "").strip()
    qtype = (request.form.get("qtype") or "vocab").strip().lower()
    qlang = (request.form.get("qlang") or "English").strip()  # quiz UI language
    n     = int(request.form.get("n", "5"))

    svc = QuizService(anki=current_app.anki, quiz_ai=quiz_ai, tts_func=openai_tts)

    try:
        if qtype == "vocab":
            bundle = svc.generate_vocab_quiz(deck=deck, lang=lang, level=level, quiz_lang=qlang, n=n)
            session["quiz_bundle"] = bundle
            return render_template(
                "quiz/vocab_run.html",
                title="Quiz: Vocabulary Practice",
                deck=deck,
                lang=lang,
                level=level,
                items=bundle["items"],
            )

        elif qtype == "reading":
            bundle = svc.generate_reading_quiz(lang=lang, level=level, quiz_lang=qlang, n=n)
            bundle["lang"] = lang
            session["quiz_bundle"] = bundle
            return render_template(
                "quiz/reading_run.html",
                title="Quiz: Reading Comprehension",
                passage=bundle["meta"]["passage"],
                items=bundle["items"],
                lang=lang,
            )

        elif qtype == "listening":
            bundle = svc.generate_listening_quiz(lang=lang, level=level, quiz_lang=qlang, n=n)
            bundle["lang"] = lang
            session["quiz_bundle"] = bundle
            return render_template("quiz/listening_run.html",
                                   title="Quiz: Listening Comprehension",
                                   audio=bundle["meta"]["audio"],
                                   items=bundle["items"],
                                   )

        elif qtype == "translate":
            flash("Translation quiz is coming soon. Please choose Vocabulary or Reading.", "info")
            return redirect(url_for("quiz.index"))

        else:
            flash("Unknown quiz type.", "error")
            return redirect(url_for("quiz.index"))

    except Exception as e:
        current_app.logger.exception("Quiz start failed")
        flash(f"Could not start quiz: {e}", "error")
        return redirect(url_for("quiz.index"))


@bp.post("/quiz/grade")
def grade():
    bundle = session.get("quiz_bundle")
    if not bundle:
        flash("Quiz session expired. Please start again.", "error")
        return redirect(url_for("quiz.index"))

    kind  = bundle.get("kind") or "vocab"
    items = bundle.get("items") or []

    # collect answers in order
    user_answers = [(request.form.get(f"q{idx}") or "").strip()
                    for idx, _ in enumerate(items, start=1)]

    try:
        if kind == "vocab":
            verdicts = quiz_ai.eval_vocab_batch(
                lang=bundle["lang"],
                items=items,
                user_answers=user_answers
            )

            rows = []
            correct_count = 0
            for i, (it, ans, v) in enumerate(zip(items, user_answers, verdicts), start=1):
                ok = bool(v and v.get("ok"))
                if ok:
                    correct_count += 1

                canonical = (
                    (v.get("canonical") if v else None) or
                    it.get("answer") or
                    (it.get("lemma") if it.get("type") == "cloze" else "") or
                    "—"
                )

                rows.append({
                    "n": i,
                    "prompt": it.get("prompt", ""),
                    "choices": it.get("choices"),
                    "user": ans or "—",
                    "answer": canonical,
                    "ok": ok,
                    # only show explanation when wrong
                    "explanation": (v.get("explanation", "") if not ok else ""),
                })

            total = max(1, len(items))
            score_text = f"{correct_count} / {total}"

            return render_template(
                "quiz/vocab_results.html",
                title="Quiz: Vocabulary Practice",
                rows=rows,
                score=score_text,
            )

        elif kind == "reading":
            passage = (bundle.get("meta") or {}).get("passage", "")
            lang    = bundle.get("lang") or (request.form.get("lang") or "")
            verdicts = quiz_ai.eval_reading_batch(lang=lang, passage=passage, items=items, user_answers=user_answers)
            rows, correct_count = [], 0
     
            for i, (it, ans, v) in enumerate(zip(items, user_answers, verdicts), start=1):
                ok = bool(v and v.get("ok"))
                if ok:
                    correct_count += 1
                rows.append({
                    "n": i,
                    "prompt": it.get("prompt", ""),
                    "choices": it.get("choices"),
                    "user": ans or "—",
                    "answer": (v.get("canonical", "") if v else ""),
                    "ok": ok,
                    "explanation": (v.get("explanation", "") if not ok else ""),
                })

            total = max(1, len(items))
            score_text = f"{correct_count} / {total}"

            return render_template(
                "quiz/reading_results.html",
                title="Quiz: Reading Comprehension",
                passage=passage,
                rows=rows,
                score=score_text,
            )
        
        elif kind == "listening":
            passage = (bundle.get("meta") or {}).get("passage", "")
            verdicts = quiz_ai.eval_reading_batch(lang=lang, passage=passage, items=items, user_answers=user_answers)
            rows, correct_count = [], 0
            for i, (it, ans, v) in enumerate(zip(items, user_answers, verdicts), start=1):
                ok = bool(v and v.get("ok"))
                if ok: correct_count += 1
                rows.append({
                    "n": i, "prompt": it.get("prompt",""), "choices": it.get("choices"),
                    "user": ans or "—", "answer": (v.get("canonical","") if v else ""),
                    "ok": ok, "explanation": (v.get("explanation","") if not ok else ""),
                })
            score_text = f"{correct_count} / {max(1,len(items))}"
            return render_template("quiz/listening_results.html",
                                   title="Quiz: Listening Comprehension",
                                   rows=rows, score=score_text)

        else:
            flash("That quiz type is not yet implemented for grading.", "error")
            return redirect(url_for("quiz.index"))

    except Exception as e:
        current_app.logger.exception("Quiz grading failed")
        flash(f"Evaluation failed: {e}", "error")
        return redirect(url_for("quiz.index"))