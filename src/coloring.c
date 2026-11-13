#define _CRT_SECURE_NO_WARNINGS
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <omp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_GRAPH_VERTICES 20000U
#define MAX_OPENMP_TASKS 8192
#define DEFAULT_TASK_DEPTH 4

typedef struct {
    size_t n;
    size_t m;
    uint8_t *adj;
} Graph;

typedef struct {
    int task_id;
    int depth;
    int thread_id;
    double start_s;
    double end_s;
} TraceEvent;

typedef struct {
    const Graph *graph;
    int k;
    int solution_found;
    int *solution;
    int task_depth;
    int tasks_created;
    TraceEvent *events;
    bool tracing;
    double trace_start;
    char *error;
    size_t error_capacity;
} ParallelSearch;

typedef struct {
    int chromatic_number;
    bool colorable;
    bool decision_mode;
    int *colors;
} SolveResult;

static void set_error(char *buffer, size_t capacity, const char *message) {
    if (buffer != NULL && capacity > 0) {
        snprintf(buffer, capacity, "%s", message);
    }
}

static bool graph_load(const char *path, Graph *graph, char *error, size_t error_capacity) {
    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        snprintf(error, error_capacity, "Impossible d'ouvrir '%s': %s", path, strerror(errno));
        return false;
    }

    long long parsed_n = -1;
    if (fscanf(file, "%lld", &parsed_n) != 1 || parsed_n < 0 ||
        (unsigned long long)parsed_n > MAX_GRAPH_VERTICES) {
        set_error(error, error_capacity, "La première valeur doit être un nombre de sommets entre 0 et 20000.");
        fclose(file);
        return false;
    }

    const size_t n = (size_t)parsed_n;
    if (n != 0 && n > SIZE_MAX / n) {
        set_error(error, error_capacity, "La taille de la matrice dépasse les limites de la plateforme.");
        fclose(file);
        return false;
    }

    uint8_t *adj = NULL;
    if (n != 0) {
        adj = (uint8_t *)malloc(n * n * sizeof(*adj));
        if (adj == NULL) {
            set_error(error, error_capacity, "Mémoire insuffisante pour la matrice d'adjacence.");
            fclose(file);
            return false;
        }
    }

    for (size_t i = 0; i < n * n; ++i) {
        int ch;
        do {
            ch = fgetc(file);
        } while (ch != EOF && isspace((unsigned char)ch));
        if (ch != '0' && ch != '1') {
            set_error(error, error_capacity, "La matrice doit contenir exactement n² valeurs 0 ou 1.");
            free(adj);
            fclose(file);
            return false;
        }
        adj[i] = (uint8_t)(ch - '0');
    }

    int ch;
    while ((ch = fgetc(file)) != EOF) {
        if (!isspace((unsigned char)ch)) {
            set_error(error, error_capacity, "Le fichier contient des données après la matrice.");
            free(adj);
            fclose(file);
            return false;
        }
    }
    fclose(file);

    size_t m = 0;
    for (size_t i = 0; i < n; ++i) {
        if (adj[i * n + i] != 0) {
            set_error(error, error_capacity, "La diagonale doit être nulle (aucune boucle)." );
            free(adj);
            return false;
        }
        for (size_t j = i + 1; j < n; ++j) {
            if (adj[i * n + j] != adj[j * n + i]) {
                set_error(error, error_capacity, "La matrice doit être symétrique pour un graphe non orienté.");
                free(adj);
                return false;
            }
            if (adj[i * n + j]) {
                ++m;
            }
        }
    }

    graph->n = n;
    graph->m = m;
    graph->adj = adj;
    return true;
}

static void graph_free(Graph *graph) {
    free(graph->adj);
    graph->adj = NULL;
    graph->n = 0;
    graph->m = 0;
}

static bool coloring_is_valid(const Graph *graph, const int *colors, int color_count) {
    if (graph->n == 0) {
        return color_count == 0;
    }
    for (size_t v = 0; v < graph->n; ++v) {
        if (colors[v] < 1 || colors[v] > color_count) {
            return false;
        }
        for (size_t u = v + 1; u < graph->n; ++u) {
            if (graph->adj[v * graph->n + u] && colors[v] == colors[u]) {
                return false;
            }
        }
    }
    return true;
}

