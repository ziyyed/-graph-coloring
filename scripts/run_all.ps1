$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & "$PSScriptRoot/build.ps1"
    if ($LASTEXITCODE -ne 0) { throw 'Compilation échouée.' }
    python tests/test_color.py
    if ($LASTEXITCODE -ne 0) { throw 'Les tests fonctionnels ont échoué.' }
    python scripts/generate_graphs.py
    if ($LASTEXITCODE -ne 0) { throw 'La génération des graphes a échoué.' }
    python scripts/benchmark.py
    if ($LASTEXITCODE -ne 0) { throw 'Les mesures ont échoué.' }

    $selection = Get-Content 'results/exact_selection.json' -Raw | ConvertFrom-Json
    $largest = $selection | Sort-Object n -Descending | Select-Object -First 1
    $ganttPath = (Join-Path $root $largest.path)
    New-Item -ItemType Directory -Force -Path 'results' | Out-Null
    & '.\build\coloring.exe' $ganttPath 'exact-omp' '--threads' '2' '--task-depth' '2' '--gantt' 'results/gantt_2threads.csv'
    if ($LASTEXITCODE -ne 0) { throw 'La capture Gantt à deux threads a échoué.' }
    & '.\build\coloring.exe' $ganttPath 'exact-omp' '--threads' '4' '--task-depth' '2' '--gantt' 'results/gantt_4threads.csv'
    if ($LASTEXITCODE -ne 0) { throw 'La capture Gantt à quatre threads a échoué.' }
    python scripts/plot_results.py
    if ($LASTEXITCODE -ne 0) { throw 'La création des graphiques a échoué.' }
} finally {
    Pop-Location
}
