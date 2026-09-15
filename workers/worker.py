"""CPU work run under four concurrency mechanisms.

This lives in a real file, not `python -c`, because multiprocessing's spawn start
method re-imports the entry module in every child. Under `-c` that re-executes
the whole benchmark in each child and the run forks forever. The __main__ guard
below is what stops that.
"""
from __future__ import annotations
import json, sys, threading, time

CHUNKS = int(sys.argv[2])
SIZE = int(sys.argv[3])

WORKER_SRC = """
def burn(n):
    total = 0
    for i in range(2, n):
        if i %% 3 and i %% 5 and i %% 7:
            total += i * i %% 1000003
    return total
burn(%d)
"""


def burn(n: int) -> int:
    total = 0
    for i in range(2, n):
        if i % 3 and i % 5 and i % 7:
            total += i * i % 1000003
    return total


def serial():
    for _ in range(CHUNKS):
        burn(SIZE)


def threads():
    ts = [threading.Thread(target=burn, args=(SIZE,)) for _ in range(CHUNKS)]
    for t in ts: t.start()
    for t in ts: t.join()


def interpreters():
    import concurrent.interpreters as ci
    src = WORKER_SRC % SIZE

    def one():
        i = ci.create()
        try:
            i.exec(src)
        finally:
            i.close()

    ts = [threading.Thread(target=one) for _ in range(CHUNKS)]
    for t in ts: t.start()
    for t in ts: t.join()


def processes():
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    with ctx.Pool(CHUNKS) as pool:
        pool.map(burn, [SIZE] * CHUNKS)


if __name__ == "__main__":
    fn = {"serial": serial, "threads": threads,
          "interpreters": interpreters, "processes": processes}[sys.argv[1]]
    t0 = time.perf_counter()
    fn()
    print(json.dumps({"ms": (time.perf_counter() - t0) * 1000}))