static int greedy_sequential(const Graph *graph, int **colors_out) {
    const size_t n = graph->n;
    int *colors = (int *)calloc(n == 0 ? 1 : n, sizeof(*colors));
    size_t *seen = (size_t *)calloc(n + 1, sizeof(*seen));
    if (colors == NULL || seen == NULL) {
        free(colors);
        free(seen);
        return -1;
    }

    int used = 0;
    for (size_t v = 0; v < n; ++v) {
        for (size_t u = 0; u < n; ++u) {
            if (graph->adj[v * n + u] && colors[u] > 0) {
                seen[colors[u]] = v + 1;
            }
        }
        int color = 1;
        while ((size_t)color <= n && seen[color] == v + 1) {
            ++color;
        }
        colors[v] = color;
        if (color > used) {
            used = color;
        }
    }
    free(seen);
    *colors_out = colors;
    return used;
}

static int greedy_openmp(const Graph *graph, int threads, int **colors_out) {
    const size_t n = graph->n;
    int *colors = (int *)calloc(n == 0 ? 1 : n, sizeof(*colors));
    int *forbidden = (int *)calloc(n + 1, sizeof(*forbidden));
    if (colors == NULL || forbidden == NULL) {
        free(colors);
        free(forbidden);
        return -1;
    }

    int used = 0;
#pragma omp parallel num_threads(threads) shared(colors, forbidden, used, graph, n)
    {
        for (size_t v = 0; v < n; ++v) {
            /* Tous les threads effacent le même tableau avant l'examen des voisins. */
#pragma omp single
            {
                memset(forbidden, 0, (n + 1) * sizeof(*forbidden));
            }

            /* L'ordre des sommets reste séquentiel. Seul le balayage d'une ligne est parallèle. */
#pragma omp for schedule(static)
            for (long long u = 0; u < (long long)n; ++u) {
                if (graph->adj[v * n + (size_t)u] && colors[u] > 0) {
                    const int neighbor_color = colors[u];
                    /* Plusieurs voisins peuvent interdire la même couleur : l'écriture atomique
                       rend ce partage sûr. La barrière implicite du omp for précède la lecture. */
#pragma omp atomic write
                    forbidden[neighbor_color] = 1;
                }
            }

#pragma omp single
            {
                int color = 1;
                while ((size_t)color <= n && forbidden[color]) {
                    ++color;
                }
                colors[v] = color;
                if (color > used) {
                    used = color;
                }
            }
        }
    }

    free(forbidden);
    *colors_out = colors;
    return used;
}

static bool is_safe_color(const Graph *graph, const int *colors, size_t vertex, int color) {
    for (size_t u = 0; u < graph->n; ++u) {
        if (graph->adj[vertex * graph->n + u] && colors[u] == color) {
            return false;
        }
    }
    return true;
}

static bool search_sequential(const Graph *graph, int k, size_t vertex, int *colors) {
    if (vertex == graph->n) {
        return true;
    }
    for (int color = 1; color <= k; ++color) {
        if (is_safe_color(graph, colors, vertex, color)) {
            colors[vertex] = color;
            if (search_sequential(graph, k, vertex + 1, colors)) {
                return true;
            }
            colors[vertex] = 0;
        }
    }
    return false;
}

static bool decide_sequential(const Graph *graph, int k, int **colors_out) {
    if (k < 1 && graph->n != 0) {
        return false;
    }
    int *colors = (int *)calloc(graph->n == 0 ? 1 : graph->n, sizeof(*colors));
    if (colors == NULL) {
        return false;
    }
    if (graph->n == 0 || search_sequential(graph, k, 0, colors)) {
        *colors_out = colors;
        return true;
    }
    free(colors);
    return false;
}

static bool atomic_solution_found(const ParallelSearch *search) {
    int found = 0;
    /* L'accès atomique évite les lectures concurrentes ordinaires du drapeau partagé. */
#pragma omp atomic read
    found = search->solution_found;
    return found != 0;
}

