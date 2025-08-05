from flask import Flask
from .site.routes      import bp as site_bp
from .flashcards.routes import bp as flashcards_bp
from .batch            import bp as batch_bp
from .picker           import bp as picker_bp

def register_blueprints(app: Flask) -> None:
    app.register_blueprint(site_bp)
    app.register_blueprint(flashcards_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(picker_bp)