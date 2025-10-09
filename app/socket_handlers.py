# app/socket_handlers.py
from flask import current_app
from app.extensions import socketio
from flask_socketio import join_room

@socketio.on("loader:ready")
def on_loader_ready(data):
    """Fired by the loader page as soon as the socket connects."""
    sid = data.get("sid")
    if not sid:
        return

    job = current_app.caches.get("pending_jobs", {}).pop(sid, None)
    if not job:                 # user refreshed or bogus SID
        return
    join_room(sid)
    
    app = current_app._get_current_object()

    def run_job():
        with app.app_context():
            from app.blueprints.batch import BatchProcessor
            processor = BatchProcessor(
                app.anki,
                app.caches,
                sid,
                job["lang"],
            )
            processor.run(job["form"])

    socketio.start_background_task(run_job)