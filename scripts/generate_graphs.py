#!/usr/bin/env python3
"""Generate reproducible adjacency-matrix families for the project."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "generated"
SEED_EXACT = 20261108
SEED_GREEDY = 20261109


def random_symmetric_matrix(n: int, density: float, seed: int) -> list[bytearray]:
    rng = random.Random(seed)
    matrix = [bytearray(n) for _ in range(n)]
    threshold = int(density * (1 << 20))
    for i in range(n):
        row = matrix[i]
        for j in range(i + 1, n):
            if rng.getrandbits(20) < threshold:
                row[j] = 1
                matrix[j][i] = 1
    return matrix


def edge_count(matrix: list[bytearray]) -> int:
    return sum(sum(row[i + 1 :]) for i, row in enumerate(matrix))


def write_graph(path: Path, matrix: list[bytearray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(f"{len(matrix)}\n".encode("ascii"))
        translation = bytes.maketrans(b"\x00\x01", b"01")
        for row in matrix:
            stream.write(bytes(row).translate(translation) + b"\n")


def write_prefixes(max_n: int, sizes: list[int], density: float, seed: int, folder: Path) -> list[dict]:
    base = random_symmetric_matrix(max_n, density, seed)
    entries = []
    for n in sizes:
        if n > max_n:
            raise ValueError(f"La taille {n} dépasse max_n={max_n}.")
        prefix = [row[:n] for row in base[:n]]
        path = folder / f"g{n}.txt"
        write_graph(path, prefix)
        edges = edge_count(prefix)
        entries.append({
            "name": f"G{n}",
            "n": n,
            "m": edges,
            "density": edges / (n * (n - 1) / 2) if n > 1 else 0.0,
            "seed": seed,
            "path": str(path.relative_to(ROOT)),
        })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output.resolve()

    exact = write_prefixes(
        max_n=36,
        sizes=[12, 16, 20, 24, 30, 36],
        density=0.45,
        seed=SEED_EXACT,
        folder=out / "exact",
    )
    greedy = write_prefixes(
        max_n=12000,
        sizes=[1000, 2000, 4000, 8000, 12000],
        density=0.10,
        seed=SEED_GREEDY,
        folder=out / "greedy",
    )
    manifest = {
        "generator": "Python random.Random, fixed seeds, symmetric Erdős–Rényi prefixes",
        "exact_seed": SEED_EXACT,
        "exact_target_density": 0.45,
        "exact_graphs": exact,
        "greedy_seed": SEED_GREEDY,
        "greedy_target_density": 0.10,
        "greedy_graphs": greedy,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
