"""Render the article/README tables from the result JSON."""
from __future__ import annotations
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent / "results"
D = json.loads((R / "interpreters.json").read_text())
TH = {(r["mode"], r["size"]): r for r in D["throughput"] if "min_ms" in r}
ST = {r["mode"]: r for r in D["startup"] if "per_worker_ms" in r}
SIZES = D["sizes"]
MODES = ["serial", "threads", "interpreters", "processes"]

def row(c, w): return "".join(str(x).ljust(n) for x, n in zip(c, w)).rstrip()
def rule(w):   return "-" * sum(w)

def startup() -> str:
    w = [22, 18, 16]
    base = ST["thread"]["per_worker_ms"]
    out = [row(["worker kind","cost to create","vs a thread"], w), rule(w)]
    for m, lab in (("thread","thread"),("interpreter","subinterpreter"),
                   ("process","process (spawn)")):
        v = ST[m]["per_worker_ms"]
        out.append(row([lab, f"{v:.3f} ms", f"{v/base:.0f}x"], w))
    out += ["", "Create, run a trivial statement, tear down. 20 workers, "
            "minimum of five runs."]
    return "\n".join(out)

def throughput() -> str:
    w = [18, 15, 12, 15, 12]
    out = [row(["mechanism","small: 0.2s","speedup","large: 2.0s","speedup"], w), rule(w)]
    for m in MODES:
        cells = []
        for sz in SIZES:
            r = TH[(m, sz)]
            cells += [f"{r['min_ms']:.0f} ms", f"{r['speedup_vs_serial']:.2f}x"]
        out.append(row([m] + cells, w))
    out += ["", "8 chunks of pure-Python CPU work split across 8 workers.",
            "Nothing here releases the GIL, which is why threads do not help."]
    return "\n".join(out)

if __name__ == "__main__":
    print("===== STARTUP =====\n" + startup())
    print("\n===== THROUGHPUT =====\n" + throughput())
