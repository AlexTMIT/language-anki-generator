from flask_socketio import SocketIO

socketio: SocketIO = SocketIO(
    cors_allowed_origins="*",  # dev convenience; tighten in prod
    async_mode="eventlet",
)

caches: dict[str, dict] = {"thumb": {}, "audio": {}}