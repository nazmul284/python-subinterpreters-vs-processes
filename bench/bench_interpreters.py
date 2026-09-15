"""Subinterpreters (PEP 734) against threads and processes for CPU-bound work.

Python 3.14 ships `concurrent.interpreters`. Each subinterpreter has its own GIL,
so unlike threads they genuinely run CPU work in parallel on a standard build.
The question is what that costs next to multiprocessing, which has done the same
job for fifteen years.

Two things are measured separately, because they pull in opposite directions:
  startup    - what one worker costs to create and tear down
  throughput - wall clock for a fixed amount of CPU work split across workers
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
PY_ = str(ROOT / ".venv" / "bin" / "python")
REPS = 5
CHUNKS = 8
SIZES = [400_000, 4_000_000]   # startup-dominated, then throughput-dominated
SIZE = 4_000_000

# Pure-Python CPU work: nothing here releases the GIL, which is the whole point.
WORK = """
def burn(n):
    total = 0
    for i in range(2, n):
        if i % 3 and i % 5 and i % 7:
            total += i * i % 1000003
    return total
"""

STARTUP = WORK + """
import json, sys, time
MODE, N = sys.argv[1], 20
if MODE == "thread":
    import threading
    t0 = time.perf_counter()
    for _ in range(N):
        t = threading.Thread(target=int); t.start(); t.join()
elif MODE == "interpreter":
    import concurrent.interpreters as ci
    t0 = time.perf_counter()
    for _ in range(N):
        i = ci.create(); i.exec("pass"); i.close()
else:
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    t0 = time.perf_counter()
    for _ in range(N):
        p = ctx.Process(target=int); p.start(); p.join()
print(json.dumps({"per_worker_ms": (time.perf_counter() - t0) / N * 1000}))
"""



def run_worker(mode: str, size: int = None, timeout: int = 1800):
    """Run the worker as a FILE. Under `python -c`, spawn re-executes the whole
    driver in every child and the run forks without end."""
    p = subprocess.run([PY_, str(ROOT / "workers" / "worker.py"), mode,
                        str(CHUNKS), str(size or SIZE)],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:170]
    return json.loads(p.stdout.strip().splitlines()[-1]), None


def run(src, *args, timeout=1200):
    p = subprocess.run([PY_, "-c", src, *args], capture_output=True,
                       text=True, timeout=timeout)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:170]
    return json.loads(p.stdout.strip().splitlines()[-1]), None


def main():
    out = {"startup": [], "throughput": []}
    for mode in ("thread", "interpreter", "process"):
        s, err = [], None
        for _ in range(REPS):
            d, err = run(STARTUP, mode)
            if d is None: break
            s.append(d["per_worker_ms"])
        if not s:
            out["startup"].append({"mode": mode, "error": err})
            print(f"  startup {mode:12} FAILED {err}"); continue
        out["startup"].append({"mode": mode, "per_worker_ms": round(min(s), 3)})
        print(f"  startup {mode:12} {min(s):8.3f} ms per worker", flush=True)

    for size in SIZES:
        for mode in ("serial", "threads", "interpreters", "processes"):
            s, err = [], None
            for _ in range(REPS):
                d, err = run_worker(mode, size)
                if d is None: break
                s.append(d["ms"])
            if not s:
                out["throughput"].append({"mode": mode, "size": size, "error": err})
                print(f"  work {size:>9} {mode:13} FAILED {err}"); continue
            out["throughput"].append({"mode": mode, "chunks": CHUNKS, "size": size,
                                      "min_ms": round(min(s), 1),
                                      "median_ms": round(statistics.median(s), 1)})
            print(f"  work {size:>9} {mode:13} {min(s):9.1f} ms", flush=True)
        base = next((r["min_ms"] for r in out["throughput"]
                     if r.get("mode") == "serial" and r.get("size") == size), None)
        if base:
            for r in out["throughput"]:
                if r.get("size") == size and "min_ms" in r:
                    r["speedup_vs_serial"] = round(base / r["min_ms"], 2)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "interpreters.json").write_text(json.dumps(
        {"reps": REPS, "chunks": CHUNKS, "sizes": SIZES,
         "cpu": "Apple M2, 4 performance + 4 efficiency cores", **out}, indent=2))
    print("\nwrote results/interpreters.json")


if __name__ == "__main__":
    main()