static int reserve_task_id(ParallelSearch *search) {
    int task_id = -1;
    /* Le verrou borne le nombre de tâches et transforme l'excédent de branches en calcul séquentiel. */
#pragma omp critical(task_budget)
    {
        if (search->tasks_created < MAX_OPENMP_TASKS) {
            task_id = search->tasks_created++;
        }
    }
    return task_id;
}

static void publish_solution(ParallelSearch *search, const int *colors) {
#pragma omp critical(solution_copy)
    {
        int found = 0;
#pragma omp atomic read
        found = search->solution_found;
        if (!found) {
            memcpy(search->solution, colors, search->graph->n * sizeof(*colors));
            /* critical protège le tableau ; atomic publie séparément l'état d'arrêt. */
#pragma omp atomic write
            search->solution_found = 1;
        }
    }
}

static void search_parallel(ParallelSearch *search, size_t vertex, int *colors, int depth);

static void run_task_branch(ParallelSearch *search, int *child, size_t child_vertex,
                            int child_depth, int task_id) {
    TraceEvent *event = NULL;
    if (search->tracing && child_depth == 2 && task_id >= 0) {
        event = &search->events[task_id];
        event->task_id = task_id;
        event->depth = child_depth;
        event->thread_id = omp_get_thread_num();
        event->start_s = omp_get_wtime() - search->trace_start;
    }

    search_parallel(search, child_vertex, child, child_depth);

    if (event != NULL) {
        event->end_s = omp_get_wtime() - search->trace_start;
    }
    free(child);
}

static void search_parallel(ParallelSearch *search, size_t vertex, int *colors, int depth) {
    if (atomic_solution_found(search)) {
        return;
    }
    if (vertex == search->graph->n) {
        publish_solution(search, colors);
        return;
    }

    bool created_child_tasks = false;
    for (int color = 1; color <= search->k; ++color) {
        if (atomic_solution_found(search)) {
            break;
        }
        if (!is_safe_color(search->graph, colors, vertex, color)) {
            continue;
        }

        int task_id = -1;
        if (depth < search->task_depth) {
            task_id = reserve_task_id(search);
        }
        if (task_id >= 0) {
            const size_t n = search->graph->n;
            int *child = (int *)malloc((n == 0 ? 1 : n) * sizeof(*child));
            if (child == NULL) {
                /* En cas de pression mémoire, cette branche est traitée sur le thread courant. */
                colors[vertex] = color;
                search_parallel(search, vertex + 1, colors, depth + 1);
                colors[vertex] = 0;
                continue;
            }
            memcpy(child, colors, n * sizeof(*child));
            child[vertex] = color;
            const size_t child_vertex = vertex + 1;
            const int child_depth = depth + 1;
#pragma omp task firstprivate(child, child_vertex, child_depth, task_id) shared(search)
            {
                run_task_branch(search, child, child_vertex, child_depth, task_id);
            }
            created_child_tasks = true;
        } else {
            colors[vertex] = color;
            search_parallel(search, vertex + 1, colors, depth + 1);
            colors[vertex] = 0;
        }
    }

    if (created_child_tasks) {
        /* taskwait synchronise les tâches enfants ; les accès partagés restent protégés séparément. */
#pragma omp taskwait
    }
}

static bool write_gantt_csv(const char *path, const ParallelSearch *search,
                            char *error, size_t error_capacity) {
    FILE *file = fopen(path, "w");
    if (file == NULL) {
        snprintf(error, error_capacity, "Impossible d'écrire '%s': %s", path, strerror(errno));
        return false;
    }
    fprintf(file, "task_id,depth,thread_id,start_s,end_s,duration_s\n");
    for (int i = 0; i < search->tasks_created; ++i) {
        const TraceEvent *event = &search->events[i];
        if (event->end_s >= event->start_s && event->start_s >= 0.0) {
            fprintf(file, "%d,%d,%d,%.9f,%.9f,%.9f\n", event->task_id, event->depth,
                    event->thread_id, event->start_s, event->end_s,
                    event->end_s - event->start_s);
        }
    }
    if (fclose(file) != 0) {
        set_error(error, error_capacity, "Erreur lors de la fermeture du fichier Gantt.");
        return false;
    }
    return true;
}

