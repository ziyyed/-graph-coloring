#!/usr/bin/env python3
"""Calibrate and run repeatable sequential/OpenMP measurements."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / ("coloring.exe" if os.name == "nt" else "coloring")
DATA = ROOT / "data" / "generated"
RESULTS = ROOT / "results"
THREADS = (1, 2, 4, 8)
EXACT_CANDIDATES = (36, 30, 24, 20, 16, 12)


def call_solver(graph: Path, mode: str, threads: int = 1, batch: int = 1,
                timeout: float = 60.0) -> tuple[dict, float]:
    command = [str(BIN), str(graph), mode, "--threads", str(threads),
               "--repeat", "1", "--batch", str(batch)]
    start = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"Échec de {mode} sur {graph.name}")
    return json.loads(completed.stdout), elapsed


def calibrate_exact() -> list[dict]:
    candidates: list[dict] = []
    graphs = DATA / "exact"
    for n in EXACT_CANDIDATES:
        path = graphs / f"g{n}.txt"
        try:
            result, elapsed = call_solver(path, "exact-seq", timeout=60.0)
        except subprocess.TimeoutExpired:
            print(f"Calibration: G{n} dépasse 60 s, instance écartée.")
            continue
        except RuntimeError as exc:
            print(f"Calibration: G{n}: {exc}")
            continue
        if elapsed <= 60.0:
            candidates.append({
                "name": f"G{n}", "n": n, "m": result["edges"],
                "density": result["edges"] / (n * (n - 1) / 2),
                "chromatic_number": result["chromatic_number"],
                "calibration_wall_seconds": elapsed,
                "path": str(path.relative_to(ROOT)),
            })
            if len(candidates) == 4:
                break
    if len(candidates) < 4:
        raise RuntimeError("Moins de quatre instances exactes ont été résolues en 60 secondes.")
    candidates.sort(key=lambda item: item["n"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "exact_selection.json").write_text(
        json.dumps(candidates, indent=2), encoding="utf-8"
    )
    return candidates


def run_configuration(graph_info: dict, graph: Path, mode: str, threads: int,
                      batch: int, family: str) -> list[dict]:
    command = [str(BIN), str(graph), mode, "--threads", str(threads),
               "--repeat", "5", "--warmup", "1", "--batch", str(batch)]
    if mode == "exact-omp":
        command += ["--task-depth", "4"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"Échec de {mode} sur {graph.name}")
    result = json.loads(completed.stdout)
    if not result["solution_valid"]:
        raise RuntimeError(f"Coloration invalide pour {mode}, {graph.name}")
    measurements = []
    for repetition, seconds in enumerate(result["seconds"], start=1):
        measurements.append({
            "family": family,
            "graph": graph_info["name"],
            "vertices": result["vertices"],
            "edges": result["edges"],
            "density": graph_info["density"],
            "mode": mode,
            "threads": threads,
            "repetition": repetition,
            "seconds": seconds,
            "chromatic_number": result["chromatic_number"],
            "valid": result["solution_valid"],
            "batch": batch,
        })
    print(f"{family} {graph_info['name']} {mode} p={threads}: "
          f"moyenne {statistics.mean(float(row['seconds']) for row in measurements):.6f} s")
    return measurements


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str, int], list[float]] = {}
    details: dict[tuple[str, str, str, int], dict] = {}
    for row in rows:
        key = (row["family"], row["graph"], row["mode"], int(row["threads"]))
        grouped.setdefault(key, []).append(float(row["seconds"]))
        details[key] = row

    means = {key: statistics.mean(values) for key, values in grouped.items()}
    output = []
    for key, values in grouped.items():
        family, graph, mode, threads = key
        baseline_mode = "greedy-seq" if family == "greedy" else "exact-seq"
        baseline_key = (family, graph, baseline_mode, 1)
        baseline = means.get(baseline_key)
        mean = means[key]
        speedup = baseline / mean if baseline is not None and mean > 0 else None
        output.append({
            "family": family,
            "graph": graph,
            "vertices": details[key]["vertices"],
            "edges": details[key]["edges"],
            "density": details[key]["density"],
            "mode": mode,
            "threads": threads,
            "mean_seconds": mean,
            "stdev_seconds": statistics.stdev(values) if len(values) > 1 else 0.0,
            "speedup_vs_sequential": speedup,
            "efficiency": speedup / threads if speedup is not None and threads > 0 else None,
            "chromatic_number": details[key]["chromatic_number"],
        })
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError("Aucune mesure à écrire.")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-calibration", action="store_true")
    parser.add_argument("--calibrate-only", action="store_true")
    parser.add_argument("--selection", type=Path, default=RESULTS / "exact_selection.json")
    args = parser.parse_args()
    if not BIN.exists():
        raise SystemExit("Compilez d'abord avec scripts/build.ps1 ou gcc.")

    os.environ["OMP_DYNAMIC"] = "FALSE"
    os.environ["OMP_PROC_BIND"] = "close"
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.calibrate_only:
        selected = calibrate_exact()
        print(json.dumps(selected, indent=2))
        return
    if args.skip_calibration and args.selection.exists():
        exact_graphs = json.loads(args.selection.read_text(encoding="utf-8"))
    else:
        exact_graphs = calibrate_exact()

    raw_rows: list[dict] = []
    for info in exact_graphs:
        graph = ROOT / info["path"]
        for mode in ("exact-seq", "exact-omp"):
            thread_values = (1,) if mode == "exact-seq" else THREADS
            for threads in thread_values:
                batch = 10 if info["n"] <= 24 else 1
                raw_rows.extend(run_configuration(info, graph, mode, threads, batch, "exact"))

    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    for info in manifest["greedy_graphs"]:
        graph = ROOT / info["path"]
        for mode in ("greedy-seq", "greedy-omp"):
            thread_values = (1,) if mode == "greedy-seq" else THREADS
            for threads in thread_values:
                raw_rows.extend(run_configuration(info, graph, mode, threads, 1, "greedy"))

    write_csv(RESULTS / "raw_measurements.csv", raw_rows)
    write_csv(RESULTS / "performance_summary.csv", summarize(raw_rows))
    print(f"Écrit {len(raw_rows)} mesures dans results/raw_measurements.csv")


if __name__ == "__main__":
    main()
