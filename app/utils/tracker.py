from __future__ import annotations
from typing import List
from app.extensions import socketio
import threading, time

class Step:
    def __init__(self, id:str, label:str, total:int|None=None):  # total == None → spinner
        self.id     = id
        self.label  = label
        self.total  = total
        self.done   = 0
        self.state  = "idle"   # idle | run | done | fail

class ProgressTracker:
    def __init__(self, sid:str, steps:List[tuple]):
        self.sid   = sid
        self.steps : dict[str,Step] = {s[0]:Step(*s) for s in steps}
        self._send("tracker:init", {"total": len(steps)})

    # ---- helpers --------------------------------------------------------
    def _send(self, ev:str, payload:dict):
        socketio.emit(ev, payload, to=self.sid)

    def _calc_pct(self) -> int:
        done = sum(1 for s in self.steps.values() if s.state == "done")
        return int(done / len(self.steps) * 100)
    
    def set_total(self, id: str, total: int):
        self.steps[id].total = total

    def interpolate(self, step_id: str, seconds: float, tick: float = .2):
        step          = self.steps[step_id]
        step.total    = 100          # treat as percentage buckets
        stop_signal   = threading.Event()
        start_time    = time.time()

        def loop():
            while not stop_signal.is_set():
                pct = min(99, int((time.time() - start_time) / seconds * 100))
                self.progress(step_id, pct, 100)
                stop_signal.wait(tick)

        threading.Thread(target=loop, daemon=True).start()
        return stop_signal.set

    # ---- API ------------------------------------------------------------
    def start(self, id:str):                       # when a step begins
        self.steps[id].state = "run"
        self._send("tracker:start", {"id": id})

    def progress(self, id:str, done:int, total:int):
        step = self.steps[id]
        step.done = done; step.total = total
        pct = self._calc_pct()
        self._send("tracker:progress", {
            "id": id, "done": done, "total": total, "global_pct": pct})

    def done(self, id:str):
        self.steps[id].state = "done"
        pct = self._calc_pct()
        self._send("tracker:done",   {"id": id})
        self._send("tracker:progress", {"id": id, "done": None,
                                        "total": None, "global_pct": pct})
        if pct == 100:
            self._send("tracker:finish", {"next": f"/picker/?sid={self.sid}"})

    def fail(self, id:str, exc:Exception):
        self.steps[id].state = "fail"
        self._send("tracker:error", {"id": id, "msg": str(exc)})