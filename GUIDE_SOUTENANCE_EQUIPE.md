# Guide de soutenance du projet de coloriage de graphes

Ce guide sert à comprendre le code et à répartir une soutenance à trois. Les numéros de ligne cités renvoient à `src/coloring.c` dans la version actuelle du dépôt. Les mesures citées sont celles de `results/performance_summary.csv`; les temps varient selon la machine.

## Parcours du code C

Il n'y a qu'un fichier C (`src/coloring.c`) et aucun fichier d'en-tête `.h`. Les types `Graph`, `TraceEvent`, `ParallelSearch` et `SolveResult`, ainsi que les limites de sommets, de tâches et de profondeur par défaut, sont définis aux lignes 13–50.

| Fonction | Lignes | Rôle et points à défendre |
| --- | --- | --- |
| `set_error` | 52–56 | Copie un message d'erreur dans le tampon fourni. |
| `graph_load` | 58–138 | Ouvre le fichier, lit `n`, vérifie `0 ≤ n ≤ 20 000` et les débordements, alloue `n²` octets, puis lit exactement des `0` et `1`. Elle rejette les données supplémentaires, une diagonale non nulle et une matrice asymétrique; elle compte chaque arête une seule fois dans le triangle supérieur. |
| `graph_free` | 140–145 | Libère la matrice et remet la structure à zéro. |
| `coloring_is_valid` | 147–162 | Vérifie que chaque couleur est comprise entre 1 et le nombre annoncé, puis que les extrémités de chaque arête ont des couleurs différentes. Le graphe vide accepte 0 couleur. |
| `greedy_sequential` | 164–193 | Visite les sommets dans l'ordre, balaie les `n` colonnes de la ligne courante, marque les couleurs de voisins déjà coloriés, puis prend la plus petite couleur libre. `seen` utilise `v+1` comme marqueur pour éviter une remise à zéro complète. |
| `greedy_openmp` | 195–244 | Garde l'ordre externe séquentiel. À chaque sommet, un `single` remet à zéro le tableau partagé `forbidden`; `omp for` distribue les colonnes; `atomic write` protège les écritures concurrentes de `1`; la barrière implicite de la boucle précède le choix de la plus petite couleur dans un second `single`. Les trois constructions apportent trois barrières implicites par sommet, donc 36 000 pour G12000. |
| `is_safe_color` | 246–253 | Parcourt la ligne d'adjacence du sommet et refuse une couleur déjà utilisée par un voisin. Un conflit peut arrêter le balayage avant la dernière colonne. |
| `search_sequential` | 255–269 | Récursion de retour sur trace : essaie les couleurs 1 à K, avance si la couleur est sûre, puis remet la case à 0 en cas d'échec. Le cas de base réussit après le dernier sommet. |
| `decide_sequential` | 271–285 | Prépare le tableau de couleurs et traite le cas vide. Elle répond à la question de décision pour une valeur donnée de K. |
| `atomic_solution_found` | 287–293 | Lit atomiquement le drapeau d'arrêt partagé afin d'éviter une lecture concurrente non synchronisée. |
| `reserve_task_id` | 295–305 | Protège avec `critical(task_budget)` le compteur qui borne le nombre de tâches à 8 192. Quand le plafond est atteint, la branche continue séquentiellement. |
| `publish_solution` | 307–320 | Entre dans `critical(solution_copy)`, relit atomiquement `solution_found`, copie la première coloration gagnante puis publie le drapeau par `atomic write`. La section critique protège le tableau; l'atomique protège le drapeau. |
| `run_task_branch` | 324–341 | Encadre l'exécution d'une branche. En mode Gantt, il enregistre identifiant, profondeur, thread et temps avec `omp_get_wtime()`, puis libère la copie de couleurs de la branche. |
| `search_parallel` | 343–395 | Arrête tôt si une solution a été publiée; examine les couleurs sûres; copie le tableau avant de créer une tâche `firstprivate`; poursuit les branches sans tâche sur le thread courant. La création s'arrête à `task_depth` (4 par défaut) ou au plafond de tâches. `taskwait` attend les enfants créés par cet appel. |
| `write_gantt_csv` | 397–418 | Écrit les événements tracés dans un CSV avec début, fin et durée. |
| `decide_parallel` | 420–490 | Alloue l'état racine et la solution partagée, démarre une région `parallel`, puis un seul thread lance la racine dans `single`. Le `taskwait` final attend les descendants avant la sortie de la région. Si le traçage est actif, elle écrit ensuite le CSV. |
| `solve_chromatic` | 492–529 | Calcule d'abord une borne supérieure avec le glouton séquentiel puis essaie K dans l'ordre croissant. Le premier succès est donc optimal. Pour le graphe vide, χ vaut 0. |
| `free_result` | 531–534 | Libère la coloration d'un résultat et remet la structure à zéro. |
| `solve_once` | 536–576 | Relie les quatre chaînes du CLI aux fonctions gloutonnes, décisionnelles et de recherche du nombre chromatique. `--k` ne s'applique qu'aux modes exacts. |
| `write_trace_after_solve` | 579–590 | Relance séparément une décision impossible avec `K=χ−1` et une profondeur de tâches 2; les feuilles de profondeur 2 exécutent ensuite le reste de leur sous-arbre en récursion séquentielle. |
| `parse_positive_int` | 593–602 | Valide une option entière et ses limites. |
| `print_usage` | 604–610 | Affiche les quatre modes et les options reconnues. |
| `main` | 611–778 | Valide les arguments, charge le graphe, exécute les échauffements et répétitions, divise le temps par la taille du lot, déclenche éventuellement le Gantt hors mesure, puis imprime la ligne JSON avec résultat, validité, couleurs, temps et paramètres. |