static bool decide_parallel(const Graph *graph, int k, int threads, int task_depth,
                            const char *gantt_path, int **colors_out,
                            char *error, size_t error_capacity) {
    if (k < 1 && graph->n != 0) {
        return false;
    }
    int *root_colors = (int *)calloc(graph->n == 0 ? 1 : graph->n, sizeof(*root_colors));
    int *solution = (int *)calloc(graph->n == 0 ? 1 : graph->n, sizeof(*solution));
    if (root_colors == NULL || solution == NULL) {
        free(root_colors);
        free(solution);
        set_error(error, error_capacity, "Mémoire insuffisante pour le backtracking parallèle.");
        return false;
    }
    if (graph->n == 0) {
        free(root_colors);
        *colors_out = solution;
        return true;
    }

    ParallelSearch search;
    memset(&search, 0, sizeof(search));
    search.graph = graph;
    search.k = k;
    search.solution = solution;
    search.task_depth = task_depth;
    search.tracing = gantt_path != NULL;
    search.error = error;
    search.error_capacity = error_capacity;
    if (search.tracing) {
        search.events = (TraceEvent *)calloc(MAX_OPENMP_TASKS, sizeof(*search.events));
        if (search.events == NULL) {
            free(root_colors);
            free(solution);
            set_error(error, error_capacity, "Mémoire insuffisante pour les événements Gantt.");
            return false;
        }
        for (int i = 0; i < MAX_OPENMP_TASKS; ++i) {
            search.events[i].start_s = -1.0;
            search.events[i].end_s = -1.0;
        }
    }

    omp_set_dynamic(0);
    search.trace_start = omp_get_wtime();
#pragma omp parallel num_threads(threads) shared(search, root_colors)
    {
#pragma omp single
        {
            search_parallel(&search, 0, root_colors, 0);
            /* Attend les descendants avant de sortir de la région single. */
#pragma omp taskwait
        }
    }

    const bool found = search.solution_found != 0;
    if (search.tracing && !write_gantt_csv(gantt_path, &search, error, error_capacity)) {
        free(search.events);
        free(root_colors);
        free(solution);
        return false;
    }
    free(search.events);
    free(root_colors);
    if (!found) {
        free(solution);
        return false;
    }
    *colors_out = solution;
    return true;
}

static bool solve_chromatic(const Graph *graph, bool parallel, int threads, int task_depth,
                            int **colors_out, int *chromatic_out,
                            char *error, size_t error_capacity) {
    if (graph->n == 0) {
        *colors_out = (int *)calloc(1, sizeof(**colors_out));
        *chromatic_out = 0;
        return *colors_out != NULL;
    }

    int *upper_colors = NULL;
    const int upper = greedy_sequential(graph, &upper_colors);
    if (upper < 0) {
        set_error(error, error_capacity, "Mémoire insuffisante pour la borne gloutonne.");
        return false;
    }

    for (int k = 1; k <= upper; ++k) {
        int *candidate = NULL;
        const bool found = parallel
            ? decide_parallel(graph, k, threads, task_depth, NULL, &candidate, error, error_capacity)
            : decide_sequential(graph, k, &candidate);
        if (found) {
            free(upper_colors);
            *colors_out = candidate;
            *chromatic_out = k;
            return true;
        }
        if (error != NULL && error_capacity > 0 && error[0] != '\0') {
            free(upper_colors);
            return false;
        }
    }

    /* La coloration gloutonne valide garantit l'arrêt à la borne supérieure. */
    *colors_out = upper_colors;
    *chromatic_out = upper;
    return true;
}

static void free_result(SolveResult *result) {
    free(result->colors);
    memset(result, 0, sizeof(*result));
}

