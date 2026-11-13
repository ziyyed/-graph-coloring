const C = {
  bg: "#F5F6F3",
  ink: "#172A3A",
  muted: "#63717D",
  teal: "#0B7A75",
  orange: "#D77A46",
  green: "#5A9B75",
  violet: "#8B6AAE",
  red: "#C14953",
  pale: "#E7ECEF",
  line: "#CBD4D8",
  white: "#FFFFFF",
  navy: "#263648",
};

const COLOR = { 1: C.teal, 2: C.orange, 3: C.green, 4: C.violet, 5: C.red, 6: "#4D7C8A", 7: "#9A7B4F" };
const FONT = "Aptos";

function addText(slide, left, top, width, height, text, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: options.name,
    position: { left, top, width, height },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: options.typeface ?? FONT,
    fontSize: options.size ?? 24,
    bold: options.bold ?? false,
    italic: options.italic ?? false,
    color: options.color ?? C.ink,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "middle",
    autoFit: "shrinkText",
    wrap: "square",
    insets: options.insets ?? 0,
  };
  return shape;
}

function addRect(slide, left, top, width, height, fill, options = {}) {
  return slide.shapes.add({
    geometry: options.geometry ?? "rect",
    name: options.name,
    position: { left, top, width, height, rotation: options.rotation ?? 0 },
    fill,
    line: { style: "solid", fill: options.line ?? fill, width: options.lineWidth ?? 0 },
  });
}

function addBase(presentation, title, number, section = "COLORIAGE DE GRAPHES") {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  addText(slide, 72, 28, 540, 22, section, { size: 14, bold: true, color: C.teal });
  addText(slide, 72, 56, 1136, 58, title, { size: 42, bold: true, color: C.ink });
  addRect(slide, 72, 126, 1136, 2, C.line);
  addText(slide, 72, 682, 850, 20, "Complexité algorithmique  |  Calcul parallèle et distribué", { size: 13, color: C.muted });
  addText(slide, 1150, 682, 58, 20, String(number).padStart(2, "0"), { size: 13, color: C.muted, align: "right" });
  return slide;
}

function addNotes(slide, text) {
  slide.speakerNotes.text = text;
}

function drawGraph(slide, { labels, edges, colors, left, top, width, height, radius, nodeSize = 66, fontSize = 17 }) {
  const cx = left + width / 2;
  const cy = top + height / 2;
  const r = radius ?? Math.min(width, height) * 0.36;
  const points = labels.map((_, i) => {
    const angle = -Math.PI / 2 + 2 * Math.PI * i / labels.length;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
  for (const [u, v] of edges) {
    const a = points[u], b = points[v];
    const dx = b.x - a.x, dy = b.y - a.y;
    const length = Math.sqrt(dx * dx + dy * dy) - nodeSize * 0.72;
    const angle = Math.atan2(dy, dx) * 180 / Math.PI;
    addRect(slide, (a.x + b.x) / 2 - length / 2, (a.y + b.y) / 2 - 2,
      Math.max(1, length), 4, C.muted, { rotation: angle });
  }
  labels.forEach((label, i) => {
    const p = points[i];
    const node = slide.shapes.add({
      geometry: "ellipse",
      name: `sommet-${label}`,
      position: { left: p.x - nodeSize / 2, top: p.y - nodeSize / 2, width: nodeSize, height: nodeSize },
      fill: COLOR[colors[i]] ?? C.teal,
      line: { style: "solid", fill: C.white, width: 2 },
    });
    node.text = label;
    node.text.style = { typeface: FONT, fontSize, bold: true, color: C.white,
      alignment: "center", verticalAlignment: "middle", autoFit: "shrinkText", insets: 2 };
  });
}

function addTable(slide, values, position, columnWidths = undefined) {
  const rows = values.length;
  const columns = values[0].length;
  const table = slide.tables.add({
    rows, columns,
    left: position.left, top: position.top, width: position.width, height: position.height,
    values,
    ...(columnWidths ? { columnWidths } : {}),
  });
  table.borders.assign({ style: "solid", fill: C.line, width: 1 });
  const header = table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: columns });
  header.fill = C.navy;
  header.textStyle.color = C.white;
  header.textStyle.fontSize = 17;
  header.textStyle.bold = true;
  header.textStyle.alignment = "center";
  for (let row = 1; row < rows; row++) {
    const range = table.cells.block({ row, column: 0, rowCount: 1, columnCount: columns });
    range.fill = row % 2 === 0 ? "#EDF2F3" : C.white;
    range.textStyle.color = C.ink;
    range.textStyle.fontSize = 16;
  }
  return table;
}

