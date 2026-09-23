<#
.SYNOPSIS
  Build a submission-ready VigilantEye zip without venv / node_modules / giant datasets.

.DESCRIPTION
  Windows Explorer "Send to compressed folder" crashes on this repo because it is
  ~2GB+ and 60k+ files (backend/venv, ai/dataset, frontend/node_modules).

  This script packs source + docs + small samples only.
#>
param(
  [string]$OutDir = "",
  [switch]$IncludeGit,
  [switch]$IncludeDatasetYamlOnly
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutDir) {
  $OutDir = Join-Path ([Environment]::GetFolderPath("Desktop")) "VigilantEye_Submission"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$ZipPath = Join-Path $OutDir "VigilantEye_$stamp.zip"

# Directories / patterns to skip (relative, forward-slash normalized)
$SkipDirNames = @(
  ".git",
  "venv",
  "node_modules",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  "dist",
  ".vite",
  "uploads",
  "pending_persist"
)

# Always skip these path prefixes (relative to repo root)
$SkipPrefixes = @(
  "backend/venv",
  "frontend/node_modules",
  "frontend/dist",
  "ai/dataset/ufm/images",
  "ai/dataset/ufm/labels",
  "ai/dataset/ufm/dataset",
  "ai/dataset/_extracted_frames",
  "backend/uploads",
  "ai/runs/train",
  "ai/weights"
)

if ($IncludeGit) {
  $SkipDirNames = $SkipDirNames | Where-Object { $_ -ne ".git" }
}

function Should-Skip([string]$rel) {
  $n = $rel.Replace("\", "/")
  foreach ($p in $SkipPrefixes) {
    if ($n -eq $p -or $n.StartsWith("$p/")) { return $true }
  }
  $parts = $n.Split("/")
  foreach ($part in $parts) {
    if ($SkipDirNames -contains $part) { return $true }
  }
  # Heavy binary / cache extensions
  if ($n -match '\.(pt|pth|onnx|pyc|pyo|zip|tar|gz|7z|rar)$') { return $true }
  if ($n -match '(^|/)\.env$') { return $true }
  return $false
}

Write-Host "Root: $Root"
Write-Host "Zip:  $ZipPath"

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

$zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
$added = 0
$skipped = 0
$bytes = 0L

try {
  $files = Get-ChildItem -Path $Root -Recurse -File -Force -ErrorAction SilentlyContinue
  foreach ($f in $files) {
    $rel = $f.FullName.Substring($Root.Length).TrimStart("\", "/")
    $relNorm = $rel.Replace("\", "/")

    if (Should-Skip $relNorm) {
      $skipped++
      continue
    }

    # Keep dataset yaml / readmes but not image blobs
    if ($relNorm.StartsWith("ai/dataset/") -and $relNorm -match '\.(jpg|jpeg|png|bmp|webp|tif|tiff)$') {
      $skipped++
      continue
    }

    try {
      # Zip entry names must use /
      [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip,
        $f.FullName,
        $relNorm,
        [System.IO.Compression.CompressionLevel]::Optimal
      )
      $added++
      $bytes += $f.Length
    } catch {
      Write-Warning "Skip unreadable: $relNorm ($($_.Exception.Message))"
      $skipped++
    }
  }

  # Small README for evaluators inside the zip
  $readmeEntry = $zip.CreateEntry("SUBMISSION_README.txt")
  $sw = New-Object System.IO.StreamWriter($readmeEntry.Open())
  $sw.Write(@"
VigilantEye — submission package
================================
This zip EXCLUDES:
  - backend/venv (recreate with pip install -r backend/requirements.txt)
  - frontend/node_modules (recreate with npm install)
  - ai/dataset image blobs (~1GB training images)
  - *.pt YOLO weights (download yolov8n.pt or train custom weights)
  - backend/uploads evidence dumps
  - .git history

Quick start:
  1) Extract zip
  2) Backend:  cd backend && python -m venv venv && venv\Scripts\activate
               pip install -r requirements.txt
               uvicorn main:app --reload
  3) Frontend: cd frontend && npm install && npm run dev
  4) Demo login password: Demo@123 (see project README)

Weights: place COCO yolov8n.pt under ai/weights/ (Ultralytics will also auto-download).
"@)
  $sw.Dispose()
}
finally {
  $zip.Dispose()
}

$zipMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "Done."
Write-Host ("  Added:   {0} files ({1:N1} MB uncompressed source)" -f $added, ($bytes/1MB))
Write-Host ("  Skipped: {0} files" -f $skipped)
Write-Host ("  Zip size:{0} MB" -f $zipMB)
Write-Host ("  Path:    {0}" -f $ZipPath)