static bool solve_once(const Graph *graph, const char *mode, int threads, int task_depth,
                       bool has_k, int requested_k, SolveResult *result,
                       char *error, size_t error_capacity) {
    memset(result, 0, sizeof(*result));
    const bool is_parallel = strcmp(mode, "greedy-omp") == 0 || strcmp(mode, "exact-omp") == 0;
    const bool is_exact = strcmp(mode, "exact-seq") == 0 || strcmp(mode, "exact-omp") == 0;
    if (has_k && !is_exact) {
        set_error(error, error_capacity, "L'option --k est réservée aux modes exact-seq et exact-omp.");
        return false;
    }

    if (has_k) {
        result->decision_mode = true;
        result->colorable = is_parallel
            ? decide_parallel(graph, requested_k, threads, task_depth, NULL, &result->colors,
                              error, error_capacity)
            : decide_sequential(graph, requested_k, &result->colors);
        if (!result->colorable && error != NULL && error_capacity > 0 && error[0] != '\0') {
            return false;
        }
        result->chromatic_number = requested_k;
        return true;
    }

    result->decision_mode = false;
    if (strcmp(mode, "greedy-seq") == 0) {
        result->chromatic_number = greedy_sequential(graph, &result->colors);
    } else if (strcmp(mode, "greedy-omp") == 0) {
        result->chromatic_number = greedy_openmp(graph, threads, &result->colors);
    } else {
        result->colorable = solve_chromatic(graph, is_parallel, threads, task_depth,
                                            &result->colors, &result->chromatic_number,
                                            error, error_capacity);
        return result->colorable;
    }
    result->colorable = result->chromatic_number >= 0;
    if (!result->colorable) {
        set_error(error, error_capacity, "Mémoire insuffisante pendant le coloriage glouton.");
        return false;
    }
    return true;
}

static bool write_trace_after_solve(const Graph *graph, int chromatic_number,
                                    const char *path, int threads,
                                    char *error, size_t error_capacity) {
    int trace_k = chromatic_number > 1 ? chromatic_number - 1 : 1;
    int *discard = NULL;
    bool found = decide_parallel(graph, trace_k, threads, 2, path, &discard, error, error_capacity);
    free(discard);
    if (error != NULL && error_capacity > 0 && error[0] != '\0') {
        return false;
    }
    (void)found;
    return true;
}

static bool parse_positive_int(const char *text, int minimum, int maximum, int *value) {
    char *end = NULL;
    errno = 0;
    long parsed = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed < minimum || parsed > maximum) {
        return false;
    }
    *value = (int)parsed;
    return true;
}

