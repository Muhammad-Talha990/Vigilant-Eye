# Sync FYP placed-training artifacts into NEW PROJ after train_yolo completes.
# Usage (from NEW PROJ Vigilant Eye root):
#   powershell -File scripts/sync_placed_train_artifacts.ps1

$ErrorActionPreference = "Stop"
$src = "C:\Users\KING\Desktop\FYP\Vigilant Eye\ai\runs\train\ufm_custom"
$dst = Join-Path $PSScriptRoot "..\ai\runs\train\ufm_custom"
$dst = [IO.Path]::GetFullPath($dst)

if (-not (Test-Path "$src\weights\best.pt")) {
    throw "Source best.pt missing: $src\weights\best.pt"
}
if (-not (Test-Path "$src\results.csv")) {
    throw "Source results.csv missing — training may still be running."
}

$lines = Get-Content "$src\results.csv"
# header + 15 epoch rows expected for --epochs 15
if ($lines.Count -lt 16) {
    Write-Warning "results.csv has $($lines.Count - 1) epoch rows (want 15). Syncing anyway."
}

New-Item -ItemType Directory -Force -Path "$dst\weights" | Out-Null
Copy-Item -Force "$src\weights\best.pt" "$dst\weights\best.pt"
Copy-Item -Force "$src\weights\last.pt" "$dst\weights\last.pt"
Copy-Item -Force "$src\results.csv" "$dst\results.csv"
Copy-Item -Force "$src\args.yaml" "$dst\args.yaml"
Get-ChildItem $src -Filter "*.png" -File | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $dst $_.Name)
}

Write-Host "Synced to $dst"
Get-Item "$dst\weights\best.pt", "$dst\results.csv" | Format-Table FullName, Length, LastWriteTime
