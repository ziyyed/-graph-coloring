$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    New-Item -ItemType Directory -Force -Path 'build' | Out-Null
    & gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -fopenmp 'src/coloring.c' -o 'build/coloring.exe' -fopenmp
    if ($LASTEXITCODE -ne 0) { throw "GCC a échoué avec le code $LASTEXITCODE." }
} finally {
    Pop-Location
}