function summaryRow(rows, graph, mode, threads) {
  return rows.find(row => row.graph === graph && row.mode === mode && Number(row.threads) === threads);
}

function formatSeconds(value) {
  return Number(value).toFixed(3).replace(".", ",");
}

function lineChart(slide, { left, top, width, height, categories, series, yFormat = "0.00" }) {
  return slide.charts.add("line", {
    position: { left, top, width, height },
    categories,
    series: series.map(item => ({
      name: item.name,
      values: item.values,
      line: { style: item.dash ?? "solid", fill: item.color, width: item.width ?? 3 },
      marker: { symbol: "circle", size: 6, fill: item.color },
    })),
    lineOptions: { smooth: false },
    hasLegend: true,
    legend: { position: "bottom", overlay: false },
    chartFill: C.bg,
    plotAreaFill: C.bg,
    chartLine: { style: "solid", fill: C.bg, width: 0 },
    xAxis: {
      textStyle: { typeface: FONT, fontSize: 14, fill: C.muted },
      line: { style: "solid", fill: C.line, width: 1 },
    },
    yAxis: {
      numberFormatCode: yFormat,
      textStyle: { typeface: FONT, fontSize: 13, fill: C.muted },
      majorGridlines: { style: "solid", fill: C.pale, width: 1 },
      line: { style: "solid", fill: C.line, width: 1 },
    },
  });
}

function addGraphDrawing(slide, { labels, edges, colors, left, top, width, height, radius, nodeSize, fontSize }) {
  drawGraph(slide, { labels, edges, colors, left, top, width, height, radius, nodeSize, fontSize });
}

function exactTables(slide) {
  addTable(slide, [
    ["Algorithme", "Meilleur", "Moyen observé", "Pire", "Mémoire auxiliaire"],
    ["Glouton, matrice", "Θ(n²)", "Θ(n²)", "Θ(n²)", "O(n)"],
    ["Décision à K couleurs", "Θ(n) si échec rapide", "moyenne sur G(n, 0,45)", "O(n Kⁿ)", "O(n) + pile O(n)"],
    ["Recherche de χ(G)", "Θ(n²) si χ=1", "mesures par taille", "O(n Σ kⁿ), k=1..χ", "O(n) + pile O(n)"],
    ["Exact OpenMP", "selon l'arbre", "mesures par thread", "ordre exponentiel", "O(n) par copie active"],
  ], { left: 72, top: 185, width: 1136, height: 330 });
  addText(slide, 76, 550, 1120, 88,
    "n = |V|, m = |E|. La matrice occupe Θ(n²). Le glouton lit toute ligne pour chaque sommet, même si m = 0. Au backtracking, chaque nœud a jusqu'à K choix et le contrôle balaie jusqu'à n cases. Un échec rapide coûte Θ(n); une solution à K=1 peut demander Θ(n²).",
    { size: 22, color: C.ink });
}

