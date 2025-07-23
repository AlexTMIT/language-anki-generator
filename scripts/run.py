"""Dev entrypoint: launches the Flask-SocketIO server and opens the browser."""
import sys
import webbrowser
from pathlib import Path
from threading import Timer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.factory import create_app
from app.extensions import socketio

def main() -> None:
    app = create_app()

    Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5001")).start()

    socketio.run(
        app,
        host="0.0.0.0",
        port=5001,
        debug=True,               # false for prod
        use_reloader=False        # prevent double-launch
    )

if __name__ == "__main__":
    main()