#!/usr/bin/env python3
"""Black-box correctness checks for the C/OpenMP executable."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / ("coloring.exe" if os.name == "nt" else "coloring")


def invoke(graph: Path, mode: str, *args: str) -> dict:
    completed = subprocess.run(
        [str(BIN), str(graph), mode, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def write_matrix(path: Path, matrix: list[list[int]]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(f"{len(matrix)}\n")
        for row in matrix:
            stream.write("".join(str(value) for value in row) + "\n")


def cycle(n: int) -> list[list[int]]:
    matrix = [[0] * n for _ in range(n)]
    for v in range(n):
        u = (v + 1) % n
        matrix[v][u] = matrix[u][v] = 1
    return matrix


class ColoringTests(unittest.TestCase):
    def test_cycle5_greedy_variants_are_identical_and_valid(self) -> None:
        graph = ROOT / "data" / "examples" / "cycle5.txt"
        seq = invoke(graph, "greedy-seq")
        omp = invoke(graph, "greedy-omp", "--threads", "4")
        self.assertEqual(seq["colors"], omp["colors"])
        self.assertEqual(seq["chromatic_number"], 3)
        self.assertTrue(seq["solution_valid"])
        self.assertTrue(omp["solution_valid"])

    def test_known_chromatic_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cases = {
                "empty": ([], 0),
                "singleton": ([[0]], 1),
                "edgeless": ([[0, 0, 0], [0, 0, 0], [0, 0, 0]], 1),
                "triangle": ([[0, 1, 1], [1, 0, 1], [1, 1, 0]], 3),
                "odd-cycle": (cycle(5), 3),
                "complete4": ([[0 if i == j else 1 for j in range(4)] for i in range(4)], 4),
            }
            for name, (matrix, expected) in cases.items():
                graph = folder / f"{name}.txt"
                write_matrix(graph, matrix)
                for mode in ("exact-seq", "exact-omp"):
                    result = invoke(graph, mode, "--threads", "4")
                    self.assertEqual(result["chromatic_number"], expected, (name, mode))
                    self.assertTrue(result["solution_valid"], (name, mode))

    def test_decision_matches_expected_threshold(self) -> None:
        graph = ROOT / "data" / "examples" / "cycle5.txt"
        for mode in ("exact-seq", "exact-omp"):
            self.assertFalse(invoke(graph, mode, "--k", "2")["colorable"])
            self.assertTrue(invoke(graph, mode, "--k", "3")["colorable"])

    def test_disconnected_graph_and_parallel_exact_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            graph = Path(temp) / "disconnected.txt"
            matrix = [[0] * 6 for _ in range(6)]
            for u, v in ((0, 1), (1, 2), (2, 0), (3, 4)):
                matrix[u][v] = matrix[v][u] = 1
            write_matrix(graph, matrix)
            seq = invoke(graph, "exact-seq")
            omp = invoke(graph, "exact-omp", "--threads", "4")
            self.assertEqual(seq["chromatic_number"], 3)
            self.assertEqual(seq["chromatic_number"], omp["chromatic_number"])
            self.assertTrue(omp["solution_valid"])

    def test_malformed_matrices_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cases = {
                "asymmetric.txt": "2\n01\n00\n",
                "loop.txt": "1\n1\n",
                "invalid.txt": "2\n0x\n00\n",
                "extra.txt": "1\n0\n1\n",
            }
            for name, content in cases.items():
                graph = folder / name
                graph.write_text(content, encoding="ascii")
                completed = subprocess.run(
                    [str(BIN), str(graph), "greedy-seq"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertNotEqual(completed.returncode, 0, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
