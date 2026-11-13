#!/usr/bin/env python3
"""Build the French project report from the reproducible measurements."""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
OUT = ROOT / "rapport_coloriage_graphes.docx"
PALETTE = {1: "#0B7A75", 2: "#D77A46", 3: "#5A9B75", 4: "#8B6AAE", 5: "#C14953", 6: "#4D7C8A"}
TABLE_NUMBER = 0


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "5")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "D9D9D9")


def style_table(table, header=True) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    set_table_borders(table)
    for row_index, row in enumerate(table.rows):
        if row_index == 0 and header:
            tr_pr = row._tr.get_or_add_trPr()
            repeat = OxmlElement("w:tblHeader")
            repeat.set(qn("w:val"), "true")
            tr_pr.append(repeat)
        for cell in row.cells:
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.space_before = Pt(2)
                for run in paragraph.runs:
                    run.font.name = "Aptos"
                    run.font.size = Pt(8.5)
            if row_index == 0 and header:
                set_cell_shading(cell, "263648")
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.color.rgb = RGBColor(255, 255, 255)
                        run.bold = True
            elif row_index % 2 == 0:
                set_cell_shading(cell, "F2F6F8")


def add_table(doc: Document, headers: list[str], rows: list[list[str]], caption: str, widths=None):
    global TABLE_NUMBER
    TABLE_NUMBER += 1
    caption_paragraph = doc.add_paragraph()
    caption_paragraph.paragraph_format.keep_with_next = True
    caption_paragraph.paragraph_format.space_before = Pt(8)
    caption_paragraph.paragraph_format.space_after = Pt(3)
    caption_run = caption_paragraph.add_run(f"Tableau {TABLE_NUMBER} : {caption}")
    caption_run.bold = True
    caption_run.font.size = Pt(9)
    caption_run.font.color.rgb = RGBColor(38, 54, 72)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = value
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = str(value)
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Cm(width)
    style_table(table)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(9)
    p.paragraph_format.keep_together = True
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(80, 90, 100)


def add_color_legend(doc: Document, entries: list[tuple[int, str]]) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.keep_with_next = True
    for index, (color_number, label) in enumerate(entries):
        if index:
            paragraph.add_run("     ")
        swatch = paragraph.add_run("■ ")
        swatch.font.name = "Arial"
        swatch.font.size = Pt(10)
        swatch.font.color.rgb = RGBColor.from_string(PALETTE[color_number].lstrip("#"))
        run = paragraph.add_run(label)
        run.font.size = Pt(8.5)


def add_figure(doc: Document, path: Path, caption: str, width=6.1, legend=None) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    if legend:
        add_color_legend(doc, legend)
    add_caption(doc, caption)


def add_code_block(doc: Document, text: str, size=8.5) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.keep_together = True
    paragraph.paragraph_format.space_after = Pt(7)
    run = paragraph.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(size)


def add_table_of_contents(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("Table des matières", level=1)
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = ' TOC \\o "1-3" \\h \\z \\u '
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "Actualiser la table des matières dans Word si elle ne s'affiche pas."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, placeholder, end])
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    doc.settings.element.append(update_fields)
    doc.add_page_break()


def format_seconds(value: float) -> str:
    if value < 0.001:
        return f"{value * 1_000_000:.1f}".replace(".", ",") + " µs"
    if value < 1:
        return f"{value * 1000:.2f}".replace(".", ",") + " ms"
    return f"{value:.3f}".replace(".", ",") + " s"


