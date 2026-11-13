import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const sharp = require('sharp');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const results = path.join(root, 'results');
const figures = path.join(results, 'figures');
const colors = ['#007F86', '#D77A46', '#5A9B75', '#8B6AAE', '#C14953'];
const ink = '#263648';
const grid = '#DDE3E8';
const width = 1530;
const height = 900;

function csvRows(text) {
  const lines = text.replace(/^\uFEFF/, '').trim().split(/\r?\n/);
  const headers = lines.shift().split(',');
  return lines.map(line => Object.fromEntries(line.split(',').map((value, i) => [headers[i], value])));
}

function esc(text) {
  return String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

function text(x, y, label, size = 18, fill = ink, anchor = 'middle', extra = '') {
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="Arial, sans-serif" font-size="${size}px" fill="${fill}" ${extra}>${esc(label)}</text>`;
}

function formatNumber(value, digits = 2) {
  return Number(value).toFixed(digits).replace('.', ',');
}

function svgShell(title, xLabel, yLabel, body, extras = '') {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect width="100%" height="100%" fill="#FFFFFF"/>
  ${text(width / 2, 45, title, 25, ink, 'middle', 'font-weight="700"')}
  ${body}
  ${text(width / 2, height - 26, xLabel, 19, ink)}
  <text x="32" y="440" text-anchor="middle" font-family="Arial, sans-serif" font-size="19px" fill="${ink}" transform="rotate(-90 32 440)">${esc(yLabel)}</text>
  ${extras}
  </svg>`;
}

function chartSvg({ title, xLabel, yLabel, series, xDomain, xTicks, yType = 'linear', yDomain, ideal = false, legendY = 815 }) {
  const left = 155, right = 52, top = 95, bottom = 200;
  const plot = { x: left, y: top, w: width - left - right, h: height - top - bottom };
  const allY = series.flatMap(s => s.points.map(p => p.y)).filter(Number.isFinite);
  if (ideal) allY.push(xDomain[1]);
  let ymin = yDomain?.[0] ?? (yType === 'log' ? Math.min(...allY.filter(v => v > 0)) * 0.72 : 0);
  let ymax = yDomain?.[1] ?? Math.max(...allY) * 1.15;
  if (yType === 'log') {
    if (ymax <= ymin) ymax = ymin * 10;
  } else if (ymax <= ymin) ymax = ymin + 1;
  const x = value => plot.x + (value - xDomain[0]) / (xDomain[1] - xDomain[0]) * plot.w;
  const y = value => yType === 'log'
    ? plot.y + (Math.log(ymax) - Math.log(value)) / (Math.log(ymax) - Math.log(ymin)) * plot.h
    : plot.y + (ymax - value) / (ymax - ymin) * plot.h;

  let body = '';
  let yTicks = [];
  if (yType === 'log') {
    const firstPower = Math.floor(Math.log10(ymin));
    const lastPower = Math.ceil(Math.log10(ymax));
    for (let power = firstPower; power <= lastPower; power++) {
      const tick = 10 ** power;
      if (tick >= ymin && tick <= ymax) yTicks.push(tick);
    }
  } else {
    const step = ymax <= 2 ? 0.25 : ymax <= 5 ? 0.5 : Math.ceil(ymax / 8);
    for (let tick = 0; tick <= ymax + step * 0.01; tick += step) yTicks.push(tick);
  }
  for (const tick of yTicks) {
    const py = y(tick);
    body += `<line x1="${plot.x}" y1="${py}" x2="${plot.x + plot.w}" y2="${py}" stroke="${grid}" stroke-width="1.4"/>`;
    const label = yType === 'log'
      ? (tick < 1 ? tick.toFixed(Math.min(3, Math.max(1, Math.ceil(-Math.log10(tick))))).replace('.', ',') : String(tick))
      : formatNumber(tick, 2).replace(/,00$/, '');
    body += text(plot.x - 14, py + 6, label, 16, '#536170', 'end');
  }
  for (const tick of xTicks) {
    const px = x(tick.value);
    body += `<line x1="${px}" y1="${plot.y}" x2="${px}" y2="${plot.y + plot.h}" stroke="${grid}" stroke-width="1"/>`;
    body += text(px, plot.y + plot.h + 30, tick.label, 17, '#536170');
  }
  body += `<line x1="${plot.x}" y1="${plot.y + plot.h}" x2="${plot.x + plot.w}" y2="${plot.y + plot.h}" stroke="#8995A1" stroke-width="1.7"/>`;
  body += `<line x1="${plot.x}" y1="${plot.y}" x2="${plot.x}" y2="${plot.y + plot.h}" stroke="#8995A1" stroke-width="1.7"/>`;
  if (ideal) {
    // p=0 is reserved for the separate sequential reference category.
    body += `<line x1="${x(1)}" y1="${y(1)}" x2="${x(8)}" y2="${y(8)}" stroke="#626C77" stroke-width="3" stroke-dasharray="10 8"/>`;
  }
  series.forEach((s, index) => {
    const pts = s.points.filter(p => Number.isFinite(p.y) && (yType !== 'log' || p.y > 0)).sort((a, b) => a.x - b.x);
    if (!pts.length) return;
    const c = s.color ?? colors[index % colors.length];
    body += `<polyline fill="none" stroke="${c}" stroke-width="3.4" stroke-linejoin="round" stroke-linecap="round" points="${pts.map(p => `${x(p.x)},${y(p.y)}`).join(' ')}"/>`;
    for (const p of pts) body += `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="5.2" fill="${c}" stroke="white" stroke-width="1.7"/>`;
  });
  const items = [...series.map((s, i) => ({ label: s.name, color: s.color ?? colors[i % colors.length], dash: false }))];
  if (ideal) items.push({ label: 'Accélération idéale', color: '#626C77', dash: true });
  const cols = items.length > 5 ? 3 : 2;
  const colW = width / cols;
  items.forEach((item, i) => {
    const row = Math.floor(i / cols), col = i % cols;
    const lx = colW * col + 28;
    const ly = legendY + row * 28;
    body += `<line x1="${lx}" y1="${ly - 6}" x2="${lx + 34}" y2="${ly - 6}" stroke="${item.color}" stroke-width="3" ${item.dash ? 'stroke-dasharray="8 6"' : ''}/>`;
    body += text(lx + 44, ly, item.label, 15, ink, 'start');
  });
  return svgShell(title, xLabel, yLabel, body);
}

function byGraph(rows, family, graph, mode, field, threadCount = null) {
  return rows.filter(r => r.family === family && r.graph === graph && r.mode === mode && (threadCount === null || Number(r.threads) === threadCount))
    .map(r => ({ x: Number(r.threads), y: Number(r[field]) }));
}

function orderGraph(name) { return Number(name.replace(/\D/g, '')); }

async function writePng(name, svg) {
  await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(path.join(figures, name));
}

async function plotThreadCharts(rows, family) {
  const graphs = [...new Set(rows.filter(r => r.family === family).map(r => r.graph))].sort((a, b) => orderGraph(a) - orderGraph(b));
  const sequentialMode = family === 'greedy' ? 'greedy-seq' : 'exact-seq';
  const openmpMode = family === 'greedy' ? 'greedy-omp' : 'exact-omp';
  const threadLabels = [{ value: 0, label: 'Séq.' }, ...[1, 2, 4, 8].map(v => ({ value: v, label: String(v) }))];
  const specs = [
    { field: 'mean_seconds', filename: `temps_threads_${family}.png`, title: family === 'greedy' ? 'Temps moyen du glouton selon le nombre de threads' : 'Temps moyen du backtracking selon le nombre de threads', ylabel: 'Temps d’exécution (secondes)', type: 'log' },
    { field: 'speedup_vs_sequential', filename: `speedup_${family}.png`, title: family === 'greedy' ? 'Accélération du glouton selon le nombre de threads' : 'Accélération du backtracking selon le nombre de threads', ylabel: 'Accélération S(p) = T_s / T_p', type: 'linear', ideal: true },
    { field: 'efficiency', filename: `efficacite_${family}.png`, title: family === 'greedy' ? 'Efficacité du glouton selon le nombre de threads' : 'Efficacité du backtracking selon le nombre de threads', ylabel: 'Efficacité E(p) = S(p) / p', type: 'linear' },
  ];
  for (const spec of specs) {
    const series = graphs.map((graph, i) => {
      const baseline = rows.find(r => r.family === family && r.graph === graph && r.mode === sequentialMode);
      const points = baseline && Number.isFinite(Number(baseline[spec.field]))
        ? [{ x: 0, y: Number(baseline[spec.field]) }] : [];
      points.push(...rows.filter(r => r.family === family && r.graph === graph && r.mode === openmpMode)
        .map(r => ({ x: Number(r.threads), y: Number(r[spec.field]) })));
      return { name: graph, color: colors[i % colors.length], points };
    });
    const svg = chartSvg({ title: spec.title, xLabel: 'Configuration (Séq. ou nombre de threads p)', yLabel: spec.ylabel,
      series, xDomain: [0, 8], xTicks: threadLabels, yType: spec.type, ideal: Boolean(spec.ideal) });
    await writePng(spec.filename, svg);
  }
}

async function plotSize(rows, family) {
  const configs = family === 'greedy'
    ? [{ mode: 'greedy-seq', threads: 1, name: 'Glouton séquentiel', color: ink }, { mode: 'greedy-omp', threads: 4, name: 'Glouton OpenMP, 4 threads', color: colors[0] }]
    : [{ mode: 'exact-seq', threads: 1, name: 'Backtracking séquentiel', color: ink }, { mode: 'exact-omp', threads: 4, name: 'Backtracking OpenMP, 4 threads', color: colors[1] }];
  const data = configs.map(config => ({ ...config, points: rows.filter(r => r.family === family && r.mode === config.mode && Number(r.threads) === config.threads).map(r => ({ x: Number(r.vertices), y: Number(r.mean_seconds) })) }));
  const xs = [...new Set(data.flatMap(s => s.points.map(p => p.x)))].sort((a, b) => a - b);
  const svg = chartSvg({ title: family === 'greedy' ? 'Temps moyen du glouton selon la taille du graphe' : 'Temps moyen du backtracking selon la taille du graphe',
    xLabel: 'Taille du graphe (n = |V|)', yLabel: 'Temps d’exécution moyen (secondes)', series: data,
    xDomain: [xs[0], xs[xs.length - 1]], xTicks: xs.map(v => ({ value: v, label: String(v) })), yType: 'log', legendY: 815 });
  await writePng(`taille_${family}.png`, svg);
}

async function plotGantt(file, outName) {
  const events = csvRows(await fs.readFile(file, 'utf8')).map(r => ({ ...r, task_id: Number(r.task_id), thread_id: Number(r.thread_id), start: Number(r.start_s), end: Number(r.end_s), duration: Number(r.duration_s) }));
  if (!events.length) throw new Error(`Aucun événement Gantt dans ${file}`);
  const threadIds = [...new Set(events.map(e => e.thread_id))].sort((a, b) => a - b);
  const end = Math.max(...events.map(e => e.end));
  const L = 155, R = 55, T = 100, B = 190;
  const plotW = width - L - R, plotH = height - T - B;
  const rowH = plotH / threadIds.length;
  const sx = v => L + v / end * plotW;
  let body = '';
  for (let i = 0; i < threadIds.length; i++) {
    const y = T + i * rowH + rowH * 0.16;
    body += `<rect x="${L}" y="${y}" width="${plotW}" height="${rowH * 0.66}" fill="#E7ECEF"/>`;
    body += text(L - 18, y + rowH * 0.43, `Thread ${threadIds[i]}`, 18, ink, 'end');
    for (const event of events.filter(e => e.thread_id === threadIds[i])) {
      const bx = sx(event.start), bw = Math.max(1, sx(event.end) - bx);
      body += `<rect x="${bx}" y="${y + rowH * 0.07}" width="${bw}" height="${rowH * 0.52}" rx="3" fill="#007F86" stroke="white" stroke-width="1.5"/>`;
      if (bw > 28) body += text(bx + bw / 2, y + rowH * 0.42, `T${event.task_id}`, 13, '#FFFFFF');
    }
  }
  const tickEnd = Math.ceil(end * 2) / 2;
  const ticks = [];
  for (let t = 0; t <= tickEnd + 1e-9; t += 0.5) ticks.push(t);
  if (ticks[ticks.length - 1] < end - 0.05) ticks.push(end);
  for (const tick of ticks) {
    const px = sx(tick);
    body += `<line x1="${px}" y1="${T}" x2="${px}" y2="${T + plotH}" stroke="${grid}" stroke-width="1"/>`;
    body += text(px, T + plotH + 30, formatNumber(tick, 1), 16, '#536170');
  }
  body += `<line x1="${L}" y1="${T + plotH}" x2="${L + plotW}" y2="${T + plotH}" stroke="#8995A1" stroke-width="1.7"/>`;
  body += `<rect x="500" y="${height - 103}" width="24" height="18" fill="#007F86"/>` + text(536, height - 88, 'Tâche feuille exécutée', 15, ink, 'start');
  body += `<rect x="805" y="${height - 103}" width="24" height="18" fill="#E7ECEF"/>` + text(841, height - 88, 'Aucune tâche feuille journalisée', 15, ink, 'start');
  const svg = svgShell(`G36, K=6 - ${threadIds.length} threads, tâches feuilles de profondeur 2`, 'Temps depuis le début du traçage (secondes)', 'Thread OpenMP', body);
  await writePng(outName, svg);
}

async function plotTree() {
  const W = 1530, H = 900;
  let body = '';
  const root = { x: 765, y: 130, label: '∅', fill: ink, w: 120 };
  const xs = [420, 1110];
  const ys = [250, 360, 470, 580];
  const paths = [
    ['v₁ = 1', 'v₂ = 2', 'v₃ = 1', 'v₄ = 2'],
    ['v₁ = 2', 'v₂ = 1', 'v₃ = 2', 'v₄ = 1'],
  ];
  body += `<rect x="${root.x-root.w/2}" y="${root.y-27}" width="${root.w}" height="54" rx="14" fill="${root.fill}"/>` + text(root.x, root.y+8, root.label, 24, '#FFFFFF');
  for (let branch = 0; branch < 2; branch++) {
    let previous = root;
    for (let level = 0; level < 4; level++) {
      const node = { x: xs[branch], y: ys[level], label: paths[branch][level], fill: level % 2 === 0 ? colors[0] : colors[1], w: 190 };
      body += `<line x1="${previous.x}" y1="${previous.y+28}" x2="${node.x}" y2="${node.y-28}" stroke="#87929C" stroke-width="2.2"/>`;
      body += text((previous.x + node.x) / 2 + (branch === 0 ? -22 : 22), (previous.y + node.y) / 2 - 4, `c=${level % 2 === 0 ? branch + 1 : 2 - branch}`, 15, ink);
      body += `<rect x="${node.x-node.w/2}" y="${node.y-27}" width="${node.w}" height="54" rx="14" fill="${node.fill}"/>` + text(node.x, node.y+7, node.label, 20, '#FFFFFF');
      previous = node;
    }
    const leafY = 705;
    body += `<line x1="${previous.x}" y1="${previous.y+28}" x2="${previous.x}" y2="${leafY-42}" stroke="#87929C" stroke-width="2.2"/>`;
    body += `<rect x="${previous.x-235}" y="${leafY-42}" width="470" height="100" rx="13" fill="#FBEAEC" stroke="#C14953" stroke-width="2"/>`;
    body += text(previous.x, leafY-2, 'Impasse : v₅ adjacent à v₁ et v₄', 18, '#C14953', 'middle', 'font-weight="700"');
    body += text(previous.x, leafY+28, 'Les couleurs 1 et 2 sont interdites', 16, '#C14953');
  }
  body += text(W / 2, 830, 'Nœud : affectation partielle   •   Branche : choix de c   •   Feuille : solution complète ou impasse', 16, '#536170');
  await writePng('arbre_backtracking_c5_k2.png', `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="white"/>${text(W/2,48,'Arbre de recherche réduit pour C₅ avec K = 2',25,ink,'middle','font-weight="700"')}${body}</svg>`);
}

async function main() {
  await fs.mkdir(figures, { recursive: true });
  const summary = csvRows(await fs.readFile(path.join(results, 'performance_summary.csv'), 'utf8'));
  for (const family of ['greedy', 'exact']) {
    await plotThreadCharts(summary, family);
    await plotSize(summary, family);
  }
  await plotTree();
  await plotGantt(path.join(results, 'gantt_2threads.csv'), 'gantt_2threads.png');
  await plotGantt(path.join(results, 'gantt_4threads.csv'), 'gantt_4threads.png');
  console.log(`Figures écrites dans ${figures}`);
}

main().catch(error => { console.error(error); process.exitCode = 1; });
