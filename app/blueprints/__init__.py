from flask import Flask
from . import index, batch, picker


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(index.bp)
    app.register_blueprint(batch.bp)
    app.register_blueprint(picker.bp)