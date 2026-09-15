# python-subinterpreters-vs-processes

PEP 734 landed `concurrent.interpreters` in Python 3.14. Each subinterpreter has its
own GIL, so unlike threads they run CPU work in parallel on a standard build. This
measures what that is worth next to multiprocessing. **2026-09-15**, Apple M2, 4 performance + 4 efficiency cores, 8 GB, macOS 26.6.2, CPython 3.14.7.

## What a worker costs

```
worker kind           cost to create    vs a thread
--------------------------------------------------------
thread                0.036 ms          1x
subinterpreter        9.177 ms          255x
process (spawn)       32.797 ms         911x

Create, run a trivial statement, tear down. 20 workers, minimum of five runs.
```

## Throughput

```
mechanism         small: 0.2s    speedup     large: 2.0s    speedup
------------------------------------------------------------------------
serial            203 ms         1.00x       2041 ms        1.00x
threads           200 ms         1.02x       2002 ms        1.02x
interpreters      63 ms          3.25x       418 ms         4.88x
processes         160 ms         1.27x       512 ms         3.98x

8 chunks of pure-Python CPU work split across 8 workers.
Nothing here releases the GIL, which is why threads do not help.
```

Subinterpreters beat processes at both sizes, and the gap widens as the task shrinks:
2.6x faster on the small task, 1.2x on the large one. A subinterpreter costs 9.2 ms to
create against a spawned process's 32.8.

## Verified, not assumed

A 4.88x speedup on a GIL build deserves a check, so wall clock was compared against CPU
time with `/usr/bin/time -l`:

```
serial        wall 2.07s  cpu 2.06s  parallelism 1.00x
threads       wall 2.02s  cpu 2.02s  parallelism 1.00x
interpreters  wall 0.52s  cpu 2.89s  parallelism 5.56x
processes     wall 0.75s  cpu 3.23s  parallelism 4.31x
```

Threads use exactly one core, which is the GIL doing its job. Subinterpreters use about
5.6, and burn less total CPU than processes for the same work.

## A note on the harness

The worker lives in a real file, not `python -c`. multiprocessing's spawn start method
re-imports the entry module in every child, and under `-c` that re-runs the whole
benchmark in each child and forks without end. The `__main__` guard in `workers/worker.py`
is what stops it. The first version of this benchmark hung for ten minutes because of it.

## Limits

- Pure-Python CPU work. Anything that releases the GIL (NumPy, compression, I/O) changes
  the threads row completely and weakens the case for both alternatives.
- 8 chunks on 8 logical cores, 4 of which are efficiency cores, so neither mechanism can
  reach 8x.
- Only work dispatch is measured. Subinterpreters have real constraints on what can cross
  between them, and a workload that needs to pass large objects around may not fit at all.
- One machine, CPython 3.14.7. `concurrent.interpreters` is new and its performance is
  likely to move.

## Reproducing

```bash
uv venv --python 3.14 .venv
.venv/bin/python bench/bench_interpreters.py
python3 bench/tables.py
```

MIT.
