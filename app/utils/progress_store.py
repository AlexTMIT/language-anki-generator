from __future__ import annotations
import json, os, time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict

try:
    import redis
    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _r = redis.Redis.from_url(_REDIS_URL, decode_responses=True)
    _r.ping()
except Exception:
    _r = None  # fallback to in-memory

class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"

@dataclass
class Step:
    id: str
    label: str
    state: StepState = StepState.PENDING
    done: int = 0
    total: int = 0
    pct: int = 0
    note: Optional[str] = None

@dataclass
class JobState:
    sid: str
    title: str
    subtitle: str
    steps: List[Step]
    rev: int = 0  # incremented on each change

def _to_json(job: JobState) -> str:
    return json.dumps({
        "sid": job.sid,
        "title": job.title,
        "subtitle": job.subtitle,
        "rev": job.rev,
        "steps": [asdict(s) for s in job.steps],
    }, ensure_ascii=False)

def _from_json(s: str) -> JobState:
    d = json.loads(s)
    steps = [Step(**{**x, "state": StepState(x["state"])}) for x in d["steps"]]
    return JobState(sid=d["sid"], title=d["title"], subtitle=d["subtitle"], steps=steps, rev=int(d.get("rev", 0)))

class ProgressStore:
    """
    Usage:
      ps = ProgressStore()
      ps.create(job) / ps.load(sid) / ps.save(job)
      ps.start/advance/finish/fail/subtitle(...)
    """
    def __init__(self, ttl_seconds: int = 60*60):
        self.ttl = ttl_seconds
        self._mem: Dict[str, str] = {}

    # ---- persistence ----
    def _key(self, sid: str) -> str: return f"job:{sid}:state"

    def load(self, sid: str) -> Optional[JobState]:
        if _r:
            s = _r.get(self._key(sid))
        else:
            s = self._mem.get(self._key(sid))
        return _from_json(s) if s else None

    def save(self, job: JobState) -> None:
        job.rev += 1
        payload = _to_json(job)
        if _r:
            _r.set(self._key(job.sid), payload, ex=self.ttl)
        else:
            self._mem[self._key(job.sid)] = payload

    def create(self, job: JobState) -> None:
        job.rev = 0
        if _r:
            _r.set(self._key(job.sid), _to_json(job), ex=self.ttl)
        else:
            self._mem[self._key(job.sid)] = _to_json(job)

    # ---- high-level API called from your services ----
    def set_subtitle(self, sid: str, text: str):
        job = self.load(sid);  job.subtitle = text;  self.save(job)

    def start(self, sid: str, step_id: str, note: Optional[str]=None, total: Optional[int]=None):
        job = self.load(sid); s = self._step(job, step_id)
        s.state = StepState.RUNNING
        if total is not None: s.total = total
        if note is not None:  s.note = note
        self.save(job)

    def advance(self, sid: str, step_id: str, done: int, total: Optional[int]=None, note: Optional[str]=None):
        job = self.load(sid); s = self._step(job, step_id)
        if total is not None: s.total = total
        s.done = done
        s.pct = int(round((s.done / s.total) * 100)) if s.total else 0
        if note is not None: s.note = note
        self.save(job)

    def finish(self, sid: str, step_id: str):
        job = self.load(sid); s = self._step(job, step_id)
        s.state = StepState.DONE
        if s.total and s.pct < 100: s.pct = 100
        self.save(job)

    def fail(self, sid: str, step_id: str, message: str):
        job = self.load(sid); s = self._step(job, step_id)
        s.state = StepState.ERROR
        s.note = message
        self.save(job)

    def _step(self, job: JobState, step_id: str) -> Step:
        for s in job.steps:
            if s.id == step_id: return s
        raise KeyError(step_id)