### Garanties et coûts à savoir expliquer

- **Glouton séquentiel et parallèle :** l'ordre des sommets est déterministe. La couleur d'un sommet dépend des couleurs attribuées aux sommets précédents, donc on ne parallélise pas cette boucle externe. L'OpenMP ne répartit que les colonnes indépendantes du sommet courant; il retrouve la même coloration que le glouton séquentiel.
- **Tableau `forbidden` :** il est partagé une fois par étape de sommet. Plusieurs voisins peuvent interdire la même couleur; `#pragma omp atomic write` rend ces marques concurrentes sûres. Le `omp for` a une barrière implicite avant que `single` lise le tableau.
- **Backtracking parallèle :** le graphe est partagé en lecture seule. Chaque branche possède une copie indépendante du tableau de couleurs. `parallel` crée l'équipe, `single` lance la recherche racine, `task` distribue les branches, `taskwait` attend leurs enfants, `critical` protège l'accès à la copie unique de la solution, et `atomic read/write` synchronise le drapeau `solution_found`.
- **Gantt :** `--gantt` n'est accepté qu'avec `exact-omp` et sans `--k`. Le traçage utilise une seconde résolution et une profondeur 2, afin que les barres représentent l'exécution des sous-arbres par les tâches feuilles. Une bande grise signifie qu'aucune tâche feuille journalisée n'apparaît à cet endroit; ce n'est pas une mesure exacte de l'inactivité CPU.

## Complexité à présenter

On note `n=|V|`, `m=|E|`, et la matrice contient `n²` cases d'un octet. Le paramètre `m` décrit le nombre d'arêtes, mais les algorithmes parcourent les lignes de la matrice au lieu d'itérer uniquement sur les arêtes présentes.

| Algorithme | Meilleur cas | Cas moyen | Pire cas | Espace |
| --- | --- | --- | --- | --- |
| Glouton matriciel | Θ(n²) | Θ(n²) | Θ(n²) | Θ(n²) pour la matrice, O(n) auxiliaire |
| Décision exacte à K | Θ(n) si un conflit arrête vite une branche; Θ(n²) sur une solution comme le graphe vide à K=1 | Dépend de la distribution; moyenne empirique sur les instances G(n, 0,45), cinq répétitions | O(nKⁿ) | Matrice Θ(n²), couleurs O(n), pile O(n) |
| Recherche de χ | Θ(n²) lorsque χ=1 et que la première décision réussit | Mesures empiriques par taille et graine, sans prétendre à une espérance universelle | O(n Σ(kⁿ)), pour k=1..χ(G) | Matrice Θ(n²), vecteurs et pile O(n) |
| Exact OpenMP | Dépend de l'arbre et de l'ordre d'exploration | Mesuré par nombre de threads sur la même instance | Même croissance exponentielle au pire, avec frais de tâches | Matrice Θ(n²), état O(n) par branche active, au plus 8 192 identifiants de tâche |

