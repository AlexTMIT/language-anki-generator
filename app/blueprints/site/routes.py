from flask import Blueprint, render_template

bp = Blueprint(
    "site", __name__,
    template_folder="../../templates/site",
    static_folder="../../static"
)

@bp.get("/")
def landing():
    return render_template("site/index.html")