def format_decimal(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def format_mean_and_stdev(row: dict) -> str:
    mean = float(row.get("mean_seconds", 0) or 0)
    stdev = float(row.get("stdev_seconds", 0) or 0)
    return f"{format_seconds(mean)} ± {format_seconds(stdev)}"


def rows_for_graph(summary: list[dict], graph: str) -> dict[tuple[str, int], dict]:
    return {(row["mode"], int(row["threads"])): row for row in summary if row["graph"] == graph}


def add_performance_table(doc: Document, summary: list[dict], family: str) -> None:
    subset = [row for row in summary if row["family"] == family]
    names = sorted({row["graph"] for row in subset}, key=lambda name: int("".join(ch for ch in name if ch.isdigit())))
    rows = []
    for name in names:
        by_key = rows_for_graph(subset, name)
        mode_seq = "greedy-seq" if family == "greedy" else "exact-seq"
        mode_omp = "greedy-omp" if family == "greedy" else "exact-omp"
        seq = by_key.get((mode_seq, 1), {})
        quality = str(seq.get("chromatic_number", ""))
        rows.append([name, str(seq.get("vertices", "")), "Séquentiel", format_mean_and_stdev(seq), "1,00", "1,00", quality])
        for p in (1, 2, 4, 8):
            row = by_key.get((mode_omp, p), {})
            if row:
                config = f"OpenMP, p={p}"
                time_text = format_mean_and_stdev(row)
                s_text = format_decimal(float(row["speedup_vs_sequential"]))
                e_text = format_decimal(float(row["efficiency"]))
            else:
                config, time_text, s_text, e_text = f"OpenMP, p={p}", "n. m.", "n. m.", "n. m."
            rows.append([name, str(seq.get("vertices", "")), config, time_text, s_text, e_text, quality])
    quality_label = "K_glouton" if family == "greedy" else "χ(G)"
    title = ("Temps, speedup et efficacité du glouton (moyenne ± écart-type sur 5 mesures)"
             if family == "greedy" else
             "Temps, speedup et efficacité du backtracking exact (moyenne ± écart-type sur 5 mesures)")
    add_table(doc,
        ["Graphe", "n", "Configuration", "Temps moyen ± σ", "S(p)", "E(p)", quality_label],
        rows,
        caption=title,
        widths=[1.7, 0.8, 2.4, 3.4, 1.2, 1.2, 1.6])


def add_summary_text(doc: Document, summary: list[dict], family: str) -> None:
    mode_seq = "greedy-seq" if family == "greedy" else "exact-seq"
    mode_omp = "greedy-omp" if family == "greedy" else "exact-omp"
    subset = [row for row in summary if row["family"] == family]
    largest = max(subset, key=lambda row: int(row["vertices"]))
    n = largest["graph"]
    by_key = rows_for_graph(subset, n)
    base = float(by_key[(mode_seq, 1)]["mean_seconds"])
    speedups = []
    for p in (2, 4, 8):
        row = by_key.get((mode_omp, p))
        if row:
            speedups.append(f"p={p} : S={format_decimal(float(row['speedup_vs_sequential']))}, E={format_decimal(float(row['efficiency']))}")
    detail = "; ".join(speedups) if speedups else "aucune configuration parallèle mesurée"
    if family == "greedy":
        conclusion = (f"Sur {n}, le glouton séquentiel prend {format_seconds(base)}. "
                      f"Les accélérations et efficacités calculées sont {detail}. "
                      "Le tableau partagé des couleurs interdites impose des opérations atomiques et des barrières à chaque sommet.")
    else:
        best = max(subset, key=lambda row: float(row["speedup_vs_sequential"]))
        conclusion = (f"Sur {n}, le solveur exact séquentiel prend {format_seconds(base)}. "
                      f"Les accélérations et efficacités calculées sont {detail}. "
                      f"Le meilleur speedup observé est {format_decimal(float(best['speedup_vs_sequential']))} sur {best['graph']} avec {best['threads']} threads. "
                      "Le travail varie selon les préfixes et le drapeau d'arrêt peut laisser certaines tâches sans travail utile.")
    doc.add_paragraph(conclusion)


def build_report() -> None:
    global TABLE_NUMBER
    TABLE_NUMBER = 0
    summary = read_csv(RESULTS / "performance_summary.csv")
    raw = read_csv(RESULTS / "raw_measurements.csv")
    exact_selection = json.loads((RESULTS / "exact_selection.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "data" / "generated" / "manifest.json").read_text(encoding="utf-8"))

    FIGURES.mkdir(parents=True, exist_ok=True)
    slide_dir = RESULTS / "slides"
    required_slides = [3, 10]
    missing = [n for n in required_slides if not (slide_dir / f"slide-{n:02d}.png").exists()]
    if missing:
        raise RuntimeError("Les diapositives doivent d'abord être exportées : " + ", ".join(map(str, missing)))

    def crop_slide(slide_number: int, name: str, box: tuple[int, int, int, int]) -> None:
        source = slide_dir / f"slide-{slide_number:02d}.png"
        with Image.open(source) as image:
            image.crop(box).save(FIGURES / name)

    crop_slide(3, "cycle5_colore.png", (520, 145, 1215, 670))
    crop_slide(10, "exam_schedule.png", (72, 145, 725, 640))
    required_figures = [
        "arbre_backtracking_c5_k2.png", "temps_threads_greedy.png", "speedup_greedy.png",
        "efficacite_greedy.png", "temps_threads_exact.png", "speedup_exact.png",
        "efficacite_exact.png", "taille_greedy.png", "taille_exact.png",
        "gantt_2threads.png", "gantt_4threads.png",
    ]
    missing_figures = [name for name in required_figures if not (FIGURES / name).exists()]
    if missing_figures:
        raise RuntimeError("Générez d'abord les figures : " + ", ".join(missing_figures))

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.8)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(34, 43, 52)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.12
    for style_name, size in (("Title", 25), ("Heading 1", 17), ("Heading 2", 13), ("Heading 3", 11)):
        style = doc.styles[style_name]
        style.font.name = "Aptos Display" if style_name != "Heading 3" else "Aptos"
        style.font.size = Pt(size)
        style.font.bold = style_name != "Title"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(13 if style_name != "Title" else 0)
        style.paragraph_format.space_after = Pt(6)

    # Built-in Word Title styles can carry a default blue bottom border.
    # Remove style and direct paragraph borders so the title remains plain black text.
    title_ppr = doc.styles["Title"]._element.find(qn("w:pPr"))
    if title_ppr is not None:
        title_border = title_ppr.find(qn("w:pBdr"))
        if title_border is not None:
            title_ppr.remove(title_border)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Coloriage de graphes  |  ")
    add_page_field(footer)

    institution = doc.add_paragraph()
    institution.alignment = WD_ALIGN_PARAGRAPH.CENTER
    institution.paragraph_format.space_before = Pt(64)
    institution.add_run("Institut Supérieur d'Informatique de Mahdia (ISI Mahdia)").bold = True
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(30)
    title_ppr = title._p.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    title.add_run("Le coloriage de graphes")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Étude algorithmique et parallélisation OpenMP")
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(50, 64, 78)
    doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(
        "Complexité algorithmique  |  Calcul parallèle et distribué\n\n"
        "Étudiants : Zied Chouk, Chayma Hakouna et Wirak\n\n"
        "Année universitaire : 2026-2027\nMahdia, le 9 novembre 2026\n\n"
        "Implémentation en C11 et OpenMP"
    )
    doc.add_page_break()

    doc.add_heading("Résumé", level=1)
    doc.add_paragraph(
        "Ce rapport étudie le coloriage propre d'un graphe non orienté et compare une heuristique gloutonne à une recherche exacte par retour sur trace. "
        "Les deux méthodes sont implémentées en C, avec une version OpenMP de l'examen des voisins pour le glouton et une exploration par tâches pour le backtracking. "
        "Les mesures combinent des instances exactes denses de taille modérée et de grandes matrices pour le glouton. Les résultats montrent la différence entre trouver rapidement une coloration valide et certifier le nombre chromatique."
    )
    add_table_of_contents(doc)
    doc.add_heading("1. Problème et notions", level=1)
    doc.add_paragraph(
        "Un graphe non orienté G=(V,E) représente des objets par ses sommets V et leurs incompatibilités par ses arêtes E. "
        "Deux sommets reliés sont adjacents. Un coloriage propre associe une couleur à chaque sommet sans attribuer la même couleur aux extrémités d'une arête. "
        "Un coloriage valide respecte ces contraintes ; un coloriage optimal utilise le nombre minimum de couleurs, appelé nombre chromatique χ(G)."
    )
    doc.add_paragraph(
        "Le problème de décision demande si G peut être colorié avec au plus K couleurs. Pour K≥3, cette décision est NP-complète. "
        "La recherche de χ(G) est donc difficile en général : le nombre de combinaisons possibles augmente rapidement avec le nombre de sommets. "
        "Un graphe complet à n sommets a un degré n−1 à chaque sommet et requiert n couleurs."
    )

    doc.add_heading("2. Objectifs et organisation de l'étude", level=1)
    doc.add_paragraph(
        "Le projet compare une heuristique qui construit vite une coloration valide à une recherche exacte qui certifie le nombre chromatique. "
        "Chaque version séquentielle est confrontée à une variante OpenMP. Le rapport présente d'abord un exemple théorique court, puis une application réelle distincte, avant les algorithmes, l'analyse de complexité et les mesures."
    )
    doc.add_heading("2.1 Démarche de résolution", level=2)
    resolution_steps = [
        "Modéliser la situation par un graphe non orienté.",
        "Identifier les sommets, les incompatibilités et les couleurs interprétées comme ressources ou créneaux.",
        "Choisir une méthode gloutonne pour obtenir rapidement une solution, puis une méthode exacte pour certifier le minimum.",
        "Appliquer chaque méthode au graphe étudié dans un ordre de sommets explicite.",
        "Vérifier la validité en contrôlant chaque arête et les couleurs de ses extrémités.",
        "Évaluer le nombre de couleurs et le comparer à la borne gloutonne ou au nombre chromatique connu.",
        "Discuter la qualité de la solution, les coûts de calcul et les limites du modèle.",
    ]
    for step in resolution_steps:
        doc.add_paragraph(step, style="List Number")

    doc.add_heading("3. Exemple théorique : cycle à cinq sommets", level=1)
    doc.add_paragraph("Le graphe C₅ possède V={v₁,…,v₅} et E={(v₁,v₂),(v₂,v₃),(v₃,v₄),(v₄,v₅),(v₅,v₁)}.")
    add_figure(doc, FIGURES / "cycle5_colore.png", "Figure 1. Coloration gloutonne de C₅ dans l'ordre v₁, v₂, v₃, v₄, v₅.", 4.7,
               legend=[(1, "Couleur 1"), (2, "Couleur 2"), (3, "Couleur 3")])
    add_table(doc, ["Sommet", "Couleurs déjà interdites", "Couleur choisie"], [
        ["v₁", "aucune", "1"], ["v₂", "1", "2"], ["v₃", "2", "1"],
        ["v₄", "1", "2"], ["v₅", "1 et 2", "3"],
    ], caption="Trace de l'algorithme glouton sur C₅")
    doc.add_paragraph(
        "Cette coloration utilise trois couleurs. Elle est optimale : un cycle impair n'est pas biparti, donc deux couleurs ne suffisent pas ; la figure fournit une coloration valide à trois couleurs. Ainsi χ(C₅)=3."
    )
    doc.add_paragraph(
        "La version exacte teste K=1, puis K=2. Les deux recherches échouent ; la borne supérieure gloutonne vaut 3 et fournit déjà une coloration valide. Le solveur conclut donc que le minimum est 3."
    )

    doc.add_heading("4. Application réelle : emploi du temps des examens", level=1)
    doc.add_paragraph(
        "Chaque examen est un sommet. Une arête relie deux examens qui partagent au moins un étudiant et ne peuvent donc pas se tenir au même créneau. Une couleur représente un créneau horaire."
    )
    doc.add_paragraph(
        "Pour l'exemple, V={Algo, BD, Syst, Maths, Réseau, IA}. Les sept arêtes de conflit sont "
        "E={(Algo,BD), (Algo,Syst), (BD,Syst), (BD,Maths), (Syst,Réseau), (Maths,IA), (Réseau,IA)}. "
        "Les abréviations désignent Algorithmique, Bases de données, Systèmes d'exploitation, Mathématiques, Réseaux et Intelligence artificielle."
    )
    add_figure(doc, FIGURES / "exam_schedule.png", "Figure 2. Exemple de conflits entre six examens et attribution de trois créneaux.", 5.7,
               legend=[(1, "Créneau 1"), (2, "Créneau 2"), (3, "Créneau 3")])
    doc.add_paragraph(
        "Le petit exemple comporte sept conflits. La coloration produite attribue le créneau 1 à Algorithmique, Mathématiques et Réseaux ; le créneau 2 à Bases de données et Intelligence artificielle ; le créneau 3 à Systèmes d'exploitation. "
        "Aucun examen en conflit ne partage un créneau. La modélisation suppose que les conflits sont connus et que les salles ou capacités ne limitent pas le nombre d'examens simultanés."
    )

    doc.add_heading("5. Méthodes de résolution", level=1)
    doc.add_heading("5.1 Glouton", level=2)
    doc.add_paragraph(
        "Le glouton traite les sommets dans leur ordre d'entrée. Pour chacun, il examine les couleurs déjà portées par ses voisins et choisit la plus petite couleur disponible. Cette méthode construit toujours une coloration propre, mais le nombre de couleurs dépend de l'ordre et n'est pas nécessairement minimal."
    )
    add_code_block(doc,
        "GLOUTON(A, n)\n"
        "Entrées : matrice d'adjacence A, nombre de sommets n\n"
        "Sorties : couleur[0..n-1], K_glouton\n"
        "initialiser couleur[v] ← 0 pour chaque sommet v\n"
        "pour v = 0 … n−1 :\n"
        "    effacer interdit[1..n]\n"
        "    pour u = 0 … n−1 :\n"
        "        si A[v,u] = 1 et couleur[u] > 0 : interdit[couleur[u]] ← vrai\n"
        "    c ← plus petite couleur ≥ 1 telle que interdit[c] = faux\n"
        "    couleur[v] ← c\n"
        "retourner couleur et max(couleur)", size=8.2)
    doc.add_paragraph(
        "La validité est préservée à chaque étape : seules les couleurs des voisins déjà coloriés sont interdites, et le sommet reçoit une autre couleur. Toute arête a donc des extrémités de couleurs différentes lorsque le parcours se termine."
    )
    doc.add_heading("5.2 Backtracking exact", level=2)
    doc.add_paragraph(
        "Pour une valeur fixée de K, la recherche affecte une couleur au sommet courant, vérifie les contraintes avec ses voisins, puis poursuit récursivement. Elle annule l'affectation et essaie une autre couleur quand une branche mène à une impasse. La recherche du nombre chromatique teste K en ordre croissant jusqu'à la première solution, avec le résultat glouton comme borne supérieure."
    )
    add_code_block(doc,
        "EST_VALIDE(v, c, couleur, A, n)\n"
        "Entrées : sommet v, couleur c, tableau couleur, matrice A, taille n\n"
        "Sortie : vrai si c peut être affectée à v, faux sinon\n"
        "pour u = 0 … n−1 :\n"
        "    si A[v,u] = 1 et couleur[u] = c : retourner faux\n"
        "retourner vrai\n\n"
        "COLORIER(v, K, couleur, A, n)\n"
        "Entrées : sommet courant v, limite K, tableau couleur, matrice A, taille n\n"
        "Sortie : vrai si les sommets v..n−1 peuvent être coloriés; couleur contient la solution\n"
        "si v = n : retourner vrai\n"
        "pour c = 1 … K :\n"
        "    si EST_VALIDE(v, c, couleur, A, n) :\n"
        "        couleur[v] ← c\n"
        "        si COLORIER(v+1, K, couleur, A, n) : retourner vrai\n"
        "        couleur[v] ← 0  // retour arrière\n"
        "retourner faux\n\n"
        "TROUVER_NOMBRE_CHROMATIQUE(A, n)\n"
        "Entrées : matrice d'adjacence A, nombre de sommets n\n"
        "Sorties : χ(G), coloration optimale\n"
        "si n = 0 : retourner (0, tableau vide)\n"
        "K_glouton ← GLouton(A, n).nombre_de_couleurs\n"
        "pour K = 1 … K_glouton :\n"
        "    initialiser couleur[v] ← 0 pour chaque v\n"
        "    si COLORIER(0, K, couleur, A, n) : retourner (K, couleur)", size=8.1)
    doc.add_heading("5.2.1 Arbre de recherche", level=3)
    doc.add_paragraph(
        "Un nœud représente une affectation partielle des couleurs aux premiers sommets. Une branche ajoute un choix c∈{1,…,K} pour le sommet suivant, uniquement si EST_VALIDE l'accepte. Une feuille est soit une coloration complète valide, soit une impasse où aucune couleur n'est admissible. Pour C₅ avec K=2, les deux choix possibles pour v₁ donnent des sous-arbres symétriques; dans chacun, v₅ ne peut recevoir ni 1 ni 2."
    )
    add_figure(doc, FIGURES / "arbre_backtracking_c5_k2.png",
               "Figure 3. Recherche avec deux couleurs sur C₅ : les deux branches se terminent par une impasse.", 6.2)
    doc.add_heading("5.2.2 Trace d'une branche avec K=2", level=3)
    doc.add_paragraph("Branche illustrative avec K=2 sur C₅ :")
    add_table(doc, ["Étape", "Affectation", "Décision"], [
        ["1", "v₁ = 1", "première couleur disponible"],
        ["2", "v₂ = 2", "v₂ est adjacent à v₁"],
        ["3", "v₃ = 1", "v₃ est adjacent à v₂"],
        ["4", "v₄ = 2", "v₄ est adjacent à v₃"],
        ["5", "v₅", "échec : ses voisins v₁ et v₄ utilisent 1 et 2"],
    ], caption="Trace d'une branche du backtracking sur C₅")
    doc.add_paragraph(
        "Le solveur annule alors l'affectation précédente et explore les autres couleurs possibles. Les branches restantes échouent aussi, conformément à la preuve que C₅ n'est pas biparti."
    )

    doc.add_heading("6. Implémentation C et OpenMP", level=1)
    doc.add_paragraph(
        "Le graphe est stocké dans une matrice compacte d'octets. Le lecteur accepte une matrice binaire compacte ou séparée par des espaces, puis vérifie la taille, la symétrie et l'absence de boucles. Les sorties JSON donnent les paramètres du graphe, la coloration, sa validité et les temps mesurés."
    )
    doc.add_page_break()
    add_table(doc, ["Version", "Travail partagé", "Synchronisation"], [
        ["Glouton séquentiel", "Balayage des sommets et des voisins", "Aucune"],
        ["Glouton OpenMP", "Examen parallèle des voisins d'un sommet", "atomic write, barrières implicites, single"],
        ["Exact séquentiel", "Exploration récursive des couleurs", "Aucune"],
        ["Exact OpenMP", "Branches indépendantes de l'arbre", "parallel, single, task, taskwait, critical, atomic"],
    ], caption="Travail et synchronisation des quatre versions")
    doc.add_paragraph(
        "Dans le glouton OpenMP, l'ordre externe reste séquentiel : une décision de couleur dépend des sommets précédents. Les threads marquent le même tableau partagé forbidden avec atomic write. Pour chaque sommet, les deux directives single et la boucle omp for ont chacune une barrière implicite, soit trois rendez-vous par sommet. G12000 entraîne donc environ 36 000 barrières, hors entrée et sortie de la région parallèle."
    )
    doc.add_paragraph(
        "Dans le backtracking OpenMP, le graphe reste partagé en lecture seule et chaque tâche reçoit sa copie du tableau des couleurs. parallel crée l'équipe, single lance une recherche racine, task distribue les branches et taskwait attend les tâches enfants. Les lectures et publications de solution_found sont atomiques. Dans publish_solution, critical sérialise les candidats; le premier thread qui constate le drapeau à faux copie le tableau, puis le publie atomiquement avant de quitter la section critique. taskwait attend les tâches enfants, mais ne protège pas à lui seul les données partagées. La profondeur de création est limitée à quatre et le budget à 8 192 tâches."
    )
    doc.add_paragraph("Pseudo-code du glouton OpenMP : l'ordre des sommets reste séquentiel ; omp for répartit les colonnes de la ligne courante.")
    greedy_omp = (
        "Entrées : A, n, p\nSorties : colors, K_glouton\n"
        "#pragma omp parallel num_threads(p) shared(colors, forbidden)\n"
        "pour v = 0 … n−1 :\n"
        "    #pragma omp single  // effacement unique, barrière implicite\n"
        "        effacer forbidden[1…n]\n"
        "    #pragma omp for  // barrière implicite avant la sélection\n"
        "        pour u = 0 … n−1 :\n"
        "            si A[v,u] = 1 et colors[u] > 0 :\n"
        "                #pragma omp atomic write  // marques concurrentes sûres\n"
        "                    forbidden[colors[u]] ← 1\n"
        "    #pragma omp single  // choisit la plus petite couleur libre, puis barrière implicite\n"
        "        colors[v] ← min{c ≥ 1 : forbidden[c] = 0}"
    )
    add_code_block(doc, greedy_omp, size=8.3)
    doc.add_paragraph("Pseudo-code de la recherche parallèle; chaque tâche possède un tableau de couleurs privé. Le drapeau atomique sert à l'arrêt anticipé, critical protège l'unique copie, et taskwait attend les tâches enfants.")
    parallel_omp = (
        "Entrées : A, n, K, p, profondeur_max, budget_tâches\n"
        "Sorties : un résultat de décision et, si possible, une coloration\n"
        "#pragma omp parallel num_threads(p) shared(solution_found, solution)\n"
        "    #pragma omp single  // un seul thread lance la recherche racine\n"
        "        CHERCHER(0, couleurs_vides, profondeur=0)\n"
        "\n"
        "CHERCHER(i, couleurs, profondeur) :\n"
        "    #pragma omp atomic read  // lire le drapeau d'arrêt sans data race\n"
        "    si solution_found : retourner\n"
        "    si i = n :\n"
        "        #pragma omp critical(solution_copy) :\n"
        "            #pragma omp atomic read  // relire le drapeau sous critical\n"
        "            si solution_found = faux :\n"
        "                copier couleurs vers solution\n"
        "                #pragma omp atomic write  // publication avant de quitter critical\n"
        "                solution_found ← 1\n"
        "        retourner\n"
        "    pour chaque couleur admissible c :\n"
        "        créer une copie indépendante couleurs_c\n"
        "        si profondeur < profondeur_max :\n"
        "            #pragma omp task firstprivate(couleurs_c) shared(solution_found)\n"
        "                CHERCHER(i+1, couleurs_c, profondeur+1)\n"
        "        sinon : CHERCHER(i+1, couleurs_c, profondeur+1)\n"
        "    si des tâches enfants ont été créées :\n"
        "        #pragma omp taskwait  // parent attend toutes ses branches créées"
    )
    add_code_block(doc, parallel_omp, size=8.1)

    doc.add_heading("7. Analyse de complexité", level=1)
    doc.add_paragraph(
        "On note n=|V| et m=|E|. La représentation imposée est une matrice d'adjacence qui occupe Θ(n²) octets. Le comptage des arêtes parcourt le triangle supérieur de la matrice et coûte Θ(n²)."
    )
    add_table(doc, ["Algorithme", "Meilleur cas", "Cas moyen", "Pire cas", "Espace auxiliaire"], [
        ["Glouton, matrice", "Θ(n²)", "Θ(n²)", "Θ(n²)", "O(n)"],
        ["Décision exacte, K couleurs", "Θ(n) si échec rapide", "Mesuré sur G(n,p=0,45)", "O(nKⁿ)", "O(n) + pile O(n)"],
        ["Recherche de χ(G)", "Θ(n²) si χ=1", "Moyenne empirique par taille", "O(n Σ(kⁿ)), k=1..χ(G)", "O(n) + pile O(n)"],
        ["Exact OpenMP", "Dépend de l'arbre", "Mesuré par configuration", "Même ordre exponentiel, plus tâches", "O(nQ), Q≤8 192 tâches"],
    ], caption="Complexités temporelles et spatiales sous matrice d'adjacence")
    doc.add_paragraph(
        "Le temps quadratique du glouton vient de la lecture complète de n colonnes pour chacun des n sommets. Même si m=0, l'implémentation ne parcourt pas seulement les arêtes présentes : elle inspecte toutes les cases de la matrice. La recherche d'une couleur libre coûte au plus O(n) opérations supplémentaires par sommet."
    )
    doc.add_paragraph(
        "Pour une décision à K couleurs, l'arbre a au plus n niveaux et K branches par niveau. Chaque essai de couleur peut lire jusqu'à n cases de la ligne courante, d'où O(nKⁿ) au pire. Un échec rapide peut arrêter la recherche après les premières affectations, en Θ(n) dans un cas favorable. À l'inverse, sur le graphe vide avec K=1, une seule branche atteint la solution, mais chaque sommet balaie une ligne complète, donc Θ(n²). Le cas moyen n'a pas de borne serrée universelle indépendante de la distribution; nous le caractérisons par les temps moyens observés sur la famille G(n,p=0,45), avec cinq répétitions par configuration."
    )
    doc.add_paragraph(
        "Pour chaque taille, les cinq répétitions portent sur le même préfixe déterministe. Leur moyenne décrit le temps observé pour cette instance ; elle ne représente pas l'espérance statistique sur tous les graphes de même taille. L'analyse compare les moyennes entre tailles sans présenter cette série comme une borne asymptotique du cas moyen."
    )

    doc.add_heading("8. Organisation et protocole", level=1)
    doc.add_heading("8.1 Phases du projet", level=2)
    add_table(doc, ["Phase", "Travail", "Résultat attendu"], [
        ["Analyse", "Formaliser le coloriage, les entrées et les cas d'usage", "Spécification et exemples"],
        ["Versions séquentielles", "Coder le glouton et le backtracking, valider les entrées", "Références de correction"],
        ["Parallélisation", "Ajouter OpenMP, les atomiques, les tâches et le traçage", "Deux variantes parallèles sûres"],
        ["Expériences", "Calibrer les graphes, mesurer, calculer S(p) et E(p), tracer le Gantt", "CSV et figures"],
        ["Synthèse", "Analyser la complexité, interpréter les résultats et préparer la démonstration", "Rapport et diapositives"],
    ], caption="Phases du projet et résultats attendus")
    doc.add_heading("8.2 Protocole expérimental", level=2)
    doc.add_paragraph(
        "Les graphes exacts sont des préfixes d'une même instance aléatoire symétrique, générée avec la graine 20261108 et une densité cible de 0,45. Le pilote séquentiel garde les quatre plus grandes tailles résolues sous 60 secondes. Les graphes gloutons, de tailles 1 000 à 12 000, partagent la graine 20261109 et une densité cible de 0,10."
    )
    selected_text = ", ".join(f"{x['name']} (m={x['m']}, d={format_decimal(x['density'], 3)})" for x in exact_selection)
    doc.add_paragraph(f"Instances exactes retenues : {selected_text}.")
    doc.add_paragraph(
        "Chaque configuration utilise une exécution d'échauffement et cinq mesures. Pour les petits cas exacts, un lot de plusieurs résolutions amortit la granularité de l'horloge ; le temps indiqué est divisé par la taille du lot. Le chargement et la validation des matrices sont hors chronométrage. Les équipes OpenMP dynamiques sont désactivées et la liaison des threads est fixée à close."
    )
    cpu_count = os.cpu_count() or 1
    gcc_version = subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    doc.add_paragraph(
        f"Environnement de mesure : {platform.platform()} ; {cpu_count} processeurs logiques visibles ; {gcc_version}. "
        "Les résultats dépendent du processeur, du système, de la version du runtime OpenMP et de la charge de la machine."
    )

    doc.add_heading("9. Résultats", level=1)
    doc.add_heading("9.1 Glouton", level=2)
    add_performance_table(doc, summary, "greedy")
    add_summary_text(doc, summary, "greedy")
    add_figure(doc, FIGURES / "temps_threads_greedy.png",
               "Figure 4. Temps moyen (secondes) du glouton selon p pour G1000, G2000, G4000, G8000 et G12000.")
    add_figure(doc, FIGURES / "speedup_greedy.png",
               "Figure 5. Accélération S(p) du glouton pour G1000, G2000, G4000, G8000 et G12000, avec la référence idéale.")
    add_figure(doc, FIGURES / "efficacite_greedy.png",
               "Figure 6. Efficacité E(p) du glouton pour G1000, G2000, G4000, G8000 et G12000.")
    doc.add_paragraph(
        "Les courbes de temps, d'accélération et d'efficacité comparent G1000, G2000, G4000, G8000 et G12000. Pour G12000, le séquentiel prend 159,20 ms; à p=2, 4 et 8, S vaut respectivement 0,22, 0,13 et 0,07. L'accélération reste inférieure à 1 avec plusieurs threads."
    )
    doc.add_paragraph(
        "Sur G12000, les 7 194 563 arêtes donnent environ 7,19 millions d'écritures atomiques pendant une résolution, en plus des 36 000 barrières implicites. Les threads écrivent dans les mêmes lignes du petit tableau forbidden; le coût dépend du runtime OpenMP et du processeur, mais la contention et le trafic de cohérence peuvent annuler le gain du balayage parallèle. Il s'agit d'un partage concurrent des cases, pas d'une preuve de fausse-partage ni d'une garantie d'instructions LOCK."
    )
    doc.add_heading("9.2 Backtracking exact", level=2)
    add_performance_table(doc, summary, "exact")
    add_summary_text(doc, summary, "exact")
    add_figure(doc, FIGURES / "temps_threads_exact.png",
               "Figure 7. Temps moyen (secondes) du backtracking selon p pour G20, G24, G30 et G36.")
    add_figure(doc, FIGURES / "speedup_exact.png", "Figure 8. Accélération S(p) du backtracking pour G20, G24, G30 et G36, avec la référence idéale.")
    add_figure(doc, FIGURES / "efficacite_exact.png", "Figure 9. Efficacité E(p) du backtracking pour G20, G24, G30 et G36.")
    add_figure(doc, FIGURES / "taille_greedy.png", "Figure 10. Temps d'exécution (secondes) du glouton selon la taille n, en séquentiel et avec quatre threads.")
    add_figure(doc, FIGURES / "taille_exact.png", "Figure 11. Temps d'exécution (secondes) du backtracking selon la taille n, en séquentiel et avec quatre threads.")
    doc.add_paragraph(
        "G30 et G36 sont des préfixes d'une même instance et ont tous deux χ(G)=7. Le temps séquentiel moyen mesuré est pourtant inférieur sur G36 (8,87 s) que sur G30 (10,19 s). Le parcours des trente premiers sommets suit les mêmes branches; G36 ajoute ensuite six sommets à vérifier. Cette différence ne démontre donc pas que le plus grand graphe exige moins de travail : sans compteur de nœuds, nous ne pouvons pas distinguer les effets de la disposition mémoire et de l'exécution de la variabilité de mesure."
    )

    doc.add_heading("9.3 Ordonnancement des tâches", level=2)
    doc.add_paragraph(
        "Les deux traces utilisent G36 et K=6. Comme χ(G36)=7, cette décision est impossible : le solveur explore toutes les branches admissibles jusqu'à leur échec sans arrêt anticipé sur une première solution. Cela fournit une charge suffisamment longue pour comparer les répartitions. Les tâches tracées sont les feuilles séquentielles de profondeur 2; les mesures de performance restent séparées de cette journalisation."
    )
    add_figure(doc, FIGURES / "gantt_2threads.png",
               "Figure 12. Gantt de la recherche G36, K=6, avec deux threads : identifiants, intervalles de début-fin et durées des tâches feuilles.")
    add_figure(doc, FIGURES / "gantt_4threads.png",
               "Figure 13. Gantt de la recherche G36, K=6, avec quatre threads : identifiants, intervalles de début-fin et durées des tâches feuilles.")
    doc.add_paragraph(
        "Les barres turquoise identifient les tâches et leur largeur représente leur durée; l'axe gradué situe leur début et leur fin. Les bandes grises signalent qu'aucune tâche feuille de profondeur 2 n'a été journalisée sur ce thread. Elles peuvent inclure une attente à taskwait, l'absence de tâche prête ou le travail d'un niveau non tracé; elles ne sont donc pas présentées comme une mesure exacte d'inactivité CPU. Les sous-arbres n'ont pas la même taille : certains échouent tôt sur un conflit, d'autres poursuivent l'exploration."
    )

    doc.add_heading("10. Analyse critique", level=1)
    doc.add_heading("10.1 Accélération", level=2)
    doc.add_paragraph(
        "Les tableaux 6 et 7 donnent S(p)=T_s/T_p pour p=2, 4 et 8 sur chaque graphe. L'accélération n'est pas proportionnelle au nombre de threads. Le meilleur résultat mesuré est 5,69 sur G30 avec huit threads, inférieur à l'idéal 8; sur G36, huit threads donnent S=2,62. Pour le glouton, les synchronisations dominent et S reste inférieur à 1 à p≥2."
    )
    doc.add_paragraph(
        "Une accélération supérieure à p est possible en backtracking lorsque l'ordre d'exploration parallèle atteint une coloration valide avant le parcours séquentiel et publie solution_found, ce qui évite d'explorer certaines branches; un meilleur comportement du cache peut aussi contribuer. Ici, G20 dépasse la référence : S(2)=3,41 et S(4)=4,07. Ces valeurs proviennent de temps courts, surtout variables à p=2; elles doivent donc être lues comme des accélérations observées sur cette petite instance, et non comme une efficacité matérielle durable."
    )
    doc.add_paragraph(
        "Les graphiques placent la référence séquentielle sous la catégorie « Séq. » et conservent les mesures OpenMP aux abscisses p=1, 2, 4 et 8. Les deux valeurs restent donc lisibles lorsque le point OpenMP p=1 diffère de la référence. Sur G1000, S(1)=2,00 provient de durées très courtes mesurées séparément et reflète leur variabilité, pas une accélération garantie. Les accélérations limitées viennent aussi du travail séquentiel, de la création et de la copie des tâches, des barrières, des atomiques et du déséquilibre des sous-arbres."
    )
    doc.add_heading("10.2 Efficacité", level=2)
    doc.add_paragraph(
        "Les valeurs E(p)=S(p)/p figurent avec les temps et les speedups dans les tableaux 6 et 7. Elles diminuent généralement avec p : G30 passe de E=1,12 à deux threads à 0,71 à huit threads; G36 passe de 0,63 à 0,33. La petite instance G20 est sensible à la granularité de l'horloge et à la variabilité des tâches, d'où une valeur supérieure à 1 à p=2 qui ne doit pas être interprétée comme une efficacité physique durable."
    )
    doc.add_paragraph(
        "L'efficacité baisse quand les frais de coordination, les accès concurrents et les périodes sans tâche utile augmentent plus vite que le travail partagé. Pour les grands cas exacts, quatre threads offrent un compromis lisible : G30 conserve S=3,45 et E=0,86, tandis que passer à huit threads réduit encore le temps mais ramène E à 0,71. Le choix dépend de la priorité entre temps minimal et utilisation efficace des threads. Pour le glouton mesuré, p=2 est le moins mauvais choix parallèle, mais il reste plus lent que le séquentiel."
    )
    doc.add_heading("10.3 Répartition des tâches et pistes d'amélioration", level=2)
    doc.add_paragraph(
        "Pour équilibrer l'arbre exact, on peut régler la profondeur de création et le seuil de travail restant : créer des tâches seulement tant que suffisamment de sommets ou de possibilités restent à explorer, puis terminer les feuilles en séquentiel. Il faut comparer les temps à p=2, 4 et 8, car des tâches trop fines augmentent l'ordonnancement et des tâches trop grosses réduisent le parallélisme. Un ordre de sommets par degré décroissant ou une heuristique dynamique DSATUR peut aussi faire apparaître les conflits plus tôt; l'exhaustivité des branches restantes doit être conservée pour garder l'optimalité. Les tâches untied ne sont à retenir que si une mesure montre que le déplacement de tâches améliore la charge."
    )
    doc.add_paragraph(
        "Le glouton actuel parallélise uniquement l'examen des voisins et conserve l'ordre séquentiel des sommets. Pour paralléliser réellement plusieurs affectations, une autre stratégie consiste à colorier, par niveaux, des ensembles indépendants construits par priorité, par exemple avec Jones–Plassmann. Une variante à tableaux forbidden privés par thread puis fusionnés peut aussi être testée pour réduire la contention atomique, en mesurant le coût de la remise à zéro et de la fusion. Ces changements produiraient une autre stratégie gloutonne et pourraient modifier le nombre de couleurs."
    )
    doc.add_heading("10.4 Limites du modèle", level=2)
    doc.add_paragraph(
        "Le modèle d'emploi du temps ignore les capacités de salles, les préférences des étudiants et les contraintes de disponibilité. Ces règles demanderaient des contraintes supplémentaires ou une formulation d'optimisation plus riche."
    )

    doc.add_heading("11. Applications", level=1)
    add_table(doc, ["Domaine", "Sommets", "Arêtes", "Couleurs"], [
        ["Examens", "Examens", "Étudiant commun", "Créneaux"],
        ["Télécommunications", "Émetteurs", "Interférence possible", "Fréquences"],
        ["Compilation", "Variables", "Durées de vie qui se chevauchent", "Registres"],
        ["Industrie", "Tâches", "Ressource ou période incompatible", "Machines ou créneaux"],
    ], caption="Exemples d'applications du coloriage de graphes")
    doc.add_paragraph(
        "En télécommunications, les émetteurs sont des sommets, les interférences sont des arêtes et les couleurs attribuent des fréquences compatibles. En compilation, les variables dont les durées de vie se chevauchent sont reliées dans un graphe d'interférence; les couleurs leur affectent des registres distincts. En planification industrielle, les opérations incompatibles partagent une arête et les couleurs désignent des machines ou des créneaux compatibles."
    )

    doc.add_heading("Conclusion", level=1)
    doc.add_paragraph(
        "Les deux approches répondent à des objectifs différents. Le glouton construit une solution valide à faible coût polynomial ; le backtracking certifie le nombre chromatique au prix d'une recherche exponentielle dans le pire cas. OpenMP parallélise les opérations indépendantes du glouton et les branches du solveur exact, avec des coûts de synchronisation qui dépendent de la taille et de la structure du graphe. Les mesures, les courbes et le Gantt permettent de relier ces coûts aux résultats observés plutôt que de supposer une accélération idéale."
    )
    references = doc.add_paragraph(
        "Références : sujet de coloriage de graphes ; fiches d'évaluation générale, de Complexité algorithmique et de Calcul parallèle et distribué ; "
        "OpenMP Application Programming Interface, directives parallel, for, single, task, taskwait, atomic et critical."
    )
    references.paragraph_format.space_before = Pt(4)
    references.paragraph_format.space_after = Pt(0)
    for run in references.runs:
        run.font.size = Pt(8.5)
        run.italic = True
        run.font.color.rgb = RGBColor(90, 100, 110)

    doc.core_properties.title = "Le coloriage de graphes"
    doc.core_properties.subject = "Étude algorithmique et parallélisation OpenMP"
    doc.core_properties.author = "Zied Chouk, Chayma Hakouna, Wirak"
    doc.core_properties.keywords = "coloriage, graphes, backtracking, OpenMP, complexité"
    doc.save(OUT)
    print(f"Rapport écrit : {OUT}")
    print(f"Mesures exploitées : {len(raw)} répétitions brutes")


if __name__ == "__main__":
    build_report()
