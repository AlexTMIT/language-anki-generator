import webbrowser
from threading import Timer
from webui import app

if __name__ == "__main__":
    Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run()