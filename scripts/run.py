"""Dev entrypoint: launches the Flask app and opens the browser."""
import sys
import webbrowser
from pathlib import Path
from threading import Timer

# Ensure project root is on sys.path when executing via `python scripts/run.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.factory import create_app


def main() -> None:
    app = create_app()
    Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run()


if __name__ == "__main__":
    main()