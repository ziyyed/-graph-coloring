#!/usr/bin/env python3
"""Create report-ready performance charts and the separate OpenMP Gantt view."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "performance_summary.csv"
FIGURES = ROOT / "results" / "figures"
GRAPH_COLORS = ["#007F86", "#D77A46", "#5A9B75", "#8B6AAE", "#C14953", "#4D7C8A"]
IDEAL = "#263648"


def load_summary() -> list[dict]:
    with SUMMARY.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def thread_points(rows: list[dict], family: str, graph: str, field: str) -> list[tuple[float, float]]:
    """Return the sequential baseline at x=0, followed by OpenMP p=1,2,4,8."""
    sequential_mode = "greedy-seq" if family == "greedy" else "exact-seq"
    openmp_mode = "greedy-omp" if family == "greedy" else "exact-omp"
    points: list[tuple[float, float]] = []
    for row in rows:
        if row["family"] == family and row["graph"] == graph and row["mode"] == sequential_mode:
            if row[field] not in ("", "None"):
                points.append((0.0, float(row[field])))
            break
    points.extend(
        (float(row["threads"]), float(row[field]))
        for row in rows
        if row["family"] == family and row["graph"] == graph and row["mode"] == openmp_mode
        and row[field] not in ("", "None")
    )
    return sorted(points)


def plot_thread_curves(rows: list[dict], family: str, field: str, ylabel: str, filename: str) -> None:
    graph_names = sorted({row["graph"] for row in rows if row["family"] == family})
    fig, ax = plt.subplots(figsize=(8.5, 4.9), constrained_layout=True)
    for graph_index, graph in enumerate(graph_names):
        points = thread_points(rows, family, graph, field)
        if points:
            ax.plot([x for x, _ in points], [y for _, y in points], marker="o", linewidth=2,
                    color=GRAPH_COLORS[graph_index % len(GRAPH_COLORS)], label=graph)
    if field == "speedup_vs_sequential":
        ax.plot([1, 2, 4, 8], [1, 2, 4, 8], linestyle="--", color="#626C77",
                linewidth=1.4, label="Accélération idéale")
    if field == "mean_seconds":
        ax.set_yscale("log")
    ax.set_xlabel("Configuration (Séq. ou nombre de threads p)")
    ax.set_ylabel(ylabel)
    ax.set_xticks([0, 1, 2, 4, 8], ["Séq.", "1", "2", "4", "8"])
    ax.set_xlim(-0.35, 8.4)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))
    ax.grid(axis="y", color="#DDE3E8", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    fig.subplots_adjust(bottom=0.24)
    fig.savefig(FIGURES / filename, dpi=180)
    plt.close(fig)


def plot_size_curve(rows: list[dict], family: str) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.9), constrained_layout=True)
    series = (
        (("greedy-seq", 1), "Glouton séquentiel", IDEAL),
        (("greedy-omp", 4), "Glouton OpenMP, 4 threads", GRAPH_COLORS[0]),
    ) if family == "greedy" else (
        (("exact-seq", 1), "Backtracking séquentiel", IDEAL),
        (("exact-omp", 4), "Backtracking OpenMP, 4 threads", GRAPH_COLORS[1]),
    )
    for (mode, thread_count), label, color in series:
        points = [row for row in rows if row["family"] == family and row["mode"] == mode and int(row["threads"]) == thread_count]
        if not points:
            continue
        points.sort(key=lambda row: int(row["vertices"]))
        ax.plot([int(row["vertices"]) for row in points],
                [float(row["mean_seconds"]) for row in points],
                marker="o", linewidth=2, color=color, label=label)
    ax.set_xlabel("Taille du graphe n = |V|")
    ax.set_ylabel("Temps d'exécution moyen (secondes)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))
    ax.grid(axis="both", color="#DDE3E8", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.savefig(FIGURES / f"taille_{family}.png", dpi=180)
    plt.close(fig)


def plot_gantt(path: Path, output: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    if not events:
        raise RuntimeError("Aucun événement Gantt à représenter.")
    by_thread: dict[int, list[dict]] = {}
    for event in events:
        by_thread.setdefault(int(event["thread_id"]), []).append(event)
    fig, ax = plt.subplots(figsize=(9.2, 4.5), constrained_layout=True)
    total_end = max(float(event["end_s"]) for event in events)
    for thread, thread_events in sorted(by_thread.items()):
        # Le fond gris montre les périodes sans tâche feuille journalisée sur ce thread.
        ax.barh(thread, total_end, left=0, height=0.66,
                color="#E7ECEF", edgecolor="none", zorder=0)
        for event in thread_events:
            start = float(event["start_s"])
            duration = float(event["duration_s"])
            ax.barh(thread, duration, left=start, height=0.52,
                    color="#007F86", edgecolor="white", linewidth=0.7, zorder=2)
            if duration > 0:
                ax.text(start + duration / 2, thread, f"T{event['task_id']}",
                        ha="center", va="center", color="white", fontsize=7)
    ax.set_xlim(0, total_end if total_end > 0 else 1)
    ax.set_yticks(sorted(by_thread))
    ax.set_yticklabels([f"Thread {thread}" for thread in sorted(by_thread)])
    ax.set_xlabel("Temps depuis le début du traçage (secondes)")
    ax.set_ylabel("Thread OpenMP")
    thread_count = len(by_thread)
    ax.set_title(f"G36, K=6 — {thread_count} threads, tâches feuilles de profondeur 2")
    ticks = [index * 0.5 for index in range(int(total_end / 0.5) + 1)]
    if not ticks or total_end - ticks[-1] > 0.05:
        ticks.append(total_end)
    labels = [f"{value:.1f}".replace(".", ",") for value in ticks]
    if ticks and ticks[-1] == total_end:
        labels[-1] = f"{total_end:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    ax.set_xticks(ticks, labels)
    ax.grid(axis="x", color="#DDE3E8", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(handles=[
        Patch(facecolor="#007F86", label="Tâche feuille exécutée"),
        Patch(facecolor="#E7ECEF", label="Aucune tâche feuille journalisée"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.19), ncol=2, frameon=False, fontsize=8)
    fig.subplots_adjust(bottom=0.24)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_backtracking_tree() -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.1), constrained_layout=True)
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(7.0, 0.0)
    ax.axis("off")
    teal, orange, red, ink = "#007F86", "#D77A46", "#C14953", "#263648"
    root = (0.0, 0.55)
    ax.add_patch(FancyBboxPatch((-0.48, 0.25), 0.96, 0.58,
                                boxstyle="round,pad=0.05", facecolor=ink, edgecolor="white"))
    ax.text(*root, "∅", ha="center", va="center", color="white", fontsize=12, weight="bold")

    paths = [
        (-2.35, ["v₁ = 1", "v₂ = 2", "v₃ = 1", "v₄ = 2"], [teal, orange, teal, orange], [1, 2, 1, 2]),
        (2.35, ["v₁ = 2", "v₂ = 1", "v₃ = 2", "v₄ = 1"], [orange, teal, orange, teal], [2, 1, 2, 1]),
    ]
    ys = [1.55, 2.55, 3.55, 4.55, 5.8]
    for x, labels, colors, choices in paths:
        previous = root
        for index, (label, fill, choice) in enumerate(zip(labels, colors, choices)):
            y = ys[index]
            ax.annotate("", xy=(x, y - 0.28), xytext=previous,
                        arrowprops={"arrowstyle": "-", "color": "#87929C", "lw": 1.5})
            ax.text((previous[0] + x) / 2 + (0.24 if x > 0 else -0.24),
                    (previous[1] + y - 0.28) / 2,
                    f"c={choice}", ha="center", va="center", color=ink, fontsize=8)
            ax.add_patch(FancyBboxPatch((x - 0.74, y - 0.28), 1.48, 0.56,
                                        boxstyle="round,pad=0.05", facecolor=fill, edgecolor="white"))
            ax.text(x, y, label, ha="center", va="center", color="white", fontsize=9, weight="bold")
            previous = (x, y + 0.28)
        leaf_y = ys[-1]
        ax.annotate("", xy=(x, leaf_y - 0.42), xytext=previous,
                    arrowprops={"arrowstyle": "-", "color": "#87929C", "lw": 1.5})
        ax.add_patch(FancyBboxPatch((x - 1.32, leaf_y - 0.42), 2.64, 0.88,
                                    boxstyle="round,pad=0.05", facecolor="#FBEAEC", edgecolor=red, linewidth=1.3))
        ax.text(x, leaf_y + 0.02, "Impasse : v₅ adjacent à v₁ et v₄\n1 et 2 sont interdites",
                ha="center", va="center", color=red, fontsize=8.3, weight="bold")
    ax.set_title("Arbre de recherche réduit pour C₅ avec K = 2", color=ink, fontsize=13, pad=8)
    fig.text(0.5, 0.015,
             "Nœud : affectation partielle · branche : choix d’une couleur · feuille : solution complète ou impasse",
             ha="center", color=ink, fontsize=8.5)
    fig.savefig(FIGURES / "arbre_backtracking_c5_k2.png", dpi=190, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gantt-two", type=Path, default=ROOT / "results" / "gantt_2threads.csv")
    parser.add_argument("--gantt-four", type=Path, default=ROOT / "results" / "gantt_4threads.csv")
    args = parser.parse_args()
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = load_summary()
    for family in ("greedy", "exact"):
        plot_thread_curves(rows, family, "mean_seconds", "Temps d'exécution moyen (secondes)", f"temps_threads_{family}.png")
        plot_thread_curves(rows, family, "speedup_vs_sequential", "Accélération S(p) = T_s / T_p", f"speedup_{family}.png")
        plot_thread_curves(rows, family, "efficiency", "Efficacité E(p) = S(p) / p", f"efficacite_{family}.png")
        plot_size_curve(rows, family)
    plot_backtracking_tree()
    if args.gantt_two.exists():
        plot_gantt(args.gantt_two, FIGURES / "gantt_2threads.png")
    if args.gantt_four.exists():
        plot_gantt(args.gantt_four, FIGURES / "gantt_4threads.png")
    print(f"Graphiques écrits dans {FIGURES}")


if __name__ == "__main__":
    main()