function addGantt(slide, events) {
  const threads = [...new Set(events.map(e => Number(e.thread_id)))].sort((a, b) => a - b);
  const total = Math.max(...events.map(e => Number(e.end_s)));
  const x0 = 150, chartWidth = 930, y0 = 210, rowGap = 86, barHeight = 38;
  addText(slide, 82, 156, 1120, 34,
    "G36, K = 6, 4 threads. Le traçage séparé journalise les tâches feuilles créées au niveau 2.",
    { size: 20, color: C.muted });
  threads.forEach((thread, index) => {
    const y = y0 + index * rowGap;
    addText(slide, 72, y - 2, 70, 36, `T${thread}`, { size: 19, bold: true, color: C.ink });
    addRect(slide, x0, y, chartWidth, barHeight, C.pale);
    for (const event of events.filter(e => Number(e.thread_id) === thread)) {
      const start = Number(event.start_s), end = Number(event.end_s);
      const width = Math.max(2, (end - start) / total * chartWidth);
      const x = x0 + start / total * chartWidth;
      addRect(slide, x, y + 3, width, barHeight - 6, C.teal, { line: C.white, lineWidth: 1 });
      if (width > 34) {
        addText(slide, x, y + 3, width, barHeight - 6, `T${event.task_id}`,
          { size: 13, bold: true, color: C.white, align: "center" });
      }
    }
  });
  const axisY = y0 + threads.length * rowGap - 20;
  addRect(slide, x0, axisY, chartWidth, 2, C.muted);
  addText(slide, x0 - 8, axisY + 6, 100, 25, "0 s", { size: 14, color: C.muted });
  addText(slide, x0 + chartWidth - 120, axisY + 6, 120, 25, `${total.toFixed(3)} s`, { size: 14, color: C.muted, align: "right" });
  addRect(slide, 150, 640, 20, 14, C.teal);
  addText(slide, 180, 632, 235, 28, "Tâche exécutée", { size: 16, color: C.muted });
  addRect(slide, 430, 640, 20, 14, C.pale);
  addText(slide, 460, 632, 650, 28, "Aucune tâche feuille journalisée, attente comprise", { size: 16, color: C.muted });
}