Pour le glouton, chaque sommet balaie les `n` colonnes, même si `m=0`, ce qui explique Θ(n²) dans les trois cas. Pour la décision exacte, l'arbre a au plus `n` niveaux et `K` choix par niveau; un contrôle de conflit peut lire jusqu'à `n` colonnes. Le cas moyen du coloriage exact dépend fortement de la structure et de la distribution des graphes : les résultats du projet sont des moyennes empiriques sur les instances générées à graine fixe, pas une formule générale.

## Répartition de la présentation et de la démonstration

Les trois rôles visent environ le même temps de parole (environ quatre minutes chacun). La répartition privilégie les blocs logiques du sujet; le rôle 2 développe davantage le code et les synchronisations, tandis que le rôle 3 présente les chiffres et le terminal.

| Rôle | Diapositives et contenu | Partie de la démo |
| --- | --- | --- |
| **1 — Problème, modélisation, algorithmes séquentiels et complexité** | Slides 2–7 : modèle, C₅, trace manuelle, glouton, backtracking et complexités. Présente aussi l'examen comme exemple réel sur la slide 10. | Lance `exact-seq` sur C₅ et explique pourquoi la sortie certifie χ(C₅)=3. |
| **2 — OpenMP et synchronisation** | Slides 8–9 : dépendance de l'ordre glouton, `forbidden`, tâches exactes, copies privées, atomiques, sections critiques et attentes. Explique comment le modèle d'examens se transpose à l'exécution parallèle sur la slide 10. | Montre les blocs source des fonctions `greedy_openmp` et `search_parallel`; explique les directives et le drapeau d'arrêt sans ajouter de calcul long. |
| **3 — Expériences, speedup, efficacité, Gantt et conclusion** | Slides 11–17 : protocole, temps, accélération, efficacité, taille, Gantt, applications et conclusion. | Lance les deux commandes G20 séquentielle et OpenMP, compare `seconds` et rappelle que le temps varie selon la machine. |

## Questions probables du jury

### Complexité algorithmique — 7 questions

1. **Pourquoi le glouton est-il en Θ(n²) avec une matrice ?**
   Il lit jusqu'à n cases pour chacun des n sommets. `greedy_sequential` fait la boucle complète sur `u` aux lignes 164–193; `greedy_openmp` partage cette même ligne entre les threads aux lignes 195–244.

2. **Pourquoi le nombre d'arêtes m ne donne-t-il pas ici un coût Θ(n+m) ?**
   `graph_load`, `greedy_sequential` et `is_safe_color` parcourent la représentation matricielle. Même quand m=0, les n² cases sont inspectées par les algorithmes concernés.

3. **Quel est le meilleur cas de la décision exacte ?**
   Un conflit découvert tôt peut arrêter rapidement une branche; pour n≥2 le coût total peut être Θ(n), car le premier contrôle parcourt une ligne et le suivant échoue tôt. Une instance satisfaisable, comme le graphe vide à K=1, suit n niveaux et balaie une ligne par niveau, donc Θ(n²).

4. **Comment caractérisez-vous le cas moyen du backtracking ?**
   Il n'existe pas de valeur moyenne indépendante du modèle de graphe. Nous rapportons des répétitions sur les préfixes déterministes de densité cible 0,45, après calibration, et nous présentons leur moyenne comme un résultat empirique.

5. **D'où vient O(nKⁿ) ?**
   `search_sequential` a au plus n niveaux, chacun essaie jusqu'à K couleurs, et `is_safe_color` peut balayer n colonnes; la borne du pire cas combine ces facteurs.

6. **Comment prouvez-vous que le nombre de couleurs rendu est minimal ?**
   `solve_chromatic` teste les valeurs de K dans l'ordre croissant et s'arrête à la première solution. Il utilise le glouton comme borne supérieure valide, donc il ne manque pas de solution au-delà.

7. **Quelle mémoire consomment les versions exactes ?**
   La matrice prend Θ(n²) octets. Le vecteur de couleurs et la pile de récursion prennent O(n); le parallèle ajoute une copie O(n) pour chaque branche active, avec un plafond de 8 192 tâches réservées.

### Calcul parallèle et OpenMP — 8 questions

8. **Pourquoi ne pas paralléliser la boucle externe du glouton ?**
   La couleur de `v` dépend des couleurs déjà attribuées aux sommets précédents. La garder séquentielle conserve l'ordre déterministe et garantit la même sortie que `greedy_sequential`.

