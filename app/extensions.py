from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import threading

executor = ThreadPoolExecutor(max_workers=6)

caches: dict[str, dict[str, str|list[str]]] = {
    "thumb": {},
    "audio": {},
}

progress: dict[str, dict[str, int]] = defaultdict(dict)
progress_lock = threading.Lock()