static void print_usage(const char *program) {
    fprintf(stderr,
        "Usage: %s GRAPH MODE [--threads N] [--task-depth 1..4] [--repeat N] [--batch N] [--warmup N] [--k K] [--gantt CSV]\n"
        "Modes: greedy-seq, greedy-omp, exact-seq, exact-omp\n",
        program);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 2;
    }

    const char *graph_path = argv[1];
    const char *mode = argv[2];
    if (strcmp(mode, "greedy-seq") != 0 && strcmp(mode, "greedy-omp") != 0 &&
        strcmp(mode, "exact-seq") != 0 && strcmp(mode, "exact-omp") != 0) {
        print_usage(argv[0]);
        return 2;
    }

    int threads = 1;
    int task_depth = DEFAULT_TASK_DEPTH;
    int repeat = 1;
    int batch = 1;
    int warmup = 0;
    int requested_k = 0;
    bool has_k = false;
    const char *gantt_path = NULL;
    for (int i = 3; i < argc; ++i) {
        if (strcmp(argv[i], "--threads") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 1, 256, &threads)) {
                fprintf(stderr, "--threads doit être compris entre 1 et 256.\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--task-depth") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 1, 4, &task_depth)) {
                fprintf(stderr, "--task-depth doit être compris entre 1 et 4.\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--repeat") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 1, 100, &repeat)) {
                fprintf(stderr, "--repeat doit être compris entre 1 et 100.\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--batch") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 1, 1000000, &batch)) {
                fprintf(stderr, "--batch doit être compris entre 1 et 1000000.\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--warmup") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 0, 20, &warmup)) {
                fprintf(stderr, "--warmup doit être compris entre 0 et 20.\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--k") == 0 && i + 1 < argc) {
            if (!parse_positive_int(argv[++i], 1, INT_MAX, &requested_k)) {
                fprintf(stderr, "--k doit être un entier positif.\n");
                return 2;
            }
            has_k = true;
        } else if (strcmp(argv[i], "--gantt") == 0 && i + 1 < argc) {
            gantt_path = argv[++i];
        } else {
            fprintf(stderr, "Option inconnue ou sans valeur: %s\n", argv[i]);
            print_usage(argv[0]);
            return 2;
        }
    }
    if (gantt_path != NULL && (strcmp(mode, "exact-omp") != 0 || has_k)) {
        fprintf(stderr, "--gantt exige exact-omp sans option --k.\n");
        return 2;
    }

    Graph graph = {0, 0, NULL};
    char error[512] = {0};
    if (!graph_load(graph_path, &graph, error, sizeof(error))) {
        fprintf(stderr, "%s\n", error);
        return 1;
    }

    double *times = (double *)calloc((size_t)repeat, sizeof(*times));
    if (times == NULL) {
        fprintf(stderr, "Mémoire insuffisante pour les mesures.\n");
        graph_free(&graph);
        return 1;
    }

    omp_set_dynamic(0);
    SolveResult last = {0};
    for (int i = 0; i < warmup; ++i) {
        SolveResult warm_batch = {0};
        for (int b = 0; b < batch; ++b) {
            SolveResult warm = {0};
            error[0] = '\0';
            if (!solve_once(&graph, mode, threads, task_depth, has_k, requested_k,
                            &warm, error, sizeof(error))) {
                fprintf(stderr, "Échauffement: %s\n", error[0] ? error : "échec du solveur");
                free_result(&warm);
                free_result(&warm_batch);
                free(times);
                graph_free(&graph);
                return 1;
            }
            free_result(&warm_batch);
            warm_batch = warm;
        }
        free_result(&warm_batch);
    }

    for (int i = 0; i < repeat; ++i) {
        SolveResult batch_last = {0};
        const double start = omp_get_wtime();
        for (int b = 0; b < batch; ++b) {
            SolveResult current = {0};
            error[0] = '\0';
            if (!solve_once(&graph, mode, threads, task_depth, has_k, requested_k,
                            &current, error, sizeof(error))) {
                fprintf(stderr, "Calcul: %s\n", error[0] ? error : "échec du solveur");
                free_result(&current);
                free_result(&batch_last);
                free_result(&last);
                free(times);
                graph_free(&graph);
                return 1;
            }
            free_result(&batch_last);
            batch_last = current;
        }
        times[i] = (omp_get_wtime() - start) / (double)batch;
        free_result(&last);
        last = batch_last;
    }

    if (gantt_path != NULL && !write_trace_after_solve(&graph, last.chromatic_number,
                                                        gantt_path, threads, error, sizeof(error))) {
        fprintf(stderr, "%s\n", error[0] ? error : "Échec de la journalisation Gantt.");
        free_result(&last);
        free(times);
        graph_free(&graph);
        return 1;
    }

    printf("{\"mode\":\"%s\",\"vertices\":%zu,\"edges\":%zu,", mode, graph.n, graph.m);
    if (has_k) {
        printf("\"k\":%d,\"colorable\":%s,", requested_k,
               last.colorable ? "true" : "false");
        if (last.colorable) {
            printf("\"solution_valid\":%s,\"colors\":[",
                   coloring_is_valid(&graph, last.colors, requested_k) ? "true" : "false");
        } else {
            printf("\"solution_valid\":null,\"colors\":null");
        }
    } else {
        printf("\"chromatic_number\":%d,\"solution_valid\":%s,\"colors\":[",
               last.chromatic_number,
               coloring_is_valid(&graph, last.colors, last.chromatic_number) ? "true" : "false");
    }
    if (last.colors != NULL) {
        for (size_t i = 0; i < graph.n; ++i) {
            printf("%s%d", i == 0 ? "" : ",", last.colors[i]);
        }
        printf("]");
    }
    printf(",\"seconds\":[");
    for (int i = 0; i < repeat; ++i) {
        printf("%s%.9f", i == 0 ? "" : ",", times[i]);
    }
    printf("],\"threads\":%d,\"task_depth\":%d,\"batch\":%d}\n", threads, task_depth, batch);

    free_result(&last);
    free(times);
    graph_free(&graph);
    return 0;
}