export function buildDeck(presentation, data) {
  const { summary, exactSelection, exactManifest, greedyManifest, events } = data;
  const exactLargest = exactSelection.reduce((a, b) => a.n > b.n ? a : b);
  const exactName = exactLargest.name;
  const greedyLargest = greedyManifest.reduce((a, b) => a.n > b.n ? a : b);
  const greedyName = greedyLargest.name;
  const threadCategories = ["1", "2", "4", "8"];
  const sourceGeneral = "Sources : sujet de projet « Le problème du coloriage de graphes », sections 1 à 11 ; fiche d'évaluation générale.";
  const sourceComplexity = "Sources : sujet de projet, sections 6 à 8 ; fiche d'évaluation de Complexité algorithmique.";
  const sourceParallel = "Sources : sujet de projet, section 9 ; fiche d'évaluation de Calcul parallèle et distribué.";

  // 1. Minimal cover.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.bg;
    addRect(slide, 82, 116, 7, 420, C.teal);
    addText(slide, 124, 154, 930, 30, "PROJET UNIVERSITAIRE", { size: 16, bold: true, color: C.teal });
    addText(slide, 124, 224, 1020, 142, "Le coloriage\nde graphes", { size: 62, bold: true, color: C.ink });
    addText(slide, 124, 402, 990, 48, "Complexité algorithmique et parallélisation OpenMP", { size: 26, color: C.muted });
    addRect(slide, 124, 514, 500, 2, C.line);
    addText(slide, 124, 542, 900, 50, "Implémentations, analyse et étude expérimentale", { size: 21, color: C.ink });
    addText(slide, 124, 614, 1080, 28, "Zied Chouk  ·  Chayma Hakouna  ·  Wirak", { size: 17, color: C.muted });
    addNotes(slide, `Présentation de projet. ${sourceGeneral}`);
  }

  // 2. Problem statement.
  {
    const slide = addBase(presentation, "Colorier sous contraintes", 2);
    addText(slide, 92, 176, 480, 40, "Le modèle", { size: 27, bold: true, color: C.teal });
    addText(slide, 92, 228, 480, 168,
      "Un sommet représente un objet.\nUne arête représente une incompatibilité.\nUne couleur représente une ressource ou un créneau.",
      { size: 26, color: C.ink });
    addRect(slide, 626, 176, 2, 395, C.line);
    addText(slide, 676, 176, 480, 40, "Deux objectifs distincts", { size: 27, bold: true, color: C.teal });
    addText(slide, 676, 228, 470, 128,
      "Coloration valide\nAucune arête ne relie deux sommets de même couleur.",
      { size: 24, color: C.ink });
    addText(slide, 676, 390, 470, 132,
      "Coloration optimale\nElle utilise le minimum de couleurs : χ(G).",
      { size: 24, color: C.ink });
    addText(slide, 92, 572, 1060, 54,
      "La décision « G est-il coloriable avec K couleurs ? » est NP-complète pour K ≥ 3.",
      { size: 22, bold: true, color: C.orange });
    addNotes(slide, `Définir G=(V,E), sommets adjacents, coloration propre, graphe complet, degré et nombre chromatique. Distinguer la décision à K couleurs de l'optimisation. ${sourceGeneral}`);
  }

  // 3. Five-cycle graph.
  {
    const slide = addBase(presentation, "Exemple théorique : le cycle C₅", 3);
    addText(slide, 82, 180, 390, 150,
      "V = {v₁, v₂, v₃, v₄, v₅}\n\nE = {(v₁,v₂), (v₂,v₃), (v₃,v₄), (v₄,v₅), (v₅,v₁)}",
      { size: 21, color: C.ink });
    addText(slide, 82, 420, 370, 94, "Coloration valide :\n(1, 2, 1, 2, 3)", { size: 25, bold: true, color: C.teal });
    addGraphDrawing(slide, {
      labels: ["v₁", "v₂", "v₃", "v₄", "v₅"],
      edges: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]],
      colors: [1, 2, 1, 2, 3], left: 560, top: 160, width: 590, height: 460, radius: 178, nodeSize: 72,
    });
    addText(slide, 900, 606, 220, 38, "χ(C₅) = 3", { size: 26, bold: true, color: C.ink, align: "center" });
    addNotes(slide, `Le cycle impair ne peut pas être colorié avec deux couleurs. La coloration affichée utilise trois couleurs, donc elle est optimale. ${sourceGeneral}`);
  }

  // 4. Greedy trace.
  {
    const slide = addBase(presentation, "Trace gloutonne sur C₅", 4);
    addTable(slide, [
      ["Sommet", "Couleurs déjà prises par les voisins", "Choix"],
      ["v₁", "aucune", "1"],
      ["v₂", "1", "2"],
      ["v₃", "2", "1"],
      ["v₄", "1", "2"],
      ["v₅", "1 et 2", "3"],
    ], { left: 82, top: 174, width: 1110, height: 360 }, [150, 720, 180]);
    addText(slide, 92, 568, 1090, 58,
      "Optimalité : un cycle impair n'est pas biparti. Deux couleurs échouent, trois suffisent.",
      { size: 22, bold: true, color: C.teal });
    addNotes(slide, `Cette trace est distincte de l'exemple réel d'emploi du temps présenté plus loin. Elle sert à illustrer l'ordre de parcours et la preuve d'optimalité. ${sourceGeneral}`);
  }

  // 5. Greedy method.
  {
    const slide = addBase(presentation, "Méthode gloutonne", 5);
    addText(slide, 86, 174, 505, 48, "Choix local", { size: 28, bold: true, color: C.teal });
    addText(slide, 86, 230, 505, 276,
      "1. Parcourir les sommets dans l'ordre fixé.\n\n2. Examiner les couleurs des voisins déjà traités.\n\n3. Affecter la plus petite couleur disponible.",
      { size: 23, color: C.ink });
    addRect(slide, 640, 178, 2, 380, C.line);
    addText(slide, 690, 176, 490, 54, "Garantie et limite", { size: 27, bold: true, color: C.teal });
    addText(slide, 690, 238, 468, 190,
      "Chaque étape respecte les arêtes déjà traitées.\n\nLe résultat est valide. Son nombre de couleurs dépend de l'ordre et peut dépasser χ(G).",
      { size: 23, color: C.ink });
    addText(slide, 690, 474, 450, 46, "Temps avec matrice : Θ(n²)", { size: 26, bold: true, color: C.orange });
    addNotes(slide, `La matrice impose un parcours complet des n voisins potentiels pour chacun des n sommets. La complexité reste quadratique même lorsque le graphe ne contient aucune arête. ${sourceComplexity}`);
  }

  // 6. Exact method.
  {
    const slide = addBase(presentation, "Retour sur trace", 6);
    addText(slide, 82, 175, 515, 50, "Décider pour une valeur de K", { size: 27, bold: true, color: C.teal });
    addText(slide, 82, 230, 510, 300,
      "Essayer une couleur au sommet courant.\n\nSi aucun voisin n'a cette couleur, descendre d'un niveau.\n\nSi toutes les couleurs échouent, annuler l'affectation et remonter.",
      { size: 23, color: C.ink });
    addRect(slide, 632, 180, 2, 378, C.line);
    addText(slide, 680, 176, 470, 52, "Recherche de χ(C₅)", { size: 27, bold: true, color: C.teal });
    addText(slide, 680, 242, 470, 244,
      "K = 1 : échec, car une arête impose deux couleurs.\n\nK = 2 : les contraintes du cycle impair épuisent les branches.\n\nK = 3 : une solution existe.",
      { size: 22, color: C.ink });
    addText(slide, 680, 510, 470, 52, "χ(C₅) = 3", { size: 28, bold: true, color: C.orange });
    addNotes(slide, `Une solution trouvée à K ne prouve pas à elle seule la minimalité. On teste les K croissants ; l'échec pour K=1 et K=2, puis la réussite à K=3, certifient χ(C₅)=3. Le glouton borne supérieurement la recherche. ${sourceComplexity}`);
  }

  // 7. Complexity.
  {
    const slide = addBase(presentation, "Complexité avec matrice d'adjacence", 7);
    exactTables(slide);
    addNotes(slide, `Pour le cas moyen, préciser la distribution utilisée. Il n'existe pas une borne moyenne serrée qui s'applique à toutes les distributions de graphes. Le rapport mesure les instances G(n,p) et répète les exécutions. ${sourceComplexity}`);
  }

  // 8. Parallel greedy.
  {
    const slide = addBase(presentation, "Glouton OpenMP", 8);
    addText(slide, 82, 170, 1090, 44, "La dépendance entre sommets conserve l'ordre externe séquentiel.", { size: 24, bold: true, color: C.ink });
    const xs = [92, 475, 858];
    const labels = [
      ["Sommet v", "état précédent"],
      ["Voisins de v", "balayage omp for"],
      ["Couleur", "single après barrière"],
    ];
    labels.forEach((pair, i) => {
      addText(slide, xs[i], 290, 260, 44, pair[0], { size: 25, bold: true, color: C.teal, align: "center" });
      addText(slide, xs[i], 344, 260, 86, pair[1], { size: 20, color: C.muted, align: "center" });
      if (i < 2) addRect(slide, xs[i] + 290, 328, 70, 3, C.orange);
    });
    addText(slide, 82, 476, 1090, 86,
      "Le tableau forbidden est partagé. Les marques utilisent atomic write ; la barrière implicite garantit que single lit les couleurs interdites après les voisins.",
      { size: 22, color: C.ink });
    addNotes(slide, `La version parallèle n'affecte pas plusieurs sommets simultanément. Les couleurs des voisins viennent d'étapes précédentes et déterminent la couleur du sommet courant. Les atomic write empêchent les écritures concurrentes ordinaires dans forbidden. ${sourceParallel}`);
  }

  // 9. Tasks and synchronization.
  {
    const slide = addBase(presentation, "Backtracking parallèle avec tâches", 9);
    const nodes = [
      [640, 205, "État racine"], [420, 330, "Couleur 1"], [640, 330, "Couleur 2"], [860, 330, "Couleur 3"],
      [360, 470, "Sous-arbre"], [520, 470, "Sous-arbre"], [690, 470, "Sous-arbre"], [850, 470, "Sous-arbre"], [1010, 470, "Sous-arbre"],
    ];
    const links = [[0,1],[0,2],[0,3],[1,4],[1,5],[2,6],[2,7],[3,8]];
    for (const [a, b] of links) {
      const [x1,y1] = nodes[a], [x2,y2] = nodes[b];
      const dx = x2-x1, dy = y2-y1, length = Math.sqrt(dx*dx+dy*dy);
      addRect(slide, (x1+x2)/2-length/2, (y1+y2)/2-1, length, 2, C.line, { rotation: Math.atan2(dy,dx)*180/Math.PI });
    }
    nodes.forEach(([x,y,label], i) => {
      const color = i === 0 ? C.navy : (i < 4 ? C.teal : C.white);
      const shape = slide.shapes.add({ geometry: "ellipse", position: { left: x-58, top: y-31, width: 116, height: 62 }, fill: color,
        line: { style: "solid", fill: i < 4 ? color : C.line, width: 1 } });
      shape.text = label;
      shape.text.style = { typeface: FONT, fontSize: 16, bold: true, color: i < 4 ? C.white : C.ink, alignment: "center", verticalAlignment: "middle", autoFit: "shrinkText", insets: 3 };
    });
    addText(slide, 82, 550, 1080, 88,
      "Graphe partagé en lecture seule. Chaque tâche possède son tableau de couleurs. atomic lit et publie solution_found ; critical copie la solution. taskwait termine les enfants.",
      { size: 20, color: C.ink });
    addNotes(slide, `parallel crée l'équipe, single lance la racine, task distribue les branches et taskwait attend les enfants. L'état de coloration n'est jamais partagé entre branches. La profondeur et le plafond du nombre de tâches limitent l'ordonnancement. ${sourceParallel}`);
  }

  // 10. Real-world example.
  {
    const slide = addBase(presentation, "Application réelle : emploi du temps", 10);
    addGraphDrawing(slide, {
      // Short labels stay legible inside the fixed-size graph nodes; full names
      // are defined in the speaker notes and the accompanying exam table.
      labels: ["Algo", "BD", "Syst.", "Maths", "Réseau", "IA"],
      edges: [[0,1],[0,2],[1,2],[1,3],[2,4],[3,5],[4,5]],
      colors: [1,2,3,1,1,2], left: 72, top: 155, width: 640, height: 470, radius: 175, nodeSize: 84, fontSize: 14,
    });
    addText(slide, 738, 178, 410, 46, "Trois créneaux", { size: 28, bold: true, color: C.teal });
    addTable(slide, [
      ["Créneau", "Examens"],
      ["1", "Algo, Maths, Réseaux"],
      ["2", "BD, IA"],
      ["3", "Systèmes"],
    ], { left: 738, top: 240, width: 420, height: 250 }, [115, 300]);
    addText(slide, 738, 526, 410, 80, "Chaque arête relie deux examens qui partagent un étudiant.", { size: 19, color: C.muted });
    addNotes(slide, `Les six sommets sont Algorithmique, Bases de données, Systèmes d'exploitation, Mathématiques, Réseaux et Intelligence artificielle. La matrice contient 7 conflits. Une couleur représente un créneau. ${sourceGeneral}`);
  }

  // 11. Experiment setup.
  {
    const slide = addBase(presentation, "Protocole expérimental", 11);
    addTable(slide, [
      ["Famille", "Tailles retenues", "Densité cible", "Graine"],
      ["Exact, G(n,p)", exactSelection.map(x => x.n).join(", "), "0,45", "20261108"],
      ["Glouton, G(n,p)", greedyManifest.map(x => x.n).join(", "), "0,10", "20261109"],
    ], { left: 82, top: 188, width: 1110, height: 210 }, [250, 470, 170, 170]);
    addText(slide, 94, 450, 1060, 132,
      "1 échauffement puis 5 répétitions.\nThreads : 1, 2, 4 et 8.\nLes graphes sont chargés une fois ; un lot amortit la granularité de l'horloge sur les petits cas.",
      { size: 23, color: C.ink });
    addText(slide, 94, 606, 1060, 36,
      "Phases : analyse → versions séquentielles → OpenMP → expériences et Gantt → synthèse.",
      { size: 18, color: C.muted });
    addNotes(slide, `Les exacts sont calibrés par exécution séquentielle sous 60 secondes. Les mesures utilisent les mêmes instances pour chaque nombre de threads. Le chargement et la validation sont hors chronométrage. Le lot est répété sur le graphe déjà chargé et le temps est divisé par la taille du lot. ${sourceParallel}`);
  }

  // 12. Runtime chart pair.
  {
    const slide = addBase(presentation, "Temps moyen selon le nombre de threads", 12);
    addText(slide, 78, 152, 530, 34, `Glouton, ${greedyName}`, { size: 22, bold: true, color: C.teal, align: "center" });
    addText(slide, 668, 152, 530, 34, `Backtracking, ${exactName}`, { size: 22, bold: true, color: C.orange, align: "center" });
    const greedySequential = Number(summaryRow(summary, greedyName, "greedy-seq", 1).mean_seconds);
    const greedyParallel = [1,2,4,8].map(p => Number(summaryRow(summary, greedyName, "greedy-omp", p).mean_seconds));
    const exactSequential = Number(summaryRow(summary, exactName, "exact-seq", 1).mean_seconds);
    const exactParallel = [1,2,4,8].map(p => Number(summaryRow(summary, exactName, "exact-omp", p).mean_seconds));
    lineChart(slide, { left: 52, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "OpenMP", values: greedyParallel, color: C.teal }], yFormat: "0.000" });
    lineChart(slide, { left: 654, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "OpenMP", values: exactParallel, color: C.orange }], yFormat: "0.000" });
    addText(slide, 62, 600, 540, 32,
      `Référence séquentielle : ${formatSeconds(greedySequential)} s`,
      { size: 17, color: C.muted, align: "center" });
    addText(slide, 662, 600, 540, 32,
      `Référence séquentielle : ${formatSeconds(exactSequential)} s`,
      { size: 17, color: C.muted, align: "center" });
    addNotes(slide, `Le glouton parallèle est plus lent que sa base séquentielle sur cette machine, car la boucle externe reste séquentielle et chaque sommet introduit des synchronisations. Le backtracking accélère sur les tailles retenues. Les résultats sont les moyennes des répétitions. ${sourceParallel}`);
  }

  // 13. Speedup.
  {
    const slide = addBase(presentation, "Accélération parallèle", 13);
    addText(slide, 78, 152, 530, 34, `Glouton, ${greedyName}`, { size: 22, bold: true, color: C.teal, align: "center" });
    addText(slide, 668, 152, 530, 34, `Backtracking, ${exactName}`, { size: 22, bold: true, color: C.orange, align: "center" });
    const ideal = [1,2,4,8];
    const greedyS = ideal.map(p => Number(summaryRow(summary, greedyName, "greedy-omp", p).speedup_vs_sequential));
    const exactS = ideal.map(p => Number(summaryRow(summary, exactName, "exact-omp", p).speedup_vs_sequential));
    lineChart(slide, { left: 52, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "Mesuré", values: greedyS, color: C.teal }, { name: "Idéal", values: ideal, color: C.navy, dash: "dashed", width: 2 }], yFormat: "0.0" });
    lineChart(slide, { left: 654, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "Mesuré", values: exactS, color: C.orange }, { name: "Idéal", values: ideal, color: C.navy, dash: "dashed", width: 2 }], yFormat: "0.0" });
    addText(slide, 82, 605, 1100, 36, "Speedup : S(p) = Tₛ / Tₚ", { size: 21, bold: true, color: C.ink, align: "center" });
    addNotes(slide, `L'accélération idéale est S(p)=p. Les calculs utilisent les temps moyens du séquentiel et de la variante OpenMP de chaque graphe. ${sourceParallel}`);
  }

  // 14. Efficiency.
  {
    const slide = addBase(presentation, "Efficacité parallèle", 14);
    addText(slide, 78, 152, 530, 34, `Glouton, ${greedyName}`, { size: 22, bold: true, color: C.teal, align: "center" });
    addText(slide, 668, 152, 530, 34, `Backtracking, ${exactName}`, { size: 22, bold: true, color: C.orange, align: "center" });
    const greedyE = [1,2,4,8].map(p => Number(summaryRow(summary, greedyName, "greedy-omp", p).efficiency));
    const exactE = [1,2,4,8].map(p => Number(summaryRow(summary, exactName, "exact-omp", p).efficiency));
    lineChart(slide, { left: 52, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "Mesurée", values: greedyE, color: C.teal }, { name: "Efficacité idéale", values: [1,1,1,1], color: C.navy, dash: "dashed", width: 2 }], yFormat: "0.0" });
    lineChart(slide, { left: 654, top: 190, width: 560, height: 400, categories: threadCategories,
      series: [{ name: "Mesurée", values: exactE, color: C.orange }, { name: "Efficacité idéale", values: [1,1,1,1], color: C.navy, dash: "dashed", width: 2 }], yFormat: "0.0" });
    addText(slide, 82, 605, 1100, 36, "Efficacité : E(p) = S(p) / p", { size: 21, bold: true, color: C.ink, align: "center" });
    addNotes(slide, `Une efficacité supérieure à 1 peut apparaître à cause des variations de mesure, d'une meilleure répartition de la recherche ou de la granularité des lots. Elle ne signifie pas une efficacité physique supérieure à 100 % au sens absolu. ${sourceParallel}`);
  }

  // 15. Scaling.
  {
    const slide = addBase(presentation, "Temps selon la taille du graphe", 15);
    addText(slide, 78, 152, 530, 34, "Glouton : p=1 et OpenMP p=4", { size: 22, bold: true, color: C.teal, align: "center" });
    addText(slide, 668, 152, 530, 34, "Backtracking : p=1 et OpenMP p=4", { size: 22, bold: true, color: C.orange, align: "center" });
    const greedySeq = greedyManifest.map(x => Number(summaryRow(summary, x.name, "greedy-seq", 1).mean_seconds));
    const greedyOmp = greedyManifest.map(x => Number(summaryRow(summary, x.name, "greedy-omp", 4).mean_seconds));
    const greedyCats = greedyManifest.map(x => x.n.toLocaleString("fr-FR"));
    const exactSeq = exactSelection.map(x => Number(summaryRow(summary, x.name, "exact-seq", 1).mean_seconds));
    const exactOmp = exactSelection.map(x => Number(summaryRow(summary, x.name, "exact-omp", 4).mean_seconds));
    const exactCats = exactSelection.map(x => String(x.n));
    lineChart(slide, { left: 52, top: 190, width: 560, height: 400, categories: greedyCats,
      series: [{ name: "Séquentiel", values: greedySeq, color: C.navy }, { name: "OpenMP 4", values: greedyOmp, color: C.teal }], yFormat: "0.000" });
    lineChart(slide, { left: 654, top: 190, width: 560, height: 400, categories: exactCats,
      series: [{ name: "Séquentiel", values: exactSeq, color: C.navy }, { name: "OpenMP 4", values: exactOmp, color: C.orange }], yFormat: "0.000" });
    addNotes(slide, `Les tailles exactes sont choisies par le pilote séquentiel de 60 secondes. Les tailles gloutonnes vont jusqu'à 12 000 sommets. L'échelle verticale est propre à chaque graphique. ${sourceParallel}`);
  }

  // 16. Gantt.
  {
    const slide = addBase(presentation, "Ordonnancement Gantt des tâches", 16);
    addGantt(slide, events);
    addNotes(slide, `Gantt distinct des mesures de performance. La trace utilise G36, K=6 et une profondeur de tâches 2. Les barres turquoise sont les tâches feuilles journalisées ; les bandes grises signifient qu'aucune tâche feuille n'a été journalisée sur ce thread pendant cet intervalle. Ces intervalles comprennent les attentes et les périodes sans travail disponible. ${sourceParallel}`);
  }

  // 17. Applications and close.
  {
    const slide = addBase(presentation, "Applications et conclusion", 17);
    addTable(slide, [
      ["Domaine", "Sommet", "Arête", "Couleur"],
      ["Examens", "Examen", "Étudiant commun", "Créneau"],
      ["Télécommunications", "Émetteur", "Interférence", "Fréquence"],
      ["Compilation", "Variable", "Durées de vie chevauchées", "Registre"],
      ["Industrie", "Tâche", "Incompatibilité", "Machine ou période"],
    ], { left: 82, top: 172, width: 1110, height: 300 }, [220, 250, 390, 250]);
    addText(slide, 92, 526, 1080, 88,
      "Le glouton donne vite une solution valide. Le backtracking certifie l'optimum. OpenMP exploite les voisins indépendants et les branches de recherche, avec des gains qui dépendent de la charge et des synchronisations.",
      { size: 22, color: C.ink });
    addNotes(slide, `Conclusion : présenter les compromis entre méthode heuristique et méthode exacte, puis interpréter les résultats mesurés. Exemples d'applications : télécommunications, allocation de registres dans les compilateurs et planification industrielle. ${sourceGeneral} ${sourceComplexity} ${sourceParallel}`);
  }

  return { exactName, greedyName, slideCount: presentation.slides.items.length };
}