9. **Le tableau partagé `forbidden` crée-t-il une course ?**
   Les marques passent par `#pragma omp atomic write`, puis la barrière implicite à la fin de `omp for` précède leur lecture dans `single`. Le choix est effectué une fois par sommet.

10. **Quelle différence entre `atomic`, `critical` et `taskwait` ?**
    `atomic` protège un accès simple au drapeau ou à une marque; `critical` protège une séquence complète comme la copie de la solution; `taskwait` attend les tâches enfants sans remplacer la protection des données partagées.

11. **Comment `solution_found` est-il publié sans course ?**
    Les tâches lisent le drapeau avec `atomic read`. Dans `publish_solution`, le thread entre dans `critical(solution_copy)`, relit atomiquement le drapeau, copie la solution si aucune autre tâche ne l'a publiée, puis effectue `atomic write`.

12. **Comment les tâches gardent-elles leurs états indépendants ?**
    `search_parallel` alloue un nouveau tableau, le remplit par `memcpy`, applique la couleur de la branche puis le transmet en `firstprivate` à `task`. Les tâches sont créées jusqu'à la profondeur 4 par défaut; ensuite les branches sont explorées récursivement sur le thread courant.

13. **Que font `parallel`, `single` et les deux `taskwait` ?**
    `parallel` crée l'équipe OpenMP; `single` choisit un thread pour lancer la recherche racine. Le `taskwait` dans `search_parallel` attend les enfants créés par cet appel, et celui de `decide_parallel` attend les descendants avant la fin de la région.

14. **Que mesure le Gantt et que signifient les espaces gris ?**
    La trace séparée journalise les tâches feuilles de profondeur 2 avec leur thread et leurs temps relatifs à `omp_get_wtime()`. Le CSV montre leurs débuts, fins et durées; le gris peut correspondre à de l'attente, à aucune tâche disponible ou à du travail non tracé, pas nécessairement à un cœur CPU inactif.

15. **Comment expliquer les résultats inattendus des benchmarks ?**
    À G12000, le séquentiel prend environ 159 ms, contre 740 ms à deux threads, 1,207 s à quatre et 2,410 s à huit : balayages, barrières et atomiques dominent. Sur G20, 6,76 ms séquentielles contre 1,66 ms à quatre threads donnent S(4)≈4,07; cette accélération observée vient d'une petite instance et d'un ordre d'exploration qui peut trouver plus tôt la solution, avec une mesure sensible au bruit. G36 est plus rapide séquentiellement que G30 (8,87 s contre 10,19 s) malgré sa taille supérieure, car la taille seule ne détermine pas la forme de l'arbre de recherche. Les traces Gantt couvrent 7,262 s à deux threads et 5,005 s à quatre; les sous-arbres de tailles différentes expliquent le déséquilibre visible.

## Démonstration terminale en moins de 90 secondes

Compiler avant l'arrivée du jury. Sous Windows PowerShell :

```powershell
New-Item -ItemType Directory -Force build | Out-Null
gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -fopenmp src/coloring.c -o build/coloring.exe -fopenmp
Test-Path data/generated/exact/g20.txt
```

La dernière commande doit afficher `True`. Ne générez pas les graphes ni ne lancez toute la suite de benchmarks pendant la soutenance. Ordre de la démo :

```powershell
.\build\coloring.exe data\examples\cycle5.txt exact-seq
.\build\coloring.exe data\generated\exact\g20.txt exact-seq --warmup 1 --repeat 3 --batch 10
.\build\coloring.exe data\generated\exact\g20.txt exact-omp --threads 4 --task-depth 4 --warmup 1 --repeat 3 --batch 10
```

Le premier JSON doit indiquer `chromatic_number: 3` et `solution_valid: true`. G20 doit donner χ=5 et une coloration valide dans les deux dernières lignes; `seconds` donne les trois temps par résolution, déjà divisés par le lot de 10. Les moyennes enregistrées sont proches de 6,76 ms pour `exact-seq` et 1,66 ms pour `exact-omp` à quatre threads. Présentez-les comme une référence avec variation en direct, pas comme des durées garanties. Enchaînez sans pause : le solveur ne devrait pas prendre plus de quelques secondes sur G20.

Pour Linux, remplacez `.\build\coloring.exe` par `./build/coloring` et les séparateurs Windows par `/`.
