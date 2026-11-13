# Coloriage de graphes

Projet universitaire en C11 et OpenMP : deux stratégies de coloriage de graphes, leurs versions parallèles, une analyse de complexité et des mesures reproductibles. Le graphe de démonstration G20 est présent et exempté du `.gitignore`. Les grandes entrées de benchmark sont générées localement par `python scripts/generate_graphs.py`.

## Démarrage rapide

Prérequis : GCC avec OpenMP (`gcc -fopenmp`) et Python 3. Le programme C ne dépend d'aucune bibliothèque tierce. Pour les graphiques et la génération du rapport, installez les bibliothèques Python utilisées par les scripts :

```bash
python -m pip install matplotlib python-docx Pillow
```

Le générateur JavaScript alternatif `scripts/plot_results.mjs` demande Node.js et le paquet `sharp` (`npm install --no-save --package-lock=false sharp`). Les tracés Python sont la voie recommandée et n'ont pas besoin de Node.js.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force build | Out-Null
gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -fopenmp src/coloring.c -o build/coloring.exe -fopenmp
.\build\coloring.exe data\examples\cycle5.txt exact-seq
```

### Linux

```bash
mkdir -p build
gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -fopenmp src/coloring.c -o build/coloring -fopenmp
./build/coloring data/examples/cycle5.txt exact-seq
```

La commande sur `cycle5.txt` doit afficher une solution valide avec `chromatic_number: 3`. Pour vérifier G20 sans générer les autres graphes :

```text
Windows : .\build\coloring.exe data\generated\exact\g20.txt exact-seq
Linux   : ./build/coloring data/generated/exact/g20.txt exact-seq
```

Les fichiers G12 à G36 et les graphes gloutons G1000 à G12000 sont ignorés par Git. Pour les (re)créer, lancez `python scripts/generate_graphs.py`.

## Modes et options

```text
PROGRAMME FICHIER_GRAPHE MODE [options]
```

| Mode | Fonction |
| --- | --- |
| `greedy-seq` | Coloration gloutonne séquentielle, dans l'ordre des sommets du fichier. |
| `greedy-omp` | Même ordre déterministe; le balayage des voisins est parallèle. |
| `exact-seq` | Recherche séquentielle par retour sur trace du nombre chromatique. |
| `exact-omp` | Recherche exacte avec tâches OpenMP et espaces de couleurs privés par branche. |

| Option | Valeurs et effet |
| --- | --- |
| `--threads N` | 1 à 256, défaut 1. Nombre de threads OpenMP. |
| `--task-depth N` | 1 à 4, défaut 4. Profondeur jusqu'à laquelle `exact-omp` crée des tâches. |
| `--k K` | Entier positif. En mode exact, demande si le graphe est coloriable avec au plus K couleurs. |
| `--warmup N` | 0 à 20, défaut 0. Résolutions d'échauffement exclues des temps affichés. |
| `--repeat N` | 1 à 100, défaut 1. Nombre de répétitions chronométrées. |
| `--batch N` | 1 à 1 000 000, défaut 1. Résolutions par lot; le temps du lot est divisé par N. |
| `--gantt CSV` | Écrit la trace Gantt d'une résolution `exact-omp`; incompatible avec `--k`. Le traçage est séparé des mesures. |

Exemples des quatre modes :

```text
Windows : .\build\coloring.exe data\examples\cycle5.txt greedy-seq
Windows : .\build\coloring.exe data\examples\cycle5.txt greedy-omp --threads 4
Windows : .\build\coloring.exe data\examples\cycle5.txt exact-seq --k 2
Windows : .\build\coloring.exe data\examples\cycle5.txt exact-omp --threads 4 --task-depth 4
Linux   : ./build/coloring data/examples/cycle5.txt greedy-seq
Linux   : ./build/coloring data/examples/cycle5.txt greedy-omp --threads 4
Linux   : ./build/coloring data/examples/cycle5.txt exact-seq --k 2
Linux   : ./build/coloring data/examples/cycle5.txt exact-omp --threads 4 --task-depth 4
```

Le chargeur attend `n`, puis exactement `n²` valeurs `0` ou `1`. Les espaces et retours à la ligne peuvent séparer les valeurs. Il rejette les matrices asymétriques, les diagonales non nulles, les valeurs invalides et les données après la matrice. Le graphe vide s'écrit avec un unique `0`. Chaque résolution imprime un objet JSON avec les caractéristiques du graphe, la coloration, sa validité et les temps.

## Tests et benchmarks

Après compilation, les tests fonctionnels se lancent avec :

```bash
python tests/test_color.py
```

Le générateur produit des graphes symétriques à graine fixe : exacts de densité cible 0,45 et gloutons de densité cible 0,10. Le benchmark séquentiel calibre les tailles exactes, puis mesure les mêmes instances avec 1, 2, 4 et 8 threads :

```bash
python scripts/generate_graphs.py
python scripts/benchmark.py
python scripts/plot_results.py
```

`scripts/benchmark.py` sélectionne les quatre plus grandes instances exactes dont la calibration séquentielle prend moins de 60 secondes. Il écrit `results/raw_measurements.csv`, `results/performance_summary.csv` et `results/exact_selection.json`. Le tracé relit les CSV existants et ne relance pas les mesures. Les figures et CSV de résultats restent suivis par Git.

Pour créer une trace Gantt, utilisez le graphe exact le plus grand indiqué dans `results/exact_selection.json` (G36 avec les données présentes) :

```text
Windows : .\build\coloring.exe data\generated\exact\g36.txt exact-omp --threads 2 --task-depth 2 --gantt results\gantt_2threads.csv
Linux   : ./build/coloring data/generated/exact/g36.txt exact-omp --threads 2 --task-depth 2 --gantt results/gantt_2threads.csv
```

Répétez avec `--threads 4` et `results/gantt_4threads.csv`, puis lancez `python scripts/plot_results.py`. Sous Windows, `scripts/run_all.ps1` automatise la compilation, les tests, la génération, les benchmarks, les traces et les figures. Cette procédure complète peut prendre plusieurs minutes, en particulier pendant la calibration exacte.

Pour le G20 de démonstration en direct, ces commandes bornent les mesures sans régénération :

```text
Windows : .\build\coloring.exe data\generated\exact\g20.txt exact-seq --warmup 1 --repeat 3 --batch 10
Windows : .\build\coloring.exe data\generated\exact\g20.txt exact-omp --threads 4 --task-depth 4 --warmup 1 --repeat 3 --batch 10
Linux   : ./build/coloring data/generated/exact/g20.txt exact-seq --warmup 1 --repeat 3 --batch 10
Linux   : ./build/coloring data/generated/exact/g20.txt exact-omp --threads 4 --task-depth 4 --warmup 1 --repeat 3 --batch 10
```

Les mesures déjà enregistrées pour G20 sont proches de 6,76 ms en séquentiel et 1,66 ms pour OpenMP à quatre threads. Les durées d'un essai en direct varient selon la machine et la charge du système.

## Organisation du dépôt

| Chemin | Contenu |
| --- | --- |
| `src/coloring.c` | Chargeur et validation, colorations gloutonnes, recherche exacte séquentielle/parallèle, interface CLI et JSON. |
| `data/examples/` | C5, exemple d'emploi du temps et étiquettes de cours. |
| `data/generated/exact/g20.txt` | Graphe G20 déterministe conservé dans Git pour la démonstration. |
| `data/generated/` | Autres graphes et manifeste de génération, recréés localement et ignorés par Git. |
| `scripts/build.ps1`, `Makefile` | Compilation Windows et compilation avec GNU Make selon le système. |
| `scripts/generate_graphs.py` | Génération des entrées de benchmark à graines fixes. |
| `scripts/benchmark.py` | Calibration, mesures répétées, speedup et efficacité. |
| `scripts/plot_results.py`, `scripts/plot_results.mjs` | Graphiques depuis les mesures CSV existantes. |
| `scripts/create_report.py` | Génération du rapport DOCX et de ses tableaux et figures. Requiert `python-docx` et Matplotlib. |
| `scripts/artifact_deck.mjs` | Source d'édition de la présentation modifiable de 17 diapositives. |
| `scripts/set_pptx_metadata.py` | Règle les propriétés auteur, titre et sujet d'un PPTX exporté. |
| `tests/test_color.py` | Tests de validation et de correction sur des graphes connus. |
| `results/*.csv`, `results/figures/` | Mesures reproductibles, événements Gantt et figures suivis par Git. |
| `rapport_coloriage_graphes.docx` | Rapport éditable. |
| `deliverables/rapport_coloriage_graphes.pdf` | Rapport PDF final. |
| `deliverables/presentation_coloriage_graphes.pptx` | Présentation PowerPoint modifiable. |
| `GUIDE_SOUTENANCE_EQUIPE.md` | Répartition d'équipe, explication du code, Q&R et déroulé de démonstration. |

Après un nouvel export PowerPoint, réglez les propriétés auteur et sujet avec `python scripts/set_pptx_metadata.py deliverables/presentation_coloriage_graphes.pptx`. La source `scripts/artifact_deck.mjs` est destinée à l'édition dans la session Artifact du projet; le PPTX exporté reste directement modifiable dans PowerPoint ou LibreOffice Impress.

## Rappels de complexité

Avec la matrice d'adjacence, le glouton lit n cases pour chacun des n sommets : son temps est Θ(n²) au meilleur, au moyen et au pire cas, même quand m=0. Pour la décision exacte à K couleurs, la récursion descend jusqu'à n niveaux, chaque niveau essaie au plus K couleurs et chaque contrôle peut balayer n colonnes; le pire cas est O(nKⁿ). Le nombre chromatique est recherché en essayant les K croissants jusqu'à une solution, avec le nombre de couleurs glouton comme borne supérieure. Les moyennes empiriques dépendent des instances et de la distribution génératrice décrites ci-dessus.
